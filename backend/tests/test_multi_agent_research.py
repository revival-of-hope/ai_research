"""Run the real Pydantic AI tool loop without a network model or paid credentials."""

import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace

import anyio
import pytest
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.test import TestModel
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.application.service.research import ResearchService
from app.core.crypto import encrypt_secret
from app.domain.research import (
    BudgetExceeded,
    ConversationNotFound,
    DocumentNotFound,
    ProviderNotConfigured,
    ResearchCommand,
    ResearchLimits,
)
from app.infrastructure.agents.research import PydanticResearchRunner
from app.infrastructure.uow.research import SqlResearchUnitOfWork
from app.models.accounts import ApiProvider, User
from app.models.conversations import Conversation, Message, ResearchRun
from app.models.documents import SourceDocument


def models(researcher=None, *, two_steps=False):
    steps = [{"title": "核对证据", "task": "Investigate the primary evidence"}]
    if two_steps:
        steps.append({"title": "比较方案", "task": "Compare the alternatives"})
    return {
        "supervisor": TestModel(call_tools=[], custom_output_args={"steps": steps}),
        "researcher": researcher
        or TestModel(
            call_tools=[],
            custom_output_args={"summary": "Evidence summary", "source_labels": [], "gaps": []},
        ),
        "reviewer": TestModel(
            call_tools=[],
            custom_output_args={"assessment": "Evidence checked", "gaps": [], "conflicts": []},
        ),
        "synthesizer": TestModel(call_tools=[], custom_output_text="Research report [Web 1]."),
    }


async def search(query, limit):
    assert query and 0 < limit <= 6
    return [
        {
            "title": "Official evidence",
            "url": "https://example.com/evidence",
            "snippet": "A documented finding.",
        }
    ]


@pytest.fixture
def database():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        user = User(email="researcher@example.com", password_hash="unused")
        other = User(email="other@example.com", password_hash="unused")
        session.add_all([user, other])
        session.flush()
        provider = ApiProvider(
            user_id=int(user.id),
            name="My custom Responses model",
            base_url="https://models.example.com/v1",
            model="custom-model-with-tools",
            api_key_encrypted=encrypt_secret("test-secret"),
        )
        session.add(provider)
        session.commit()
        ids = (int(user.id), int(other.id), int(provider.id))
    yield engine, *ids
    engine.dispose()


def service(database, model_map=None, *, limits=None):
    engine, *_ = database
    return ResearchService(
        lambda: SqlResearchUnitOfWork(Session(engine), owns_session=True),
        lambda prepared: PydanticResearchRunner(
            prepared, models=model_map or models(), search=search, limits=limits
        ),
    )


async def collect(workspace, prepared):
    return [item async for item in workspace.stream(prepared)]


def test_real_tools_delegate_children_share_budget_and_persist(database):
    observed_tool_results = []

    def researcher(messages, info):
        returns = [
            part
            for message in messages
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]
        if not returns:
            return ModelResponse(
                parts=[
                    ToolCallPart("delegate_research", {"task": "Check one focused subquestion"}),
                    ToolCallPart("search_web", {"query": "official evidence"}),
                ]
            )
        observed_tool_results.extend(part.content for part in returns)
        return ModelResponse(
            parts=[
                ToolCallPart(
                    info.output_tools[0].name,
                    {"summary": "Confirmed evidence", "source_labels": ["Web 1"], "gaps": []},
                )
            ]
        )

    workspace = service(database, models(FunctionModel(researcher), two_steps=True))
    prepared = workspace.prepare(
        database[1], ResearchCommand("Compare the research evidence", web_search=True)
    )
    events = asyncio.run(collect(workspace, prepared))
    assert events[-1].type == "done"
    assert not any(item.type == "thinking" for item in events)
    assert any(item.type == "agent" and item.data["parent_id"] for item in events)
    assert any(
        isinstance(result, dict) and result.get("status") == "budget_exhausted"
        for result in observed_tool_results
    )
    done = events[-1].data
    assert done["usage"]["agents"] == 3
    assert done["usage"]["searches"] <= 9
    assert len(done["sources"]) == 1  # Duplicate URLs have a single stable citation label.
    with Session(database[0]) as session:
        run = session.get(ResearchRun, prepared.run_id)
        assistant = session.exec(select(Message).where(Message.role == "assistant")).one()
        assert run.status == "completed"
        assert assistant.sources == done["sources"]
        assert assistant.events == run.events
        assert assistant.usage == run.usage == done["usage"]
        assert assistant.thinking is None
        assert run.provider_name == "My custom Responses model"
        assert run.model == "custom-model-with-tools"


def test_request_budget_is_hard_and_failed_run_has_no_success_message(database):
    command = ResearchCommand("Research the evidence")
    limits = replace(ResearchLimits.for_command(command), requests=1)
    workspace = service(database, limits=limits)
    prepared = workspace.prepare(database[1], command)
    events = asyncio.run(collect(workspace, prepared))
    assert events[-1].type == "error"
    assert "预算" in events[-1].data["message"]
    assert not any(item.type == "done" for item in events)
    with Session(database[0]) as session:
        run = session.get(ResearchRun, prepared.run_id)
        assert run.status == "failed"
        assert run.usage["requests"] == 1
        assert session.exec(select(Message).where(Message.role == "assistant")).first() is None


def test_upstream_exception_body_is_never_exposed_or_persisted(database):
    def broken_model(messages, info):
        raise RuntimeError("provider body: API_KEY=do-not-expose and private prompt")

    workspace = service(database, models(FunctionModel(broken_model)))
    prepared = workspace.prepare(database[1], ResearchCommand("Research the evidence"))
    events = asyncio.run(collect(workspace, prepared))
    assert events[-1].type == "error"
    with Session(database[0]) as session:
        run = session.get(ResearchRun, prepared.run_id)
        trace = json.dumps(run.model_dump(mode="json"), ensure_ascii=False)
    assert "do-not-expose" not in json.dumps(events[-1].data)
    assert "do-not-expose" not in trace
    assert "private prompt" not in trace


def test_upstream_http_error_keeps_safe_actionable_reason_in_failed_run(database):
    from pydantic_ai.exceptions import ModelHTTPError

    def forbidden_model(messages, info):
        raise ModelHTTPError(401, "deepseek-flash", body={"key": "do-not-expose"})

    workspace = service(database, models(FunctionModel(forbidden_model)))
    prepared = workspace.prepare(database[1], ResearchCommand("Research the evidence"))
    events = asyncio.run(collect(workspace, prepared))
    assert events[-1].type == "error"
    assert "API key 未通过验证" in events[-1].data["message"]
    with Session(database[0]) as session:
        run = session.get(ResearchRun, prepared.run_id)
        assert run.status == "failed"
        assert run.error == events[-1].data["message"]
        assert "do-not-expose" not in json.dumps(run.model_dump(mode="json"))


def test_cancel_propagates_to_model_and_saves_only_cancelled_run(database):
    async def scenario():
        started, cancelled = asyncio.Event(), asyncio.Event()

        async def waiting_model(messages, info):
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        workspace = service(database, models(FunctionModel(waiting_model)))
        prepared = workspace.prepare(database[1], ResearchCommand("Research the evidence"))
        consumer = asyncio.create_task(collect(workspace, prepared))
        await asyncio.wait_for(started.wait(), 5)
        consumer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await consumer
        assert cancelled.is_set()
        assert not [task for task in asyncio.all_tasks() if task.get_name().startswith("research-")]
        return prepared

    prepared = asyncio.run(scenario())
    with Session(database[0]) as session:
        run = session.get(ResearchRun, prepared.run_id)
        assert run.status == "cancelled"
        assert run.usage["requests"] >= 1
        assert session.exec(select(Message).where(Message.role == "assistant")).first() is None


def test_closing_after_meta_cancels_even_before_first_model_request(database):
    workspace = service(database)
    prepared = workspace.prepare(database[1], ResearchCommand("Research the evidence"))

    async def scenario():
        stream = workspace.stream(prepared)
        assert (await anext(stream)).type == "meta"
        await stream.aclose()

    asyncio.run(scenario())
    with Session(database[0]) as session:
        assert session.get(ResearchRun, prepared.run_id).status == "cancelled"


def test_depth_zero_refuses_real_tool_delegation(database):
    refusals = []

    def researcher(messages, info):
        returns = [
            part
            for message in messages
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]
        if not returns:
            return ModelResponse(parts=[ToolCallPart("delegate_research", {"task": "Investigate"})])
        refusals.extend(part.content for part in returns)
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, {"summary": "Own findings"})]
        )

    workspace = service(database, models(FunctionModel(researcher)))
    prepared = workspace.prepare(
        database[1], ResearchCommand("Research evidence", max_depth=0, max_agents=2)
    )
    events = asyncio.run(collect(workspace, prepared))
    assert events[-1].type == "done"
    assert events[-1].data["usage"]["agents"] == 1
    assert refusals[0]["status"] == "budget_exhausted"
    assert "深度" in refusals[0]["message"]


def test_tenant_ownership_and_failed_prepare_roll_back(database):
    workspace = service(database)
    owner, stranger = database[1:3]
    prepared = workspace.prepare(owner, ResearchCommand("Research evidence"))
    for operation in (
        lambda: workspace.messages(stranger, prepared.conversation_id),
        lambda: workspace.runs(stranger, prepared.conversation_id),
        lambda: workspace.rename(stranger, prepared.conversation_id, "Other title"),
        lambda: workspace.delete(stranger, prepared.conversation_id),
        lambda: workspace.prepare(
            stranger,
            ResearchCommand("Research evidence", conversation_id=prepared.conversation_id),
        ),
    ):
        with pytest.raises((ConversationNotFound, ProviderNotConfigured)):
            operation()
    assert workspace.list_conversations(stranger) == []
    with Session(database[0]) as session:
        session.add(
            ApiProvider(
                user_id=stranger,
                name="Another user's model",
                base_url="https://models.example.com/v1",
                model="custom-model",
                api_key_encrypted=encrypt_secret("stranger-secret"),
            )
        )
        session.commit()
    with pytest.raises(ConversationNotFound):
        workspace.prepare(
            stranger,
            ResearchCommand("Research evidence", conversation_id=prepared.conversation_id),
        )
    with Session(database[0]) as session:
        document = SourceDocument(
            user_id=stranger,
            filename="private.txt",
            media_type="text/plain",
            size_bytes=1,
            stored_path="unused",
        )
        session.add(document)
        session.commit()
        document_id = int(document.id)
    with pytest.raises(DocumentNotFound):
        workspace.prepare(owner, ResearchCommand("Research evidence", document_ids=(document_id,)))
    with Session(database[0]) as session:
        assert len(session.exec(select(Conversation)).all()) == 1
        assert len(session.exec(select(ResearchRun)).all()) == 1


def test_provider_deleted_after_prepare_does_not_break_completed_snapshot(database):
    workspace = service(database)
    prepared = workspace.prepare(database[1], ResearchCommand("Research evidence"))
    with Session(database[0]) as session:
        session.delete(session.get(ApiProvider, database[3]))
        session.commit()
    events = asyncio.run(collect(workspace, prepared))
    assert events[-1].type == "done"
    with Session(database[0]) as session:
        assistant = session.exec(select(Message).where(Message.role == "assistant")).one()
        assert assistant.provider_id is None
        assert assistant.provider_name == prepared.provider.name
        assert session.get(ResearchRun, prepared.run_id).provider_id is None


def test_quick_mode_and_domain_limits_are_deterministic():
    from app.domain.research import ResearchBudget

    limits = ResearchLimits.for_command(ResearchCommand("Research evidence", mode="quick"))
    assert limits.max_agents == 1 and limits.max_depth == 0
    budget = ResearchBudget(limits)
    assert budget.reserve_agent(0) == 1
    with pytest.raises(BudgetExceeded):
        budget.reserve_agent(0)
    with pytest.raises(BudgetExceeded):
        budget.reserve_agent(1)


@pytest.mark.parametrize("cancel_scope", [False, True])
def test_http_disconnect_cancels_inflight_anext_before_generator_close(
    database, monkeypatch, cancel_scope
):
    from app.api import research as routes
    from app.schemas.research import ResearchRequest

    async def scenario():
        started, disconnected, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def waiting_model(messages, info):
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

        workspace = service(database, models(FunctionModel(waiting_model)))
        monkeypatch.setattr(routes, "research_service", lambda _: workspace)

        class Request:
            async def is_disconnected(self):
                return disconnected.is_set()

        with Session(database[0]) as session:
            response = await routes.ask_stream(
                ResearchRequest(question="Research evidence"),
                Request(),
                SimpleNamespace(id=database[1]),
                session,
            )
            frames = []

            async def consume():
                frames.extend(await _consume_http(response.body_iterator))

            async with anyio.create_task_group() as group:
                group.start_soon(consume)
                await asyncio.wait_for(started.wait(), 5)
                if cancel_scope:
                    group.cancel_scope.cancel()
                else:
                    disconnected.set()
        assert cancelled.is_set()
        assert not any("event: done" in frame for frame in frames)

    asyncio.run(scenario())
    with Session(database[0]) as session:
        assert session.exec(select(ResearchRun)).one().status == "cancelled"


async def _consume_http(iterator):
    return [item async for item in iterator]
