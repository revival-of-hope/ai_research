"""Research rules and values. This module deliberately has no framework imports."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


class ResearchError(RuntimeError):
    pass


class ConversationNotFound(ResearchError):
    pass


class ProviderNotConfigured(ResearchError):
    pass


class DocumentNotFound(ResearchError):
    pass


class BudgetExceeded(ResearchError):
    pass


@dataclass(frozen=True)
class ResearchCommand:
    question: str
    provider_id: int | None = None
    conversation_id: int | None = None
    document_ids: tuple[int, ...] = ()
    web_search: bool = False
    mode: Literal["quick", "deep"] = "deep"
    max_agents: int = 3
    max_depth: int = 1

    def __post_init__(self) -> None:
        if not 2 <= len(self.question.strip()) <= 20_000:
            raise ValueError("问题需包含 2 至 20000 个字符")
        if self.mode not in {"quick", "deep"}:
            raise ValueError("未知研究模式")
        if not 1 <= self.max_agents <= 6 or not 0 <= self.max_depth <= 2:
            raise ValueError("研究者数量或派生深度超出范围")


@dataclass(frozen=True)
class ResearchLimits:
    """Collaboration and time bounds; API usage is measured without run quotas."""

    max_agents: int
    max_depth: int
    concurrency: int
    timeout_seconds: int
    request_timeout_seconds: int = 90

    @classmethod
    def for_command(cls, command: ResearchCommand) -> "ResearchLimits":
        quick = command.mode == "quick"
        agents = 0 if quick else command.max_agents
        return cls(
            max_agents=agents,
            max_depth=0 if quick else command.max_depth,
            concurrency=max(1, min(3, agents)),
            timeout_seconds=180 if quick else 600,
        )


@dataclass
class ResearchBudget:
    """Reservations are synchronous and atomic within the owning asyncio loop.

    max_agents counts all researcher instances, including dynamically delegated
    children, across a run. Supervisor/reviewer/synthesizer are fixed roles.
    """

    limits: ResearchLimits
    agents: int = 0
    requests: int = 0
    searches: int = 0
    tool_calls: int = 0

    def reserve_agent(self, depth: int) -> int:
        if depth > self.limits.max_depth:
            raise BudgetExceeded("已达到子智能体派生深度限制")
        if self.agents >= self.limits.max_agents:
            raise BudgetExceeded("已达到本次研究的智能体总量限制")
        self.agents += 1
        return self.agents

    def record_request(self) -> None:
        self.requests += 1

    def record_search(self) -> None:
        self.searches += 1

    def record_tool(self) -> None:
        self.tool_calls += 1


@dataclass(frozen=True)
class ProviderConfig:
    id: int
    name: str
    base_url: str
    model: str
    api_key: str = field(repr=False)
    provider_type: str = "custom"


@dataclass(frozen=True)
class HistoryMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ConversationRecord:
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    kind: str = "research"
    comparison_id: int | None = None


@dataclass(frozen=True)
class PreparedResearch:
    run_id: str
    conversation_id: int
    user_id: int
    command: ResearchCommand
    provider: ProviderConfig
    history: tuple[HistoryMessage, ...]
    local_chunks: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class ResearchEvent:
    type: str
    data: dict[str, Any]


@dataclass
class ResearchResult:
    content: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)


RunStatus = Literal["running", "completed", "failed", "cancelled"]
