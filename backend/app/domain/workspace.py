"""Account and library rules, independent of persistence and delivery frameworks."""

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.providers import ProviderType


class WorkspaceError(Exception):
    pass


class NotFound(WorkspaceError):
    pass


class Conflict(WorkspaceError):
    pass


class Unauthorized(WorkspaceError):
    pass


class Forbidden(WorkspaceError):
    pass


class InvalidInput(WorkspaceError):
    pass


@dataclass
class Account:
    id: int | None
    email: str
    password_hash: str = field(repr=False)
    is_active: bool = True
    is_admin: bool = False
    created_at: datetime | None = None

    def change_access(self, actor: "Account", *, active: bool | None, admin: bool | None):
        if not actor.is_admin:
            raise Forbidden("需要管理员权限")
        if self.id == actor.id and (active is False or admin is False):
            raise Conflict("不能停用自己或移除自己的管理员权限")
        if active is not None:
            self.is_active = active
        if admin is not None:
            self.is_admin = admin


@dataclass
class ModelPreset:
    id: int | None
    user_id: int
    name: str
    base_url: str
    model: str
    api_key_encrypted: str = field(repr=False)
    provider_type: ProviderType = "custom"


@dataclass
class LibraryDocument:
    id: int | None
    user_id: int
    filename: str
    media_type: str
    size_bytes: int
    stored_path: str
    status: str = "processing"
    error_message: str | None = None
    created_at: datetime | None = None

    def complete(self, chunks: list[str]):
        if not chunks:
            raise InvalidInput("文档没有可检索的文本内容")
        self.status = "ready"
        self.error_message = None

    def fail(self, message: str):
        self.status = "failed"
        self.error_message = message[:500]
