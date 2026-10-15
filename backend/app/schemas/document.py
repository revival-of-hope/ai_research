from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    media_type: str
    size_bytes: int
    status: str
    error_message: str | None
    created_at: datetime


class SearchHit(BaseModel):
    document_id: int
    filename: str
    excerpt: str
