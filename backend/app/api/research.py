import asyncio
import json
from contextlib import aclosing

import anyio
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.api.deps import CurrentUser, SessionDep
from app.application.service.research import ResearchService
from app.domain.research import (
    ConversationNotFound,
    DocumentNotFound,
    ProviderNotConfigured,
    ResearchCommand,
)
from app.infrastructure.agents.answer import DirectAnswerRunner
from app.infrastructure.agents.research import PydanticResearchRunner
from app.infrastructure.uow.research import SqlResearchUnitOfWork
from app.schemas.research import (
    ConversationPublic,
    ConversationUpdate,
    MessagePublic,
    ResearchRequest,
    ResearchRunPublic,
)

router = APIRouter(prefix="/research", tags=["research"])


def research_service(session: Session) -> ResearchService:
    bind = session.get_bind()
    return ResearchService(
        lambda: SqlResearchUnitOfWork(Session(bind), owns_session=True),
        lambda prepared: (
            DirectAnswerRunner(prepared)
            if prepared.command.mode == "quick"
            else PydanticResearchRunner(prepared)
        ),
    )


@router.get("/conversations", response_model=list[ConversationPublic])
def list_conversations(user: CurrentUser, session: SessionDep):
    return research_service(session).list_conversations(int(user.id))


@router.get("/conversations/{conversation_id}", response_model=list[MessagePublic])
def get_messages(conversation_id: int, user: CurrentUser, session: SessionDep):
    try:
        return research_service(session).messages(int(user.id), conversation_id)
    except ConversationNotFound as error:
        raise HTTPException(404, str(error)) from error


@router.get("/conversations/{conversation_id}/runs", response_model=list[ResearchRunPublic])
def get_runs(conversation_id: int, user: CurrentUser, session: SessionDep):
    try:
        return research_service(session).runs(int(user.id), conversation_id)
    except ConversationNotFound as error:
        raise HTTPException(404, str(error)) from error


@router.patch("/conversations/{conversation_id}", response_model=ConversationPublic)
def rename_conversation(
    conversation_id: int, payload: ConversationUpdate, user: CurrentUser, session: SessionDep
):
    try:
        return research_service(session).rename(int(user.id), conversation_id, payload.title)
    except ConversationNotFound as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, user: CurrentUser, session: SessionDep):
    try:
        research_service(session).delete(int(user.id), conversation_id)
    except ConversationNotFound as error:
        raise HTTPException(404, str(error)) from error
    return Response(status_code=204)


@router.post("/ask/stream")
async def ask_stream(
    payload: ResearchRequest, request: Request, user: CurrentUser, session: SessionDep
):
    service = research_service(session)
    try:
        prepared = service.prepare(
            int(user.id),
            ResearchCommand(
                **(payload.model_dump() | {"document_ids": tuple(payload.document_ids)})
            ),
        )
    except (ConversationNotFound, DocumentNotFound) as error:
        raise HTTPException(404, str(error)) from error
    except ProviderNotConfigured as error:
        raise HTTPException(422, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error

    async def watch_disconnect() -> None:
        while not await request.is_disconnected():
            await asyncio.sleep(0.2)

    async def events():
        disconnect = asyncio.create_task(watch_disconnect(), name=f"disconnect-{prepared.run_id}")
        pending = None
        try:
            async with aclosing(service.stream(prepared)) as stream:
                try:
                    while True:
                        pending = asyncio.create_task(anext(stream))
                        while True:
                            done, _ = await asyncio.wait(
                                (pending, disconnect),
                                timeout=15,
                                return_when=asyncio.FIRST_COMPLETED,
                            )
                            if done:
                                break
                            yield ": keep-alive\n\n"
                        if disconnect in done:
                            break
                        try:
                            event = pending.result()
                        except StopAsyncIteration:
                            break
                        data = json.dumps(event.data, ensure_ascii=False, separators=(",", ":"))
                        yield f"event: {event.type}\ndata: {data}\n\n"
                finally:
                    # Cancel the in-flight __anext__ before closing its generator.
                    if pending is not None and not pending.done():
                        with anyio.CancelScope(shield=True):
                            pending.cancel()
                            await asyncio.gather(pending, return_exceptions=True)
        finally:
            with anyio.CancelScope(shield=True):
                disconnect.cancel()
                await asyncio.gather(disconnect, return_exceptions=True)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
