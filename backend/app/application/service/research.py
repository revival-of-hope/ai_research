import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import aclosing
from typing import Protocol

from app.application.uow.research import ResearchUnitOfWork
from app.domain.research import (
    ConversationRecord,
    PreparedResearch,
    ResearchCommand,
    ResearchError,
    ResearchEvent,
    ResearchResult,
    RunStatus,
)

logger = logging.getLogger(__name__)


class ResearchRunner(Protocol):
    result: ResearchResult

    def stream(self) -> AsyncIterator[ResearchEvent]: ...


def _public_error(error: BaseException) -> str:
    if isinstance(error, BaseExceptionGroup):
        return _public_error(error.exceptions[0])
    if isinstance(error, TimeoutError):
        return "研究超时，请减少研究范围或选择快速模式后重试。"
    if isinstance(error, ResearchError):
        return str(error)
    return "研究未完成。请检查模型预设、服务商额度与网络后重试。"


class ResearchService:
    def __init__(
        self,
        uow_factory: Callable[[], ResearchUnitOfWork],
        runner_factory: Callable[[PreparedResearch], ResearchRunner],
    ):
        self._uow = uow_factory
        self._runner = runner_factory

    def list_conversations(self, user_id: int) -> list[ConversationRecord]:
        with self._uow() as uow:
            return uow.research.list_conversations(user_id)

    def messages(self, user_id: int, conversation_id: int) -> list[dict]:
        with self._uow() as uow:
            return uow.research.messages(user_id, conversation_id)

    def runs(self, user_id: int, conversation_id: int) -> list[dict]:
        with self._uow() as uow:
            return uow.research.runs(user_id, conversation_id)

    def rename(self, user_id: int, conversation_id: int, title: str) -> ConversationRecord:
        with self._uow() as uow:
            conversation = uow.research.rename(user_id, conversation_id, title)
            uow.commit()
            return conversation

    def delete(self, user_id: int, conversation_id: int) -> None:
        with self._uow() as uow:
            uow.research.delete(user_id, conversation_id)
            uow.commit()

    def prepare(self, user_id: int, command: ResearchCommand) -> PreparedResearch:
        with self._uow() as uow:
            prepared = uow.research.start(user_id, command)
            uow.commit()
            return prepared

    def _finish(
        self,
        prepared: PreparedResearch,
        result: ResearchResult,
        status: RunStatus,
        error: str | None = None,
    ) -> None:
        with self._uow() as uow:
            uow.research.finish(prepared, result, status, error)
            uow.commit()

    def _fail(
        self, prepared: PreparedResearch, result: ResearchResult, status: RunStatus, error: str
    ) -> None:
        try:
            self._finish(prepared, result, status, error)
        except Exception as persistence_error:  # noqa: BLE001 - termination is best effort after deletion.
            logger.warning(
                "Could not persist research termination run_id=%s kind=%s",
                prepared.run_id,
                type(persistence_error).__name__,
            )

    async def stream(self, prepared: PreparedResearch) -> AsyncIterator[ResearchEvent]:
        runner = self._runner(prepared)
        committed = False
        meta = ResearchEvent(
            "meta",
            {
                "conversation_id": prepared.conversation_id,
                "provider_id": prepared.provider.id,
                "run_id": prepared.run_id,
                "mode": prepared.command.mode,
            },
        )
        runner.result.events.append({"type": meta.type, "data": meta.data})
        try:
            yield meta
            async with aclosing(runner.stream()) as events:
                async for event in events:
                    yield event
            self._finish(prepared, runner.result, "completed")
            committed = True
            yield ResearchEvent(
                "done",
                {
                    "conversation_id": prepared.conversation_id,
                    "provider_id": prepared.provider.id,
                    "run_id": prepared.run_id,
                    "mode": prepared.command.mode,
                    "saved": True,
                    "sources": runner.result.sources,
                    "usage": runner.result.usage,
                },
            )
        except (asyncio.CancelledError, GeneratorExit):
            if not committed:
                self._fail(prepared, runner.result, "cancelled", "研究已由用户停止或连接已断开")
            raise
        except Exception as error:  # noqa: BLE001 - sanitize all provider failures at this boundary.
            message = _public_error(error)
            runner.result.events.append(
                {"type": "error", "data": {"message": message, "run_id": prepared.run_id}}
            )
            self._fail(prepared, runner.result, "failed", message)
            yield ResearchEvent("error", {"message": message, "run_id": prepared.run_id})
