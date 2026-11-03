"""HTTP endpoints for paper and local-run evidence comparison."""

import asyncio

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import Session
from starlette.requests import Request

from app.api.deps import CurrentUser, SessionDep
from app.application.service.comparison import ComparisonService
from app.domain.comparison import (
    ComparisonConflict,
    ComparisonNotFound,
    ComparisonTimeout,
    EvidenceExtractionError,
)
from app.domain.research import DocumentNotFound, ProviderNotConfigured
from app.infrastructure.agents.comparison import extract_evidence
from app.infrastructure.uow.comparison import SqlComparisonUnitOfWork
from app.schemas.comparison import (
    ComparisonCreate,
    ComparisonPublic,
    ComparisonSourceChunk,
    ComparisonSummary,
    ComparisonUpdate,
    EvidenceContext,
)

router = APIRouter(prefix="/comparisons", tags=["comparisons"])


async def _cancel_on_disconnect(request: Request, operation: asyncio.Task) -> None:
    while not operation.done():
        await asyncio.sleep(0.1)
        if await request.is_disconnected():
            operation.cancel()
            return


def comparison_service(session: Session) -> ComparisonService:
    bind = session.get_bind()
    return ComparisonService(
        lambda: SqlComparisonUnitOfWork(Session(bind), owns_session=True),
        extract_evidence,
    )


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, (DocumentNotFound, ComparisonNotFound)):
        return HTTPException(404, str(error))
    if isinstance(error, ProviderNotConfigured):
        return HTTPException(422, str(error))
    if isinstance(error, ComparisonConflict):
        return HTTPException(409, str(error))
    if isinstance(error, ComparisonTimeout):
        return HTTPException(504, str(error))
    if isinstance(error, EvidenceExtractionError):
        return HTTPException(502, str(error))
    return HTTPException(422, str(error))


@router.get("", response_model=list[ComparisonSummary])
def list_comparisons(user: CurrentUser, session: SessionDep):
    return comparison_service(session).list(int(user.id))


@router.get("/{comparison_id}", response_model=ComparisonPublic)
def get_comparison(comparison_id: int, user: CurrentUser, session: SessionDep):
    try:
        return comparison_service(session).get(int(user.id), comparison_id)
    except ComparisonNotFound as error:
        raise _http_error(error) from error


@router.get("/{comparison_id}/evidence/{side}/{key}", response_model=EvidenceContext)
def get_comparison_evidence(
    comparison_id: int, side: str, key: str, user: CurrentUser, session: SessionDep,
):
    try:
        return comparison_service(session).evidence(int(user.id), comparison_id, side, key)
    except ComparisonNotFound as error:
        raise _http_error(error) from error


@router.get("/{comparison_id}/source-chunks/{side}", response_model=list[ComparisonSourceChunk])
def get_comparison_source_chunks(
    comparison_id: int,
    side: str,
    user: CurrentUser,
    session: SessionDep,
    q: str | None = Query(default=None, min_length=2, max_length=120),
):
    try:
        return comparison_service(session).source_chunks(
            int(user.id), comparison_id, side, q,
        )
    except ComparisonNotFound as error:
        raise _http_error(error) from error


@router.post("", status_code=201, response_model=ComparisonPublic)
async def create_comparison(
    request: Request, payload: ComparisonCreate, user: CurrentUser, session: SessionDep,
):
    operation = asyncio.create_task(comparison_service(session).create(
        int(user.id), payload.paper_document_id,
        payload.run_document_id, payload.provider_id, payload.metric,
    ))
    disconnect_monitor = asyncio.create_task(_cancel_on_disconnect(request, operation))
    try:
        return await operation
    except (
        DocumentNotFound, ProviderNotConfigured, EvidenceExtractionError,
        ComparisonTimeout, ValueError,
    ) as error:
        raise _http_error(error) from error
    finally:
        disconnect_monitor.cancel()
        if not operation.done():
            operation.cancel()
        await asyncio.gather(disconnect_monitor, operation, return_exceptions=True)


@router.patch("/{comparison_id}", response_model=ComparisonPublic)
def update_comparison(
    comparison_id: int, payload: ComparisonUpdate, user: CurrentUser, session: SessionDep,
):
    try:
        return comparison_service(session).update(
            int(user.id), comparison_id,
            payload.model_dump(exclude_unset=True).get("updates", []), payload.confirm,
        )
    except (ComparisonNotFound, ComparisonConflict, ValueError) as error:
        raise _http_error(error) from error
