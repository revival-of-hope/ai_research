from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.infrastructure.search.retrieval import retrieve_chunks
from app.models.documents import DocumentChunk, SourceDocument


def test_chinese_query_ranks_relevant_chunk_first() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        document = SourceDocument(
            user_id=7,
            filename="论文笔记.md",
            media_type="text/markdown",
            size_bytes=120,
            stored_path="/tmp/notes.md",
            status="ready",
        )
        session.add(document)
        session.commit()
        session.refresh(document)
        session.add(DocumentChunk(document_id=document.id, ordinal=0, content="卷积网络基础"))
        session.add(
            DocumentChunk(
                document_id=document.id,
                ordinal=1,
                content="视觉 Transformer 使用自注意力处理图像块。",
            )
        )
        session.commit()

        hits = retrieve_chunks(session, 7, "视觉Transformer注意力", [document.id])

    assert hits
    assert "自注意力" in str(hits[0]["content"])


def test_retrieval_never_crosses_user_boundary() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        document = SourceDocument(
            user_id=99,
            filename="private.txt",
            media_type="text/plain",
            size_bytes=20,
            stored_path="/tmp/private.txt",
            status="ready",
        )
        session.add(document)
        session.commit()
        session.refresh(document)
        session.add(DocumentChunk(document_id=document.id, ordinal=0, content="secret evidence"))
        session.commit()

        assert retrieve_chunks(session, 7, "secret", [document.id]) == []
