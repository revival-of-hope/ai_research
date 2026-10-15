from datetime import UTC, datetime

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(SQLModel, table=True):
    __tablename__ = "user_account"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=320)
    password_hash: str = Field(max_length=255)
    is_active: bool = Field(default=True, index=True)
    is_admin: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=utcnow)


class ApiProvider(SQLModel, table=True):
    __tablename__ = "api_provider"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user_account.id", index=True)
    name: str = Field(default="My Responses API", max_length=80)
    base_url: str = Field(max_length=500)
    model: str = Field(max_length=120)
    api_key_encrypted: str = Field(sa_column=Column(Text, nullable=False))
    updated_at: datetime = Field(default_factory=utcnow)
