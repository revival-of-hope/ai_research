"""Shared ownership and provider resolution for research and experiment checks."""

from sqlmodel import Session, select

from app.core.crypto import decrypt_secret
from app.core.endpoints import validate_provider_url
from app.domain.research import DocumentNotFound, ProviderConfig, ProviderNotConfigured
from app.models.accounts import ApiProvider
from app.models.documents import SourceDocument


def resolve_provider(session: Session, user_id: int, provider_id: int | None) -> ProviderConfig:
    query = select(ApiProvider).where(ApiProvider.user_id == user_id)
    if provider_id is not None:
        query = query.where(ApiProvider.id == provider_id)
    provider = session.exec(query.order_by(ApiProvider.updated_at.desc())).first()
    if provider is None:
        raise ProviderNotConfigured("请先创建并选择一个模型预设")
    key = decrypt_secret(provider.api_key_encrypted)
    if not key:
        raise ProviderNotConfigured("该模型预设缺少 API 密钥")
    return ProviderConfig(
        id=int(provider.id), name=provider.name,
        base_url=validate_provider_url(provider.base_url), model=provider.model,
        api_key=key, provider_type=provider.provider_type,
    )


def selected_documents(
    session: Session, user_id: int, document_ids: tuple[int, ...],
) -> dict[int, SourceDocument]:
    requested = set(document_ids)
    rows = session.exec(select(SourceDocument).where(
        SourceDocument.id.in_(requested), SourceDocument.user_id == user_id,
        SourceDocument.status == "ready",
    )).all()
    by_id = {int(row.id): row for row in rows}
    if set(by_id) != requested:
        raise DocumentNotFound("选中的资料不存在、尚未就绪或无权访问")
    return by_id
