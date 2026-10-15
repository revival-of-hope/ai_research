from pathlib import Path

from app.infrastructure.ingest.extract import extract_text
from app.infrastructure.ingest.split import split_text


def parse_document(path: Path) -> list[str]:
    """Extract and split one document without touching the database."""
    chunks = split_text(extract_text(path))
    if not chunks:
        raise ValueError("没有从文档中提取到可检索文字，请确认文件不是空白或仅包含图片")
    return chunks
