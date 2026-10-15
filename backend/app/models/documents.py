from datetime import datetime

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel

from app.models.accounts import utcnow


class SourceDocument(SQLModel, table=True):
    __tablename__ = "source_document"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user_account.id", index=True)
    filename: str = Field(max_length=255)
    media_type: str = Field(max_length=120)
    size_bytes: int
    stored_path: str = Field(max_length=600)
    status: str = Field(default="ready", max_length=30, index=True)
    error_message: str | None = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utcnow, index=True)


class DocumentChunk(SQLModel, table=True):
    __tablename__ = "document_chunk"

    id: int | None = Field(default=None, primary_key=True)
    document_id: int = Field(foreign_key="source_document.id", index=True)
    ordinal: int = Field(index=True)
    content: str = Field(sa_column=Column(Text, nullable=False))
