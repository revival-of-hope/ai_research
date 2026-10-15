from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser
from app.api.services import Accounts
from app.core.crypto import decrypt_secret
from app.core.endpoints import validate_provider_url
from app.domain.providers import PROVIDER_CATALOG
from app.domain.workspace import InvalidInput
from app.infrastructure.agents.catalog import discover_models
from app.infrastructure.agents.probe import probe_provider
from app.schemas.provider import (
    ProviderDiscovery,
    ProviderModels,
    ProviderPublic,
    ProviderTestResult,
    ProviderUpsert,
    UsageSummary,
)

router = APIRouter(tags=["accounts"])


@router.get("/account/provider-catalog")
def provider_catalog(user: CurrentUser):
    return PROVIDER_CATALOG


@router.post("/account/provider-models", response_model=ProviderModels)
async def provider_models(payload: ProviderDiscovery, user: CurrentUser, service: Accounts):
    # Enforce ownership even when a replacement key is supplied.
    preset = service.owned_provider(user.id, payload.provider_id) if payload.provider_id else None
    base_url = validate_provider_url(str(payload.base_url))
    key = (payload.api_key or "").strip()
    if not key and preset:
        if preset.base_url.rstrip("/") != base_url:
            raise InvalidInput("请求地址已改变，请填写对应服务商的 API key 后获取模型列表")
        try:
            key = decrypt_secret(preset.api_key_encrypted) or ""
        except ValueError:
            raise InvalidInput(
                "预设密钥无法解密，请恢复原 ENCRYPTION_KEY 或重新输入 API key"
            ) from None
    if not key:
        raise InvalidInput("请先填写 API key，以获取该账户的模型列表")
    try:
        models = await discover_models(base_url, key)
    except RuntimeError as error:
        raise HTTPException(502, str(error)) from None
    return ProviderModels(models=models)


@router.get("/account/providers", response_model=list[ProviderPublic])
def list_providers(user: CurrentUser, service: Accounts):
    return service.providers(user.id)


@router.post("/account/providers", response_model=ProviderPublic, status_code=201)
def create_provider(payload: ProviderUpsert, user: CurrentUser, service: Accounts):
    return service.save_provider(user.id, payload.model_dump())


@router.put("/account/providers/{provider_id}", response_model=ProviderPublic)
def update_provider(
    provider_id: int, payload: ProviderUpsert, user: CurrentUser, service: Accounts
):
    values = payload.model_dump()
    if "provider_type" not in payload.model_fields_set:
        values.pop("provider_type")  # Preserve metadata when an older client updates the preset.
    return service.save_provider(user.id, values, provider_id)


@router.delete("/account/providers/{provider_id}", status_code=204)
def delete_provider(provider_id: int, user: CurrentUser, service: Accounts):
    service.delete_provider(user.id, provider_id)


@router.post("/account/providers/{provider_id}/test", response_model=ProviderTestResult)
async def test_provider(provider_id: int, user: CurrentUser, service: Accounts):
    provider = service.owned_provider(user.id, provider_id)
    try:
        await probe_provider(provider)
    except RuntimeError as error:
        raise HTTPException(502, str(error)) from None
    return ProviderTestResult(message="连接成功，模型已通过 Pydantic AI 返回 Responses 响应")


@router.get("/account/usage", response_model=UsageSummary)
def usage(user: CurrentUser, service: Accounts):
    return service.usage(user.id)
