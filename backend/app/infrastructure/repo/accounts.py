from dataclasses import asdict
from datetime import UTC, datetime

from sqlalchemy import case, exists, func, or_, union_all, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domain.workspace import Account, Conflict, ModelPreset, NotFound
from app.models.accounts import ApiProvider, User
from app.models.conversations import Conversation, Message, ResearchRun


def account_from_row(row: User) -> Account:
    return Account(**{key: getattr(row, key) for key in Account.__dataclass_fields__})


def preset_from_row(row: ApiProvider) -> ModelPreset:
    return ModelPreset(**{key: getattr(row, key) for key in ModelPreset.__dataclass_fields__})


class SqlAccountRepo:
    def __init__(self, session: Session):
        self.session = session

    def get(self, account_id: int) -> Account | None:
        row = self.session.get(User, account_id)
        return account_from_row(row) if row else None

    def by_email(self, email: str) -> Account | None:
        row = self.session.exec(select(User).where(User.email == email)).first()
        return account_from_row(row) if row else None

    def save(self, account: Account) -> Account:
        row = self.session.get(User, account.id) if account.id else None
        values = asdict(account)
        if row is None:
            values.pop("id")
            if values["created_at"] is None:
                values.pop("created_at")
            row = User(**values)
        else:
            for key, value in values.items():
                setattr(row, key, value)
        self.session.add(row)
        try:
            self.session.flush()
        except IntegrityError as error:
            raise Conflict("邮箱已注册") from error
        return account_from_row(row)

    @staticmethod
    def _usage_records():
        # New runs are authoritative, including failed/cancelled work. Older
        # assistant rows without a surviving run remain the migration fallback.
        legacy = (
            select(
                Conversation.user_id.label("user_id"),
                Message.provider_id.label("provider_id"),
                Message.provider_name.label("provider_name"),
                Message.model.label("model"),
                Message.input_tokens.label("input_tokens"),
                Message.output_tokens.label("output_tokens"),
                Message.total_tokens.label("total_tokens"),
                Message.created_at.label("created_at"),
            )
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Message.role == "assistant",
                or_(
                    Message.run_id.is_(None),
                    ~exists(select(ResearchRun.id).where(ResearchRun.id == Message.run_id)),
                ),
            )
        )
        runs = select(
            ResearchRun.user_id,
            ResearchRun.provider_id,
            ResearchRun.provider_name,
            ResearchRun.model,
            func.coalesce(ResearchRun.usage["input_tokens"].as_integer(), 0),
            func.coalesce(ResearchRun.usage["output_tokens"].as_integer(), 0),
            func.coalesce(ResearchRun.usage["total_tokens"].as_integer(), 0),
            ResearchRun.created_at,
        )
        return union_all(legacy, runs).subquery("usage_records")

    def list_with_usage(self) -> list[dict]:
        records = self._usage_records()
        rows = self.session.exec(
            select(User, func.coalesce(func.sum(records.c.total_tokens), 0))
            .outerjoin(records, records.c.user_id == User.id)
            .group_by(User.id)
            .order_by(User.created_at.desc())
        ).all()
        return [
            dict(asdict(account_from_row(user)), total_tokens=int(tokens)) for user, tokens in rows
        ]

    def providers(self, user_id: int) -> list[ModelPreset]:
        rows = self.session.exec(
            select(ApiProvider)
            .where(ApiProvider.user_id == user_id)
            .order_by(ApiProvider.updated_at.desc())
        ).all()
        return [preset_from_row(row) for row in rows]

    def provider(self, user_id: int, provider_id: int) -> ModelPreset:
        row = self.session.exec(
            select(ApiProvider).where(ApiProvider.id == provider_id, ApiProvider.user_id == user_id)
        ).first()
        if row is None:
            raise NotFound("模型预设不存在")
        return preset_from_row(row)

    def save_provider(self, provider: ModelPreset) -> ModelPreset:
        row = self.session.get(ApiProvider, provider.id) if provider.id else None
        if row is None:
            row = ApiProvider(**asdict(provider))
        else:
            for key, value in asdict(provider).items():
                setattr(row, key, value)
        row.updated_at = datetime.now(UTC)
        self.session.add(row)
        self.session.flush()
        return preset_from_row(row)

    def delete_provider(self, provider: ModelPreset) -> None:
        # Preserve the snapshot and historical usage when the preset is removed.
        self.session.exec(
            update(Message).where(Message.provider_id == provider.id).values(provider_id=None)
        )
        self.session.exec(
            update(ResearchRun)
            .where(ResearchRun.provider_id == provider.id)
            .values(provider_id=None)
        )
        self.session.delete(self.session.get(ApiProvider, provider.id))
        self.session.flush()

    def usage(self, user_id: int) -> dict:
        today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        month = today.replace(day=1)
        records = self._usage_records().c
        rows = self.session.exec(
            select(
                records.provider_id,
                records.provider_name,
                records.model,
                func.sum(case((records.created_at >= today, records.total_tokens), else_=0)),
                func.sum(case((records.created_at >= month, records.total_tokens), else_=0)),
                func.sum(records.input_tokens),
                func.sum(records.output_tokens),
                func.sum(records.total_tokens),
            )
            .where(records.user_id == user_id)
            .group_by(records.provider_id, records.provider_name, records.model)
        ).all()
        providers = [
            {
                "provider_id": row[0],
                "provider_name": row[1] or "历史预设",
                "model": row[2] or "未知模型",
                "today_tokens": int(row[3] or 0),
                "month_tokens": int(row[4] or 0),
                "input_tokens": int(row[5] or 0),
                "output_tokens": int(row[6] or 0),
                "total_tokens": int(row[7] or 0),
            }
            for row in rows
        ]
        return {
            "today_tokens": sum(p["today_tokens"] for p in providers),
            "month_tokens": sum(p["month_tokens"] for p in providers),
            "lifetime_tokens": sum(p["total_tokens"] for p in providers),
            "input_tokens": sum(p["input_tokens"] for p in providers),
            "output_tokens": sum(p["output_tokens"] for p in providers),
            "by_provider": sorted(providers, key=lambda p: -p["total_tokens"]),
        }
