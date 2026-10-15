from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser
from app.api.services import Accounts
from app.infrastructure.agents.probe import probe_provider
from app.schemas.provider import ProviderPublic, ProviderTestResult, ProviderUpsert, UsageSummary

router = APIRouter(tags=["accounts"])


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
    return service.save_provider(user.id, payload.model_dump(), provider_id)


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
