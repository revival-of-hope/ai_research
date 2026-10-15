from __future__ import annotations

from dataclasses import asdict

from sqlalchemy import delete
from sqlmodel import Session, select

from app.domain.workspace import LibraryDocument, NotFound
from app.infrastructure.search.retrieval import retrieve_chunks
from app.models.documents import DocumentChunk, SourceDocument


def from_row(row: SourceDocument) -> LibraryDocument:
    return LibraryDocument(
        **{key: getattr(row, key) for key in LibraryDocument.__dataclass_fields__}
    )


class SqlDocumentRepo:
    def __init__(self, session: Session):
        self.session = session

    def list(self, user_id: int) -> list[LibraryDocument]:
        rows = self.session.exec(
            select(SourceDocument)
            .where(SourceDocument.user_id == user_id)
            .order_by(SourceDocument.created_at.desc())
        ).all()
        return [from_row(row) for row in rows]

    def owned(self, user_id: int, document_id: int) -> LibraryDocument:
        row = self.session.exec(
            select(SourceDocument).where(
                SourceDocument.user_id == user_id, SourceDocument.id == document_id
            )
        ).first()
        if row is None:
            raise NotFound("资料不存在")
        return from_row(row)

    def save(self, document: LibraryDocument) -> LibraryDocument:
        row = self.session.get(SourceDocument, document.id) if document.id else None
        values = asdict(document)
        if row is None:
            values.pop("id")
            if values["created_at"] is None:
                values.pop("created_at")
            row = SourceDocument(**values)
        else:
            for key, value in values.items():
                setattr(row, key, value)
        self.session.add(row)
        self.session.flush()
        return from_row(row)

    def replace_chunks(self, document_id: int, chunks: list[str]) -> None:
        self.session.exec(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        self.session.add_all(
            [
                DocumentChunk(document_id=document_id, ordinal=i, content=text)
                for i, text in enumerate(chunks)
            ]
        )

    def delete(self, document: LibraryDocument) -> None:
        self.session.exec(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        self.session.delete(self.session.get(SourceDocument, document.id))

    def search(self, user_id: int, query: str) -> list[dict]:
        ids = [d.id for d in self.list(user_id) if d.status == "ready"]
        return [
            {
                "document_id": hit["document_id"],
                "filename": hit["filename"],
                "excerpt": str(hit["content"])[:500],
            }
            for hit in retrieve_chunks(self.session, user_id, query, ids, limit=12)
        ]
