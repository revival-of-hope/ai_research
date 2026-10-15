from typing import Any, Protocol

from app.domain.research import (
    ConversationRecord,
    PreparedResearch,
    ResearchCommand,
    ResearchResult,
    RunStatus,
)


class ResearchRepository(Protocol):
    def list_conversations(self, user_id: int) -> list[ConversationRecord]: ...

    def messages(self, user_id: int, conversation_id: int) -> list[Any]: ...

    def runs(self, user_id: int, conversation_id: int) -> list[Any]: ...

    def rename(self, user_id: int, conversation_id: int, title: str) -> ConversationRecord: ...

    def delete(self, user_id: int, conversation_id: int) -> None: ...

    def start(self, user_id: int, command: ResearchCommand) -> PreparedResearch: ...

    def finish(
        self,
        prepared: PreparedResearch,
        result: ResearchResult,
        status: RunStatus,
        error: str | None = None,
    ) -> None: ...
