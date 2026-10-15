from datetime import datetime

from sqlalchemy import JSON, Column, ForeignKey, Integer, Text
from sqlmodel import Field, SQLModel

from app.models.accounts import utcnow


class Conversation(SQLModel, table=True):
    __tablename__ = "conversation"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user_account.id", index=True)
    title: str = Field(default="New research", max_length=160)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)


class Message(SQLModel, table=True):
    __tablename__ = "message"

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id", index=True)
    role: str = Field(max_length=20)
    content: str = Field(sa_column=Column(Text, nullable=False))
    thinking: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    provider_id: int | None = Field(default=None, foreign_key="api_provider.id", index=True)
    provider_name: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=120)
    input_tokens: int = Field(default=0)
    output_tokens: int = Field(default=0)
    total_tokens: int = Field(default=0, index=True)
    sources: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    events: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    usage: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    run_id: str | None = Field(default=None, max_length=36, index=True)
    status: str = Field(default="completed", max_length=20)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class ResearchRun(SQLModel, table=True):
    __tablename__ = "research_run"

    id: str = Field(primary_key=True, max_length=36)
    conversation_id: int = Field(foreign_key="conversation.id", index=True)
    user_id: int = Field(foreign_key="user_account.id", index=True)
    provider_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("api_provider.id", ondelete="SET NULL"), index=True),
    )
    provider_name: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=120)
    status: str = Field(default="running", max_length=20, index=True)
    mode: str = Field(default="deep", max_length=20)
    question: str = Field(sa_column=Column(Text, nullable=False))
    sources: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    events: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    usage: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(default_factory=utcnow, index=True)
    finished_at: datetime | None = Field(default=None)
