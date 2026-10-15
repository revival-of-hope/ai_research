from collections.abc import Callable
from dataclasses import asdict

from app.application.uow.workspace import WorkspaceUow
from app.domain.workspace import (
    Account,
    Conflict,
    Forbidden,
    InvalidInput,
    ModelPreset,
    NotFound,
    Unauthorized,
)


class AccountService:
    def __init__(
        self,
        uow: WorkspaceUow,
        *,
        hash_password: Callable,
        verify_password: Callable,
        encrypt: Callable,
        validate_url: Callable,
    ):
        self.uow = uow
        self.hash_password = hash_password
        self.verify_password = verify_password
        self.encrypt = encrypt
        self.validate_url = validate_url

    def register(self, email: str, password: str) -> Account:
        email = email.strip().lower()
        if len(password) < 10:
            raise InvalidInput("密码至少需要 10 个字符")
        with self.uow:
            if self.uow.accounts.by_email(email):
                raise Conflict("邮箱已注册")
            account = self.uow.accounts.save(Account(None, email, self.hash_password(password)))
            self.uow.commit()
            return account

    def login(self, email: str, password: str) -> Account:
        with self.uow:
            account = self.uow.accounts.by_email(email.strip().lower())
            if account is None or not self.verify_password(password, account.password_hash):
                raise Unauthorized("邮箱或密码错误")
            if not account.is_active:
                raise Forbidden("账户已停用")
            return account

    def current(self, account_id: int) -> Account:
        with self.uow:
            account = self.uow.accounts.get(account_id)
            if account is None or not account.is_active:
                raise Unauthorized("账户不可用，请重新登录")
            return account

    @staticmethod
    def public_provider(preset: ModelPreset) -> dict:
        return {
            "id": preset.id,
            "name": preset.name,
            "base_url": preset.base_url,
            "model": preset.model,
            "compatible": True,
            "has_api_key": bool(preset.api_key_encrypted),
        }

    def providers(self, user_id: int) -> list[dict]:
        with self.uow:
            return [self.public_provider(p) for p in self.uow.accounts.providers(user_id)]

    def owned_provider(self, user_id: int, provider_id: int) -> ModelPreset:
        with self.uow:
            return self.uow.accounts.provider(user_id, provider_id)

    def save_provider(self, user_id: int, data: dict, provider_id: int | None = None) -> dict:
        name, model = data["name"].strip(), data["model"].strip()
        if not name or not model or any(c in model for c in "\r\n"):
            raise InvalidInput("名称和模型 ID 不能为空，模型 ID 不能包含换行")
        base_url = self.validate_url(str(data["base_url"]))
        with self.uow:
            preset = (
                self.uow.accounts.provider(user_id, provider_id)
                if provider_id
                else ModelPreset(None, user_id, name, base_url, model, "")
            )
            key = (data.get("api_key") or "").strip()
            if key:
                preset.api_key_encrypted = self.encrypt(key)
            if not preset.api_key_encrypted:
                raise InvalidInput("新建模型预设需要 API key")
            preset.name, preset.base_url, preset.model = name, base_url, model
            saved = self.uow.accounts.save_provider(preset)
            result = self.public_provider(saved)
            self.uow.commit()
            return result

    def delete_provider(self, user_id: int, provider_id: int):
        with self.uow:
            self.uow.accounts.delete_provider(self.uow.accounts.provider(user_id, provider_id))
            self.uow.commit()

    def usage(self, user_id: int) -> dict:
        with self.uow:
            return self.uow.accounts.usage(user_id)

    def users(self, actor: Account) -> list[dict]:
        if not actor.is_admin:
            raise Forbidden("需要管理员权限")
        with self.uow:
            return self.uow.accounts.list_with_usage()

    def change_user(self, actor: Account, user_id: int, changes: dict) -> dict:
        with self.uow:
            account = self.uow.accounts.get(user_id)
            if account is None:
                raise NotFound("账户不存在")
            account.change_access(
                actor, active=changes.get("is_active"), admin=changes.get("is_admin")
            )
            saved = self.uow.accounts.save(account)
            result = dict(
                asdict(saved), total_tokens=self.uow.accounts.usage(user_id)["lifetime_tokens"]
            )
            self.uow.commit()
            return result
