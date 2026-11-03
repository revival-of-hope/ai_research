"""Public comparison contract. Untrusted model output is never returned unchecked."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.comparison import FieldKey


class ComparisonCreate(BaseModel):
    paper_document_id: int = Field(gt=0)
    run_document_id: int = Field(gt=0)
    provider_id: int = Field(gt=0)
    metric: str = Field(min_length=1, max_length=120)


class EvidencePublic(BaseModel):
    value: str | None = None
    excerpt: str | None = None
    chunk_id: int | None = None


class EvidenceContext(BaseModel):
    filename: str
    chunk_id: int
    ordinal: int
    content: str
    page_number: int | None = None


class ComparisonSourceChunk(BaseModel):
    chunk_id: int
    ordinal: int
    content: str


class EvidenceReferenceUpdate(BaseModel):
    excerpt: str | None = Field(default=None, max_length=500)
    chunk_id: int | None = Field(default=None, gt=0)


class ComparedFieldPublic(BaseModel):
    key: FieldKey
    label: str
    paper: EvidencePublic
    run: EvidencePublic
    status: Literal["aligned", "mismatch", "unknown"]
    review_status: Literal["pending", "confirmed", "unresolved"]
    note: str = ""


class ComparisonPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    metric: str
    paper_document_id: int
    run_document_id: int
    paper_name: str
    run_name: str
    provider_id: int | None
    status: Literal["pending", "confirmed"]
    fields: list[ComparedFieldPublic]
    created_at: datetime


class ComparisonSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    metric: str
    paper_name: str
    run_name: str
    status: Literal["pending", "confirmed"]
    created_at: datetime


class FieldReview(BaseModel):
    key: FieldKey
    paper_value: str | None = Field(max_length=500)
    run_value: str | None = Field(max_length=500)
    paper_source: EvidenceReferenceUpdate | None = None
    run_source: EvidenceReferenceUpdate | None = None
    review_status: Literal["confirmed", "unresolved"]
    note: str = Field(default="", max_length=1000)


class ComparisonUpdate(BaseModel):
    updates: list[FieldReview] = Field(default_factory=list)
    confirm: bool = False
