from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete
from sqlmodel import Session, select

from app.domain.research import (
    ConversationNotFound,
    ConversationRecord,
    HistoryMessage,
    PreparedResearch,
    ProviderConfig,
    ResearchCommand,
    ResearchResult,
    RunStatus,
)
from app.infrastructure.repo.resources import resolve_provider, selected_documents
from app.infrastructure.search.retrieval import retrieve_chunks
from app.models.accounts import ApiProvider
from app.models.comparison import ComparisonRecord
from app.models.conversations import Conversation, Message, ResearchRun


def _record(conversation: Conversation, comparison_id: int | None = None) -> ConversationRecord:
    return ConversationRecord(
        id=int(conversation.id),
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        kind="comparison" if comparison_id is not None else "research",
        comparison_id=comparison_id,
    )


class SqlResearchRepository:
    def __init__(self, session: Session):
        self.session = session

    def _owned(self, user_id: int, conversation_id: int) -> Conversation:
        conversation = self.session.get(Conversation, conversation_id)
        if conversation is None or conversation.user_id != user_id:
            raise ConversationNotFound("研究会话不存在")
        return conversation

    def list_conversations(self, user_id: int) -> list[ConversationRecord]:
        rows = self.session.exec(
            select(Conversation, ComparisonRecord.id)
            .outerjoin(ComparisonRecord, ComparisonRecord.conversation_id == Conversation.id)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        ).all()
        return [_record(row, comparison_id) for row, comparison_id in rows]

    def _comparison_id(self, conversation_id: int) -> int | None:
        return self.session.exec(
            select(ComparisonRecord.id).where(ComparisonRecord.conversation_id == conversation_id)
        ).first()

    def messages(self, user_id: int, conversation_id: int) -> list[dict]:
        self._owned(user_id, conversation_id)
        rows = self.session.exec(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at, Message.id)
        ).all()
        # Return snapshots: no lazy ORM objects can outlive the short transaction.
        run_modes = dict(
            self.session.exec(
                select(ResearchRun.id, ResearchRun.mode).where(
                    ResearchRun.conversation_id == conversation_id, ResearchRun.user_id == user_id
                )
            ).all()
        )
        return [
            row.model_dump() | {"thinking": None, "mode": run_modes.get(row.run_id, "deep")}
            for row in rows
        ]

    def runs(self, user_id: int, conversation_id: int) -> list[dict]:
        self._owned(user_id, conversation_id)
        rows = self.session.exec(
            select(ResearchRun)
            .where(ResearchRun.conversation_id == conversation_id)
            .order_by(ResearchRun.created_at.desc())
            .limit(50)
        ).all()
        return [row.model_dump() for row in rows]

    def rename(self, user_id: int, conversation_id: int, title: str) -> ConversationRecord:
        conversation = self._owned(user_id, conversation_id)
        title = title.strip()
        if not 1 <= len(title) <= 160:
            raise ValueError("标题需包含 1 至 160 个字符")
        conversation.title = title
        conversation.updated_at = datetime.now(UTC)
        self.session.add(conversation)
        self.session.flush()
        return _record(conversation, self._comparison_id(conversation_id))

    def delete(self, user_id: int, conversation_id: int) -> None:
        conversation = self._owned(user_id, conversation_id)
        self.session.exec(
            delete(ComparisonRecord).where(ComparisonRecord.conversation_id == conversation_id)
        )
        self.session.exec(delete(ResearchRun).where(ResearchRun.conversation_id == conversation_id))
        self.session.exec(delete(Message).where(Message.conversation_id == conversation_id))
        self.session.delete(conversation)

    def _provider(self, user_id: int, provider_id: int | None) -> ProviderConfig:
        return resolve_provider(self.session, user_id, provider_id)

    def start(self, user_id: int, command: ResearchCommand) -> PreparedResearch:
        provider = self._provider(user_id, command.provider_id)
        if command.document_ids:
            selected_documents(self.session, user_id, command.document_ids)
        history = ()
        if command.conversation_id is not None:
            conversation = self._owned(user_id, command.conversation_id)
            if self._comparison_id(command.conversation_id) is not None:
                raise ValueError("该记录为实验核验，请新建研究会话后继续问答")
            recent = self.session.exec(
                select(Message)
                .where(Message.conversation_id == conversation.id, Message.status == "completed")
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(6)
            ).all()
            history = tuple(
                HistoryMessage(row.role, row.content[-6_000:]) for row in reversed(recent)
            )
        else:
            conversation = Conversation(user_id=user_id, title=command.question.strip()[:80])
            self.session.add(conversation)
            self.session.flush()
        run_id = str(uuid4())
        self.session.add(
            Message(
                conversation_id=int(conversation.id),
                role="user",
                content=command.question.strip(),
                run_id=run_id,
            )
        )
        self.session.add(
            ResearchRun(
                id=run_id,
                conversation_id=int(conversation.id),
                user_id=user_id,
                provider_id=provider.id,
                provider_name=provider.name,
                model=provider.model,
                question=command.question.strip(),
                mode=command.mode,
            )
        )
        conversation.updated_at = datetime.now(UTC)
        self.session.add(conversation)
        chunks = retrieve_chunks(
            self.session, user_id, command.question, list(command.document_ids)
        )
        return PreparedResearch(
            run_id=run_id,
            conversation_id=int(conversation.id),
            user_id=user_id,
            command=command,
            provider=provider,
            history=history,
            local_chunks=tuple(chunks),
        )

    def finish(
        self,
        prepared: PreparedResearch,
        result: ResearchResult,
        status: RunStatus,
        error: str | None = None,
    ) -> None:
        conversation = self._owned(prepared.user_id, prepared.conversation_id)
        run = self.session.get(ResearchRun, prepared.run_id)
        if run is None or run.user_id != prepared.user_id:
            raise ConversationNotFound("研究运行不存在")
        if run.status != "running":
            raise RuntimeError("研究运行已结束，不能重复提交")
        run.status = status
        run.sources = list(result.sources)
        run.events = list(result.events)
        run.usage = dict(result.usage)
        run.error = error
        run.finished_at = datetime.now(UTC)
        self.session.add(run)
        if status == "completed":
            if not result.content.strip():
                raise ValueError("研究没有生成可显示的报告")
            self.session.add(
                Message(
                    conversation_id=prepared.conversation_id,
                    role="assistant",
                    content=result.content,
                    thinking=None,
                    provider_id=(
                        prepared.provider.id
                        if self.session.get(ApiProvider, prepared.provider.id) is not None
                        else None
                    ),
                    provider_name=prepared.provider.name,
                    model=prepared.provider.model,
                    input_tokens=result.usage.get("input_tokens", 0),
                    output_tokens=result.usage.get("output_tokens", 0),
                    total_tokens=result.usage.get("total_tokens", 0),
                    sources=list(result.sources),
                    events=list(result.events),
                    usage=dict(result.usage),
                    run_id=prepared.run_id,
                )
            )
        conversation.updated_at = datetime.now(UTC)
        self.session.add(conversation)
