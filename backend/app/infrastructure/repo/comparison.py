"""Comparison SQL operations, source selection and tenant checks."""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlmodel import Session, select

from app.domain.comparison import ComparisonNotFound, normalize_source_text
from app.domain.research import DocumentNotFound, ProviderConfig
from app.infrastructure.repo.resources import resolve_provider, selected_documents
from app.models.accounts import utcnow
from app.models.comparison import ComparisonRecord
from app.models.conversations import Conversation
from app.models.documents import DocumentChunk, SourceDocument


def _verified_pdf_page(path: str, excerpt: str | None) -> int | None:
    """Return a 1-based page only when a literal excerpt occurs on one PDF page."""
    if not excerpt or Path(path).suffix.lower() != ".pdf":
        return None
    normalized = normalize_source_text(excerpt)
    try:
        matches = [
            index
            for index, page in enumerate(PdfReader(path).pages, start=1)
            if normalized in normalize_source_text(page.extract_text() or "")
        ]
    except (OSError, ValueError, PdfReadError):
        return None
    return matches[0] if len(matches) == 1 else None


class SqlComparisonRepository:
    def __init__(self, session: Session):
        self.session = session

    def _owned(
        self, user_id: int, comparison_id: int, *, for_update: bool = False,
    ) -> ComparisonRecord:
        statement = select(ComparisonRecord).where(
            ComparisonRecord.id == comparison_id,
            ComparisonRecord.user_id == user_id,
        )
        if for_update:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        record = self.session.exec(statement).first()
        if record is None:
            raise ComparisonNotFound("核验记录不存在")
        return record

    def _candidate(self, document: SourceDocument, metric: str, side: str = "paper") -> dict:
        chunks = self.session.exec(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.ordinal)
            .limit(4000)
        ).all()
        metric_terms = tuple(
            term for term in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", metric.casefold())
            if len(term) > 1 and term not in {"check", "table"}
        )
        context_terms = (
            "dataset", "data", "split", "model", "metric", "result", "experiment",
            "train", "pre-train", "fine-tun", "validation", "test", "accuracy",
            "error", "seed", "preprocess", "resolution", "结果", "实验",
        )
        ranked = sorted(
            chunks,
            key=lambda row: (
                -(
                    4 * int(metric.casefold() in row.content.casefold())
                    + 3 * sum(term in row.content.casefold() for term in metric_terms)
                    + sum(term in row.content.casefold() for term in context_terms)
                ),
                row.ordinal,
            ),
        )
        chosen = ranked[:12]
        return {
            "id": document.id,
            "filename": document.filename,
            "side": side,
            "chunks": [
                {"id": chunk.id, "ordinal": chunk.ordinal, "content": chunk.content[:3000]}
                for chunk in chosen
            ],
        }

    def prepare(
        self, user_id: int, paper_id: int, run_id: int, provider_id: int, metric: str,
    ) -> tuple[ProviderConfig, dict, dict]:
        if paper_id == run_id:
            raise DocumentNotFound("请选择两份不同、本人所有且已就绪的资料")
        by_id = selected_documents(self.session, user_id, (paper_id, run_id))
        config = resolve_provider(self.session, user_id, provider_id)
        paper = self._candidate(by_id[paper_id], metric, "paper")
        run = self._candidate(by_id[run_id], metric, "run")
        if not paper["chunks"] or not run["chunks"]:
            raise DocumentNotFound("所选资料缺少可检索的文本片段")
        return config, paper, run

    def list(self, user_id: int) -> list[dict]:
        rows = self.session.exec(
            select(ComparisonRecord)
            .where(ComparisonRecord.user_id == user_id)
            .order_by(ComparisonRecord.created_at.desc(), ComparisonRecord.id.desc())
        ).all()
        return [
            {
                "id": row.id, "metric": row.metric, "paper_name": row.paper_name,
                "conversation_id": row.conversation_id,
                "run_name": row.run_name, "status": row.status, "created_at": row.created_at,
            }
            for row in rows
        ]

    def get(self, user_id: int, comparison_id: int) -> dict:
        return self._owned(user_id, comparison_id).model_dump()

    def evidence(self, user_id: int, comparison_id: int, side: str, key: str) -> dict:
        record = self._owned(user_id, comparison_id)
        if side not in {"paper", "run"}:
            raise ComparisonNotFound("证据来源不存在")
        field = next((row for row in record.fields if row["key"] == key), None)
        if field is None or field[side].get("chunk_id") is None:
            raise ComparisonNotFound("这一项没有可查看的原文")
        document_id = (
            record.paper_document_id if side == "paper" else record.run_document_id
        )
        document = self.session.exec(
            select(SourceDocument).where(
                SourceDocument.id == document_id, SourceDocument.user_id == user_id,
            )
        ).first()
        if document is None:
            raise ComparisonNotFound("来源资料已删除，保存的原文摘录仍可查看")
        chunk = self.session.exec(
            select(DocumentChunk).where(
                DocumentChunk.id == field[side]["chunk_id"],
                DocumentChunk.document_id == document.id,
            )
        ).first()
        if chunk is None:
            raise ComparisonNotFound("来源片段已不存在，请依据保存的摘录复核")
        return {
            "filename": document.filename,
            "chunk_id": chunk.id,
            "ordinal": chunk.ordinal,
            "content": chunk.content,
            "page_number": _verified_pdf_page(
                document.stored_path, field[side].get("excerpt"),
            ),
        }

    def source_chunks(
        self, user_id: int, comparison_id: int, side: str, query: str | None,
    ) -> list[dict]:
        record = self._owned(user_id, comparison_id)
        if side not in {"paper", "run"}:
            raise ComparisonNotFound("证据来源不存在")
        document_id = record.paper_document_id if side == "paper" else record.run_document_id
        document = self.session.exec(
            select(SourceDocument).where(
                SourceDocument.id == document_id,
                SourceDocument.user_id == user_id,
                SourceDocument.status == "ready",
            )
        ).first()
        if document is None:
            raise ComparisonNotFound("本次核验使用的资料已不可用")

        if query is None or not query.strip():
            chunks = self._candidate(document, record.metric)["chunks"]
            return [
                {"chunk_id": chunk["id"], "ordinal": chunk["ordinal"], "content": chunk["content"]}
                for chunk in chunks
            ]

        rows = self.session.exec(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .order_by(DocumentChunk.ordinal)
            .limit(4000)
        ).all()
        normalized_query = normalize_source_text(query)
        terms = tuple(dict.fromkeys(
            re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*|[\u3400-\u9fff]+", normalized_query)
        ))

        def score(row: DocumentChunk) -> int:
            content = normalize_source_text(row.content)
            return (
                20 * int(normalized_query in content)
                + sum(min(content.count(term), 6) for term in terms)
            )

        ranked = sorted(rows, key=lambda row: (-score(row), row.ordinal))
        return [
            {"chunk_id": row.id, "ordinal": row.ordinal, "content": row.content[:3000]}
            for row in ranked if score(row) > 0
        ][:12]

    def validate_source_reference(
        self, user_id: int, comparison_id: int, side: str,
        chunk_id: int, excerpt: str,
    ) -> None:
        record = self._owned(user_id, comparison_id)
        if side not in {"paper", "run"}:
            raise ComparisonNotFound("证据来源不存在")
        if not excerpt.strip():
            raise ValueError("原文摘录不能为空")
        document_id = record.paper_document_id if side == "paper" else record.run_document_id
        document = self.session.exec(
            select(SourceDocument).where(
                SourceDocument.id == document_id,
                SourceDocument.user_id == user_id,
            )
        ).first()
        if document is None:
            raise ComparisonNotFound("本次核验使用的资料已删除")
        chunk = self.session.exec(
            select(DocumentChunk).where(
                DocumentChunk.id == chunk_id,
                DocumentChunk.document_id == document.id,
            )
        ).first()
        if chunk is None:
            raise ValueError("请选择本次核验所用资料中的原文")
        if normalize_source_text(excerpt) not in normalize_source_text(chunk.content):
            raise ValueError("原文摘录必须能在所选文本片段中核实")

    def get_for_update(self, user_id: int, comparison_id: int) -> dict:
        return self._owned(user_id, comparison_id, for_update=True).model_dump()

    def create(
        self, user_id: int, paper: dict, run: dict,
        provider_id: int, metric: str, fields: list[dict],
    ) -> dict:
        conversation = Conversation(user_id=user_id, title=f"实验核验：{metric}"[:160])
        self.session.add(conversation)
        self.session.flush()
        record = ComparisonRecord(
            user_id=user_id,
            conversation_id=int(conversation.id),
            paper_document_id=paper["id"],
            run_document_id=run["id"],
            paper_name=paper["filename"],
            run_name=run["filename"],
            provider_id=provider_id,
            metric=metric,
            fields=fields,
        )
        self.session.add(record)
        self.session.flush()
        return record.model_dump()

    def update(
        self, user_id: int, comparison_id: int, fields: list[dict], status: str,
    ) -> dict:
        record = self._owned(user_id, comparison_id, for_update=True)
        record.fields = fields
        record.status = status
        self.session.add(record)
        conversation = self.session.get(Conversation, record.conversation_id)
        if conversation is not None:
            conversation.updated_at = utcnow()
            self.session.add(conversation)
        self.session.flush()
        return record.model_dump()
