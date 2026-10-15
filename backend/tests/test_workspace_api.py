"""Exercise delivery -> service -> UoW -> real SQL repos with tenant isolation."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.config import settings
from app.core.db import get_session
from app.domain.workspace import Account
from app.infrastructure.ingest.storage import LocalDocumentStorage, UploadTooLarge
from app.infrastructure.uow.workspace import SqlWorkspaceUow
from app.main import app
from app.models.accounts import ApiProvider, User
from app.models.conversations import Conversation, Message, ResearchRun


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.main.ensure_admin", lambda: None)
    monkeypatch.setattr(settings, "upload_dir", tmp_path / "uploads")

    def sessions():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    with TestClient(app) as client:
        yield client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def register(client, email="first@example.com"):
    response = client.post(
        "/api/auth/register", json={"email": email, "password": "passphrase-123"}
    )
    assert response.status_code == 201, response.text
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "password_hash" not in response.json()
    return response.json(), client.cookies.get("access_token")


def create_provider(client):
    response = client.post(
        "/api/account/providers",
        json={
            "name": "Custom research",
            "base_url": "https://models.example.com/v1",
            "model": "my-actual-model",
            "api_key": "private-test-key",
        },
    )
    assert response.status_code == 201, response.text
    assert "private-test-key" not in response.text
    return response.json()


def test_registration_login_logout_and_duplicate_email(workspace):
    client, _ = workspace
    user, _ = register(client)
    assert client.get("/api/account/me").json()["id"] == user["id"]
    assert (
        client.post(
            "/api/auth/register", json={"email": user["email"], "password": "passphrase-123"}
        ).status_code
        == 409
    )
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/account/me").status_code == 401
    assert (
        client.post(
            "/api/auth/login", json={"email": user["email"], "password": "wrong"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login", json={"email": user["email"], "password": "passphrase-123"}
        ).status_code
        == 200
    )


def test_provider_secret_updates_and_owner_boundary(workspace):
    client, engine = workspace
    register(client)
    preset = create_provider(client)
    with Session(engine) as session:
        encrypted = session.get(ApiProvider, preset["id"]).api_key_encrypted
        assert "private-test-key" not in encrypted
    updated = client.put(
        f"/api/account/providers/{preset['id']}",
        json={"name": "Renamed", "base_url": preset["base_url"], "model": "new-model"},
    )
    assert updated.status_code == 200
    with Session(engine) as session:
        assert session.get(ApiProvider, preset["id"]).api_key_encrypted == encrypted
    register(client, "second@example.com")
    assert client.get("/api/account/providers").json() == []
    assert client.delete(f"/api/account/providers/{preset['id']}").status_code == 404


def test_provider_catalog_and_selection_survive_secret_preserving_update(workspace):
    client, engine = workspace
    assert client.get("/api/account/provider-catalog").status_code == 401
    register(client)
    catalog = client.get("/api/account/provider-catalog").json()
    assert {entry["id"] for entry in catalog} >= {"openai", "deepseek", "qwen", "anthropic"}
    deepseek = next(entry for entry in catalog if entry["id"] == "deepseek")
    assert deepseek["base_url"] == "https://api.deepseek.com"
    assert "deepseek-flash" in deepseek["models"]
    preset = create_provider(client)
    response = client.put(
        f"/api/account/providers/{preset['id']}",
        json={
            "name": "DeepSeek",
            "base_url": deepseek["base_url"],
            "model": "deepseek-flash",
            "provider_type": "deepseek",
            "api_key": "private-test-key",
        },
    )
    assert response.status_code == 200
    assert response.json()["provider_type"] == "deepseek"
    assert client.get("/api/account/providers").json()[0]["provider_type"] == "deepseek"
    legacy_update = client.put(
        f"/api/account/providers/{preset['id']}",
        json={
            "name": "Renamed by old client",
            "base_url": deepseek["base_url"],
            "model": "deepseek-flash",
        },
    )
    assert legacy_update.status_code == 200
    assert legacy_update.json()["provider_type"] == "deepseek"
    with Session(engine) as session:
        from app.core.crypto import decrypt_secret

        assert decrypt_secret(session.get(ApiProvider, preset["id"]).api_key_encrypted) == (
            "private-test-key"
        )


def test_model_discovery_reuses_only_an_owned_secret_and_never_generates(workspace, monkeypatch):
    client, _ = workspace
    register(client)
    preset = create_provider(client)
    observed = []

    async def discover(base_url, key):
        observed.append((base_url, key))
        return ["deepseek-flash", "deepseek-v4-pro"]

    monkeypatch.setattr("app.api.accounts.discover_models", discover)
    request = {"provider_id": preset["id"], "base_url": preset["base_url"]}
    response = client.post("/api/account/provider-models", json=request)
    assert response.status_code == 200
    assert response.json()["source"] == "live"
    assert response.json()["models"] == ["deepseek-flash", "deepseek-v4-pro"]
    assert observed == [(preset["base_url"], "private-test-key")]
    assert "private-test-key" not in response.text
    register(client, "model-list-other@example.com")
    assert client.post("/api/account/provider-models", json=request).status_code == 404
    assert len(observed) == 1
    assert (
        client.post(
            "/api/account/provider-models",
            json={
                "base_url": "https://api.deepseek.com",
            },
        ).status_code
        == 422
    )


def test_changed_endpoint_cannot_reuse_a_stored_key(workspace, monkeypatch):
    client, _ = workspace
    register(client)
    preset = create_provider(client)

    async def must_not_request(*args):
        pytest.fail("An old key must not be forwarded to a changed endpoint")

    monkeypatch.setattr("app.api.accounts.discover_models", must_not_request)
    discovery = client.post(
        "/api/account/provider-models",
        json={
            "provider_id": preset["id"],
            "base_url": "https://api.deepseek.com",
        },
    )
    assert discovery.status_code == 422
    assert "请求地址已改变" in discovery.json()["detail"]
    update = client.put(
        f"/api/account/providers/{preset['id']}",
        json={
            "name": "DeepSeek",
            "model": "deepseek-flash",
            "base_url": "https://api.deepseek.com",
        },
    )
    assert update.status_code == 422
    assert client.get("/api/account/providers").json()[0]["base_url"] == preset["base_url"]


def test_connection_test_sanitizes_upstream_runtime_errors(workspace, monkeypatch):
    import httpx

    from app.infrastructure.agents import probe

    client, _ = workspace
    register(client)
    preset = create_provider(client)

    original = httpx.AsyncClient

    def respond(request):
        return httpx.Response(401, json={"error": {"message": "private-test-key"}})

    class MockClient(original):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(respond))

    monkeypatch.setattr(probe.httpx, "AsyncClient", MockClient)
    response = client.post(f"/api/account/providers/{preset['id']}/test")
    assert response.status_code == 502
    assert "API key 未通过验证" in response.json()["detail"]
    assert "private-test-key" not in response.text


def test_documents_are_ingested_searchable_and_owned(workspace):
    client, _ = workspace
    register(client)
    response = client.post(
        "/api/documents",
        files={
            "upload": (
                "notes.md",
                "视觉 Transformer 的注意力机制与研究笔记".encode(),
                "text/markdown",
            )
        },
    )
    assert response.status_code == 201, response.text
    document = response.json()
    assert document["status"] == "ready"
    hits = client.get("/api/documents/search", params={"q": "注意力"}).json()
    assert hits[0]["document_id"] == document["id"]
    register(client, "other@example.com")
    assert client.get("/api/documents").json() == []
    assert client.get("/api/documents/search", params={"q": "注意力"}).json() == []
    assert client.delete(f"/api/documents/{document['id']}").status_code == 404


def test_provider_deletion_preserves_history_and_research_run(workspace):
    client, engine = workspace
    user, _ = register(client)
    preset = create_provider(client)
    with Session(engine) as session:
        conversation = Conversation(user_id=user["id"], title="History")
        session.add(conversation)
        session.flush()
        session.add(
            ResearchRun(
                id="old-run",
                user_id=user["id"],
                conversation_id=conversation.id,
                provider_id=preset["id"],
                question="What is attention?",
                status="completed",
                mode="deep",
            )
        )
        session.add(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content="Report",
                provider_id=preset["id"],
                provider_name=preset["name"],
                model=preset["model"],
                input_tokens=5,
                output_tokens=7,
                total_tokens=12,
            )
        )
        session.commit()
    assert client.delete(f"/api/account/providers/{preset['id']}").status_code == 204
    usage = client.get("/api/account/usage").json()
    assert usage["lifetime_tokens"] == 12
    assert usage["by_provider"][0]["provider_name"] == preset["name"]
    with Session(engine) as session:
        assert session.get(ResearchRun, "old-run").provider_id is None
        assert session.exec(select(Message)).one().provider_id is None


def test_admin_cannot_remove_own_access(workspace):
    client, engine = workspace
    user, _ = register(client)
    assert client.get("/api/admin/users").status_code == 403
    with Session(engine) as session:
        row = session.get(User, user["id"])
        row.is_admin = True
        session.add(row)
        session.commit()
    for change in ({"is_active": False}, {"is_admin": False}):
        assert client.patch(f"/api/admin/users/{user['id']}", json=change).status_code == 409
    assert client.get("/api/admin/users").status_code == 200


def test_usage_counts_failed_and_cancelled_runs_without_double_counting(workspace):
    client, engine = workspace
    user, _ = register(client)
    preset = create_provider(client)
    with Session(engine) as session:
        conversation = Conversation(user_id=user["id"], title="Usage")
        session.add(conversation)
        session.flush()
        for run_id, status, tokens in (
            ("finished", "completed", 10),
            ("failed", "failed", 7),
            ("stopped", "cancelled", 3),
        ):
            session.add(
                ResearchRun(
                    id=run_id,
                    user_id=user["id"],
                    conversation_id=conversation.id,
                    provider_id=preset["id"],
                    provider_name=preset["name"],
                    model=preset["model"],
                    question="Usage?",
                    status=status,
                    usage={"input_tokens": tokens, "total_tokens": tokens},
                )
            )
        session.add(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                run_id="finished",
                content="A completed report",
                input_tokens=10,
                total_tokens=10,
            )
        )
        session.commit()
    usage = client.get("/api/account/usage").json()
    assert usage["lifetime_tokens"] == 20, usage
    assert usage["by_provider"][0]["provider_name"] == preset["name"]
    assert client.delete(f"/api/account/providers/{preset['id']}").status_code == 204
    assert client.get("/api/account/usage").json()["lifetime_tokens"] == 20


def test_uow_rolls_back_uncommitted_and_failed_writes(workspace):
    _, engine = workspace
    with Session(engine) as session:
        with SqlWorkspaceUow(session) as uow:
            uow.accounts.save(Account(None, "uncommitted@example.com", "hash"))
        assert session.exec(select(User)).all() == []
        with pytest.raises(RuntimeError), SqlWorkspaceUow(session) as uow:
            uow.accounts.save(Account(None, "error@example.com", "hash"))
            raise RuntimeError("abort")
        assert session.exec(select(User)).all() == []


def test_upload_limit_cleans_partial_file(tmp_path):
    async def scenario():
        async def chunks():
            yield b"123"
            yield b"456"

        storage = LocalDocumentStorage(tmp_path, 4)
        with pytest.raises(UploadTooLarge):
            await storage.save(chunks(), 1, ".txt")
        assert list(tmp_path.rglob("*.txt")) == []

    asyncio.run(scenario())


def test_http_research_stream_persists_report_sources_and_activity(workspace, monkeypatch):
    import json

    from pydantic_ai.models.test import TestModel

    from app.infrastructure.agents.research import PydanticResearchRunner

    client, _ = workspace
    register(client)
    preset = create_provider(client)
    document = client.post(
        "/api/documents",
        files={"upload": ("evidence.md", "注意力机制与模型比较证据。".encode(), "text/markdown")},
    ).json()

    def runner(prepared):
        return PydanticResearchRunner(
            prepared,
            models={
                "supervisor": TestModel(
                    call_tools=[],
                    custom_output_args={
                        "steps": [{"title": "核对资料", "task": "Check supplied evidence"}]
                    },
                ),
                "researcher": TestModel(
                    call_tools=[],
                    custom_output_args={
                        "summary": "Evidence supports the comparison",
                        "source_labels": ["Local 1"],
                        "gaps": [],
                    },
                ),
                "reviewer": TestModel(
                    call_tools=[],
                    custom_output_args={"assessment": "Checked", "gaps": [], "conflicts": []},
                ),
                "synthesizer": TestModel(
                    call_tools=[], custom_output_text="# Comparison\n\nEvidence [Local 1]."
                ),
            },
        )

    monkeypatch.setattr("app.api.research.PydanticResearchRunner", runner)
    payload = {
        "question": "比较注意力机制",
        "provider_id": preset["id"],
        "document_ids": [document["id"]],
        "web_search": False,
    }
    response = client.post("/api/research/ask/stream", json=payload)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/event-stream")
    frames = [frame.splitlines() for frame in response.text.split("\n\n") if frame.strip()]
    events = [
        (lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: ")))
        for lines in frames
    ]
    assert {"meta", "plan", "agent", "progress", "content", "done"} <= {e[0] for e in events}
    assert "error" not in {e[0] for e in events}
    done = next(data for name, data in events if name == "done")
    assert done["saved"] is True and done["usage"]["requests"] >= 4
    assert done["sources"][0]["document_id"] == document["id"]
    path = f"/api/research/conversations/{done['conversation_id']}"
    messages = client.get(path).json()
    assert messages[-1]["content"] == "# Comparison\n\nEvidence [Local 1]."
    assert messages[-1]["sources"] == done["sources"]
    assert messages[-1]["events"]
    assert client.get(path + "/runs").json()[0]["status"] == "completed"
    assert client.patch(path, json={"title": "Renamed research"}).status_code == 200
    register(client, "stranger@example.com")
    assert client.get(path).status_code == 404
    assert client.delete(path).status_code == 404
