import re
import unicodedata

from sqlmodel import Session, select

from app.models.documents import DocumentChunk, SourceDocument

TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9_.+-]*|[\u3400-\u9fff]+")
MAX_CANDIDATE_CHUNKS = 4_000


def _fold(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _query_terms(query: str) -> list[str]:
    terms: list[str] = []
    for token in TOKEN_PATTERN.findall(_fold(query)):
        if re.fullmatch(r"[\u3400-\u9fff]+", token):
            terms.append(token)
            if len(token) > 2:
                terms.extend(token[index : index + 2] for index in range(len(token) - 1))
        elif len(token) >= 2:
            terms.append(token)
    return list(dict.fromkeys(terms))


def _score(query: str, terms: list[str], filename: str, content: str) -> float:
    haystack = _fold(content)
    score = 0.0
    folded_query = _fold(query).strip()
    if len(folded_query) >= 2 and folded_query in haystack:
        score += 50.0
    for term in terms:
        occurrences = min(haystack.count(term), 6)
        score += occurrences * (2.0 + min(len(term), 8) / 2)
        if term in _fold(filename):
            score += 6.0
    return score


def retrieve_chunks(
    session: Session, user_id: int, query: str, document_ids: list[int], limit: int = 8
) -> list[dict[str, str | int]]:
    if not document_ids:
        return []
    statement = (
        select(DocumentChunk, SourceDocument.filename)
        .join(SourceDocument, SourceDocument.id == DocumentChunk.document_id)
        .where(
            SourceDocument.user_id == user_id,
            SourceDocument.status == "ready",
            DocumentChunk.document_id.in_(document_ids),
        )
        .order_by(DocumentChunk.ordinal)
        .limit(MAX_CANDIDATE_CHUNKS)
    )
    rows = list(session.exec(statement).all())
    terms = _query_terms(query)
    ranked = [
        (_score(query, terms, filename, chunk.content), chunk, filename) for chunk, filename in rows
    ]
    ranked.sort(key=lambda item: (-item[0], item[1].ordinal))

    matching = [item for item in ranked if item[0] > 0]
    selected = (matching or ranked)[:limit]
    return [
        {
            "document_id": chunk.document_id,
            "filename": filename,
            "content": chunk.content,
        }
        for _, chunk, filename in selected
    ]
