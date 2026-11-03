"""Stored comparison snapshots remain readable if source documents are deleted."""

from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

from app.models.accounts import utcnow


class ComparisonRecord(SQLModel, table=True):
    __tablename__ = "comparison_record"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user_account.id", index=True)
    paper_document_id: int
    run_document_id: int
    paper_name: str = Field(max_length=255)
    run_name: str = Field(max_length=255)
    provider_id: int | None = None
    metric: str = Field(max_length=120)
    status: str = Field(default="pending", max_length=20)
    fields: list[dict] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(default_factory=utcnow, index=True)
