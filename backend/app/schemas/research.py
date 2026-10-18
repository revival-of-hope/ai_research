from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ResearchRequest(BaseModel):
    question: str = Field(min_length=2, max_length=20_000)
    provider_id: int | None = None
    conversation_id: int | None = None
    document_ids: list[int] = Field(default_factory=list, max_length=30)
    web_search: bool = False
    mode: Literal["quick", "deep"] = "deep"
    max_agents: int = Field(default=3, ge=1, le=6)
    max_depth: int = Field(default=1, ge=0, le=2)


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    requests: int = 0
    searches: int = 0
    agents: int = 0
    tool_calls: int = 0


class ConversationPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    created_at: datetime
    updated_at: datetime


class MessagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    thinking: str | None
    provider_id: int | None
    provider_name: str | None
    model: str | None
    total_tokens: int
    sources: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    usage: dict = Field(default_factory=dict)
    run_id: str | None = None
    status: str = "completed"
    mode: Literal["quick", "deep"] = "deep"
    created_at: datetime


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class ResearchRunPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: int
    provider_id: int | None = None
    provider_name: str | None = None
    model: str | None = None
    status: str
    mode: str
    question: str
    sources: list[dict] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)
    usage: dict = Field(default_factory=dict)
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
