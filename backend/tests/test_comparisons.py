"""UC08 API, persistence, tenant boundary, and deterministic comparison rules."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.application.service.comparison import _verified_fields
from app.core.db import get_session
from app.domain.comparison import Evidence, build_fields, field_status
from app.main import app
from app.models.comparison import ComparisonRecord
from app.models.conversations import Conversation


@pytest.fixture
def client_db(monkeypatch, tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr("app.main.ensure_admin", lambda: None)
    monkeypatch.setattr("app.core.config.settings.upload_dir", tmp_path / "uploads")

    def sessions():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = sessions
    with TestClient(app) as client:
        yield client, engine
    app.dependency_overrides.clear()
    engine.dispose()


def register(client, email):
    response = client.post(
        "/api/auth/register", json={"email": email, "password": "passphrase-123"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def provider(client):
    response = client.post("/api/account/providers", json={
        "name": "Research", "base_url": "https://models.example.com/v1",
        "model": "comparison-model", "api_key": "placeholder-test-key",
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def upload(client, name, text):
    response = client.post(
        "/api/documents",
        files={"upload": (name, text.encode(), "text/markdown")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "ready"
    return response.json()["id"]


def test_domain_comparison_fails_closed_for_missing_or_untraceable_sources():
    left = Evidence("COCO", "dataset COCO", 1)
    right = Evidence("COCO", "dataset COCO", 2)
    assert field_status(left, right) == "aligned"
    right.value = "ImageNet"
    right.excerpt = "dataset ImageNet"
    assert field_status(left, right) == "mismatch"
    right.excerpt = "unrelated passage"
    assert field_status(left, right) == "unknown"
    fields = build_fields({"dataset": left}, {"dataset": right})
    assert len(fields) == 10
    assert fields[0].status == "unknown"
    assert fields[-1].review_status == "pending"


@pytest.mark.parametrize(
    ("key", "paper_value", "run_value", "expected"),
    [
        pytest.param("value", "40.7", "40.7%", "aligned", id="percent-value-format"),
        pytest.param("value", "40.70", "4.07e1", "aligned", id="equivalent-decimal-values"),
        pytest.param("unit", "percent", "%", "aligned", id="percent-unit-label"),
        pytest.param("value", "0.407", "40.7%", "mismatch", id="no-unit-scale-conversion"),
    ],
)
def test_percent_results_are_normalized_without_converting_scales(
    key, paper_value, run_value, expected,
):
    paper = Evidence(paper_value, f"paper reports {paper_value}", 1)
    run = Evidence(run_value, f"run reports {run_value}", 2)
    assert field_status(paper, run, key) == expected


@pytest.mark.parametrize(
    ("paper_value", "run_value", "expected"),
    [
        pytest.param("validation", "test", "mismatch", id="split-conflict"),
        pytest.param("ResNet-50", "ResNet-101", "mismatch", id="model-conflict"),
        pytest.param("10-crop", "center-crop", "mismatch", id="preprocessing-conflict"),
        pytest.param("top-1 error", "top-1 accuracy", "mismatch", id="metric-conflict"),
        pytest.param("22.85%", "22.40%", "mismatch", id="value-only-difference"),
        pytest.param("ImageNet", None, "unknown", id="missing-run-field"),
    ],
)
def test_field_comparison_scenarios_are_deterministic(paper_value, run_value, expected):
    paper = Evidence(paper_value, f"paper reports {paper_value}", 1)
    run = Evidence(run_value, f"run reports {run_value}", 2) if run_value else Evidence()
    assert field_status(paper, run) == expected


def test_verified_fields_accepts_normalized_pdf_line_wrap_citations():
    source = {
        "chunks": [{
            "id": 17,
            "content": "We report ImageNet-1K top-1 accuracy on the valida-\ntion set.",
        }],
    }
    evidence = Evidence(
        "validation", "top-1 accuracy on the validation set", 17,
    )

    assert _verified_fields(source, {"split": evidence}) == {"split": evidence}


def test_comparison_review_confirmation_and_tenant_isolation(client_db, monkeypatch):
    from app.domain.comparison import Evidence

    client, engine = client_db
    user = register(client, "researcher@example.com")
    selected_provider = provider(client)
    paper = upload(client, "paper.md", "Dataset COCO split val2017 metric mIoU 84.0%.")
    run = upload(client, "run.md", "Dataset COCO split train2017 metric mIoU 81.0%.")
    calls = []

    async def extract(config, source, metric):
        calls.append((config.id, source["id"], metric))
        passage = source["chunks"][0]
        text = passage["content"]
        split = "val2017" if "val2017" in text else "train2017"
        value = "84.0%" if "84.0%" in text else "81.0%"
        return {
            "dataset": Evidence("COCO", text, passage["id"]),
            "split": Evidence(split, text, passage["id"]),
            "metric": Evidence("mIoU", text, passage["id"]),
            "value": Evidence(value, text, passage["id"]),
        }

    monkeypatch.setattr("app.api.comparisons.extract_evidence", extract)
    payload = {
        "paper_document_id": paper, "run_document_id": run,
        "provider_id": selected_provider, "metric": "mIoU",
    }
    assert client.post("/api/research/comparisons", json={**payload, "run_document_id": paper}).status_code == 404
    assert not calls
    response = client.post("/api/research/comparisons", json=payload)
    assert response.status_code == 201, response.text
    created = response.json()
    assert set(calls) == {
        (selected_provider, paper, "mIoU"), (selected_provider, run, "mIoU"),
    }
    assert created["status"] == "pending"
    assert len(created["fields"]) == 10
    fields = {item["key"]: item for item in created["fields"]}
    assert fields["dataset"]["status"] == "aligned"
    assert fields["split"]["status"] == "mismatch"
    assert fields["value"]["status"] == "mismatch"
    assert fields["model"]["status"] == "unknown"
    assert fields["split"]["paper"]["chunk_id"] > 0
    assert client.patch(f"/api/research/comparisons/{created['id']}", json={"confirm": True}).status_code == 409

    updates = []
    for field in created["fields"]:
        updates.append({
            "key": field["key"],
            "paper_value": field["paper"]["value"],
            "run_value": field["run"]["value"],
            "review_status": "unresolved" if field["status"] == "unknown" else "confirmed",
            "note": "",
        })
    saved = client.patch(f"/api/research/comparisons/{created['id']}", json={"updates": updates})
    assert saved.status_code == 200, saved.text
    confirmed = client.patch(f"/api/research/comparisons/{created['id']}", json={"confirm": True})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert client.patch(f"/api/research/comparisons/{created['id']}", json={"confirm": True}).status_code == 409

    with Session(engine) as session:
        row = session.exec(select(ComparisonRecord)).one()
        assert row.user_id == user["id"]
        assert row.fields[0]["review_status"] == "confirmed"

    register(client, "outsider@example.com")
    assert client.get("/api/research/comparisons").json() == []
    assert client.get(f"/api/research/comparisons/{created['id']}").status_code == 404
    assert client.get(
        f"/api/research/comparisons/{created['id']}/source-chunks/paper",
    ).status_code == 404
    assert client.patch(f"/api/research/comparisons/{created['id']}", json={"confirm": True}).status_code == 404
    assert client.post("/api/research/comparisons", json=payload).status_code == 404
    assert len(calls) == 2

    client.post("/api/auth/login", json={
        "email": "researcher@example.com", "password": "passphrase-123",
    })
    assert client.get(f"/api/research/comparisons/{created['id']}").json()["status"] == "confirmed"
    assert len(client.get("/api/research/comparisons").json()) == 1


def test_reviewing_a_value_cannot_override_a_different_metric(client_db, monkeypatch):
    """A saved review must keep the metric/value dependency of the extraction."""
    from app.domain.comparison import Evidence

    client, engine = client_db
    register(client, "metric-review@example.com")
    preset = provider(client)
    paper = upload(client, "paper.md", "Swin-T top-1 accuracy 81.3")
    run = upload(client, "run.md", "Swin-T top-5 accuracy 81.3")

    async def extract(_, source, metric):
        passage = source["chunks"][0]
        text = passage["content"]
        top = "top-1 accuracy" if "top-1" in text else "top-5 accuracy"
        return {
            "model": Evidence("Swin-T", text, passage["id"]),
            "metric": Evidence(top, text, passage["id"]),
            "value": Evidence("81.3", text, passage["id"]),
        }

    monkeypatch.setattr("app.api.comparisons.extract_evidence", extract)
    created = client.post("/api/research/comparisons", json={
        "paper_document_id": paper, "run_document_id": run,
        "provider_id": preset, "metric": "top-1 accuracy",
    }).json()
    fields = {item["key"]: item for item in created["fields"]}
    assert fields["metric"]["status"] == "mismatch"
    assert fields["value"]["status"] == "unknown"

    saved = client.patch(f"/api/research/comparisons/{created['id']}", json={"updates": [{
        "key": "value", "paper_value": "81.3", "run_value": "81.3",
        "review_status": "confirmed", "note": "原文数值已核对",
    }]})
    assert saved.status_code == 200, saved.text
    persisted = {item["key"]: item for item in saved.json()["fields"]}
    assert persisted["metric"]["status"] == "mismatch"
    assert persisted["value"]["status"] == "unknown"

    with Session(engine) as session:
        row = session.exec(select(ComparisonRecord)).one()
        stored = {item["key"]: item for item in row.fields}
        assert stored["value"]["status"] == "unknown"


def test_review_cannot_compare_numbers_without_a_reported_metric(client_db, monkeypatch):
    """No metric on either side means the identical numbers stay unconfirmed."""
    from app.domain.comparison import Evidence

    client, engine = client_db
    register(client, "no-metric@example.com")
    preset = provider(client)
    paper = upload(client, "paper.md", "Swin-T reports 81.3")
    run = upload(client, "run.md", "Swin-T reports 81.3")

    async def extract(_, source, metric):
        passage = source["chunks"][0]
        return {
            "model": Evidence("Swin-T", passage["content"], passage["id"]),
            "value": Evidence("81.3", passage["content"], passage["id"]),
        }

    monkeypatch.setattr("app.api.comparisons.extract_evidence", extract)
    created = client.post("/api/research/comparisons", json={
        "paper_document_id": paper, "run_document_id": run,
        "provider_id": preset, "metric": "top-1 accuracy",
    }).json()
    fields = {item["key"]: item for item in created["fields"]}
    assert fields["metric"]["status"] == "unknown"
    assert fields["value"]["status"] == "unknown"

    saved = client.patch(f"/api/research/comparisons/{created['id']}", json={"updates": [{
        "key": "value", "paper_value": "81.3", "run_value": "81.3",
        "review_status": "confirmed", "note": "两个摘要都写 81.3",
    }]})
    assert saved.status_code == 200, saved.text
    persisted = {item["key"]: item for item in saved.json()["fields"]}
    assert persisted["value"]["status"] == "unknown"

    with Session(engine) as session:
        row = session.exec(select(ComparisonRecord)).one()
        stored = {item["key"]: item for item in row.fields}
        assert stored["value"]["status"] == "unknown"


def test_manual_edit_that_lacks_cited_evidence_stays_unknown(client_db, monkeypatch):
    client, _ = client_db
    register(client, "researcher@example.com")
    preset_id = provider(client)
    paper = upload(client, "paper.md", "COCO accuracy 90")
    run = upload(client, "run.md", "COCO accuracy 90")

    async def extract(_, source, metric):
        chunk = source["chunks"][0]
        return {"dataset": Evidence("COCO", chunk["content"], chunk["id"])}

    monkeypatch.setattr("app.api.comparisons.extract_evidence", extract)
    created = client.post("/api/research/comparisons", json={
        "paper_document_id": paper, "run_document_id": run,
        "provider_id": preset_id, "metric": "accuracy",
    }).json()
    record = client.patch(f"/api/research/comparisons/{created['id']}", json={"updates": [{
        "key": "dataset", "paper_value": "COCO", "run_value": "ImageNet",
        "review_status": "confirmed", "note": "Needs manual source check",
    }]}).json()
    first = record["fields"][0]
    assert first["status"] == "unknown"
    assert first["review_status"] == "confirmed"


def test_reviewer_can_search_selected_source_and_replace_verified_evidence(client_db, monkeypatch):
    client, _ = client_db
    register(client, "reviewer@example.com")
    preset_id = provider(client)
    paper_text = (
        "Table summary: Dataset: ImageNet-22K. "
        "Evaluation dataset: ImageNet-1K."
    )
    run_text = "Dataset: ImageNet-1K. Evaluation split: validation."
    paper = upload(client, "paper.md", paper_text)
    run = upload(client, "run.md", run_text)

    async def extract(_, source, metric):
        chunk = source["chunks"][0]
        if source["id"] == paper:
            return {"dataset": Evidence("ImageNet-22K", "Dataset: ImageNet-22K", chunk["id"])}
        return {"dataset": Evidence("ImageNet-1K", "Dataset: ImageNet-1K", chunk["id"])}

    monkeypatch.setattr("app.api.comparisons.extract_evidence", extract)
    created_response = client.post("/api/research/comparisons", json={
        "paper_document_id": paper,
        "run_document_id": run,
        "provider_id": preset_id,
        "metric": "top-1 accuracy",
    })
    assert created_response.status_code == 201, created_response.text
    created = created_response.json()
    field = next(row for row in created["fields"] if row["key"] == "dataset")
    assert field["status"] == "mismatch"

    paper_search = client.get(
        f"/api/research/comparisons/{created['id']}/source-chunks/paper?q=Evaluation%20dataset",
    )
    assert paper_search.status_code == 200, paper_search.text
    paper_chunks = paper_search.json()
    assert len(paper_chunks) == 1
    paper_chunk = paper_chunks[0]
    assert "Evaluation dataset: ImageNet-1K" in paper_chunk["content"]
    assert "validation" not in paper_chunk["content"]
    assert client.get(
        f"/api/research/comparisons/{created['id']}/source-chunks/paper?q=RunOnlyMarker",
    ).json() == []

    run_chunks = client.get(
        f"/api/research/comparisons/{created['id']}/source-chunks/run?q=Dataset",
    ).json()
    run_chunk = run_chunks[0]
    updated = client.patch(f"/api/research/comparisons/{created['id']}", json={"updates": [{
        "key": "dataset",
        "paper_value": "ImageNet-1K",
        "run_value": "ImageNet-1K",
        "paper_source": {
            "excerpt": "Evaluation dataset: ImageNet-1K",
            "chunk_id": paper_chunk["chunk_id"],
        },
        "run_source": {
            "excerpt": "Dataset: ImageNet-1K",
            "chunk_id": run_chunk["chunk_id"],
        },
        "review_status": "confirmed",
        "note": "人工核对所选论文行。",
    }]})
    assert updated.status_code == 200, updated.text
    corrected = next(row for row in updated.json()["fields"] if row["key"] == "dataset")
    assert corrected["status"] == "aligned"
    assert corrected["review_status"] == "confirmed"
    assert corrected["paper"]["excerpt"] == "Evaluation dataset: ImageNet-1K"

    invalid_excerpt = client.patch(f"/api/research/comparisons/{created['id']}", json={"updates": [{
        "key": "dataset",
        "paper_value": "ImageNet-1K",
        "run_value": "ImageNet-1K",
        "paper_source": {
            "excerpt": "This text is not in the paper",
            "chunk_id": paper_chunk["chunk_id"],
        },
        "run_source": {
            "excerpt": "Dataset: ImageNet-1K",
            "chunk_id": run_chunk["chunk_id"],
        },
        "review_status": "confirmed",
        "note": "",
    }]})
    assert invalid_excerpt.status_code == 422

    invalid = client.patch(f"/api/research/comparisons/{created['id']}", json={"updates": [{
        "key": "dataset",
        "paper_value": "ImageNet-1K",
        "run_value": "ImageNet-1K",
        "paper_source": {
            "excerpt": "Dataset: ImageNet-1K",
            "chunk_id": run_chunk["chunk_id"],
        },
        "run_source": {
            "excerpt": "Dataset: ImageNet-1K",
            "chunk_id": run_chunk["chunk_id"],
        },
        "review_status": "confirmed",
        "note": "",
    }]})
    assert invalid.status_code == 422
    preserved = client.get(f"/api/research/comparisons/{created['id']}").json()
    corrected_after_rejection = next(
        row for row in preserved["fields"] if row["key"] == "dataset"
    )
    assert corrected_after_rejection["paper"]["excerpt"] == "Evaluation dataset: ImageNet-1K"


@pytest.mark.parametrize("invalid_reference", ["excerpt", "chunk_id"])
def test_extraction_must_refer_to_the_selected_chunk(client_db, monkeypatch, invalid_reference):
    client, _ = client_db
    register(client, "researcher@example.com")
    preset_id = provider(client)
    paper = upload(client, "paper.md", "COCO accuracy 90")
    run = upload(client, "run.md", "COCO accuracy 90")

    async def extract(_, source, metric):
        chunk = source["chunks"][0]
        if source["id"] == paper and invalid_reference == "excerpt":
            return {"dataset": Evidence("COCO", "COCO from a different document", chunk["id"])}
        chunk_id = chunk["id"] + 999 if source["id"] == paper else chunk["id"]
        return {"dataset": Evidence("COCO", chunk["content"], chunk_id)}

    monkeypatch.setattr("app.api.comparisons.extract_evidence", extract)
    response = client.post("/api/research/comparisons", json={
        "paper_document_id": paper, "run_document_id": run,
        "provider_id": preset_id, "metric": "accuracy",
    })
    assert response.status_code == 201, response.text
    item = response.json()["fields"][0]
    assert item["status"] == "unknown"
    assert item["paper"]["value"] is None
    assert item["run"]["value"] == "COCO"


def test_upstream_error_does_not_save_a_candidate(client_db, monkeypatch):
    from app.infrastructure.agents.comparison import EvidenceExtractionError

    client, engine = client_db
    register(client, "researcher@example.com")
    preset_id = provider(client)
    paper = upload(client, "paper.md", "COCO accuracy 90")
    run = upload(client, "run.md", "COCO accuracy 90")

    async def fail(_, source, metric):
        raise EvidenceExtractionError("模型服务暂时不可用")

    monkeypatch.setattr("app.api.comparisons.extract_evidence", fail)
    response = client.post("/api/research/comparisons", json={
        "paper_document_id": paper, "run_document_id": run,
        "provider_id": preset_id, "metric": "accuracy",
    })
    assert response.status_code == 502
    assert "读取失败" in response.json()["detail"]
    assert client.get("/api/research/comparisons").json() == []
    with Session(engine) as session:
        assert session.exec(select(ComparisonRecord)).all() == []


def test_run_side_failure_is_identified_without_persisting_a_partial_record(
    client_db, monkeypatch,
):
    from app.domain.comparison import EvidenceExtractionError

    client, engine = client_db
    register(client, "reader@example.com")
    preset_id = provider(client)
    paper = upload(client, "paper.md", "paper data ImageNet")
    run = upload(client, "run.md", "run data ImageNet")

    async def extract(_, source, metric):
        if source["id"] == run:
            raise EvidenceExtractionError("模型响应格式有误")
        chunk = source["chunks"][0]
        return {"dataset": Evidence("ImageNet", chunk["content"], chunk["id"])}

    monkeypatch.setattr("app.api.comparisons.extract_evidence", extract)
    response = client.post("/api/research/comparisons", json={
        "paper_document_id": paper, "run_document_id": run,
        "provider_id": preset_id, "metric": "accuracy",
    })
    assert response.status_code == 502, response.text
    assert response.json()["detail"].startswith("运行摘要读取失败：")
    assert client.get("/api/research/comparisons").json() == []
    with Session(engine) as session:
        assert session.exec(select(ComparisonRecord)).all() == []


def test_malformed_structured_output_does_not_save_a_candidate(client_db, monkeypatch):
    import json

    import httpx

    from app.infrastructure.agents import comparison

    client, engine = client_db
    register(client, "researcher@example.com")
    response = client.post("/api/account/providers", json={
        "name": "Malformed response test",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-flash",
        "api_key": "placeholder-test-key",
        "provider_type": "deepseek",
    })
    assert response.status_code == 201, response.text
    preset_id = response.json()["id"]
    paper = upload(client, "paper.md", "COCO top-1 error 40.7%")
    run = upload(client, "run.md", "COCO top-1 error 40.7%")
    requests = []
    original_client = httpx.AsyncClient

    def respond(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "resp_malformed_comparison",
            "object": "response",
            "created_at": 1,
            "model": "deepseek-flash",
            "status": "completed",
            "output": [{
                "id": "msg_malformed",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": "{", "annotations": []}],
            }],
        })

    class MockClient(original_client):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(respond))

    monkeypatch.setattr(comparison.httpx, "AsyncClient", MockClient)
    result = client.post("/api/research/comparisons", json={
        "paper_document_id": paper,
        "run_document_id": run,
        "provider_id": preset_id,
        "metric": "top-1 error",
    })
    assert result.status_code == 502, result.text
    assert "读取失败" in result.json()["detail"]
    # Both sources start; one can be cancelled before using its single retry.
    assert 2 <= len(requests) <= 4
    assert client.get("/api/research/comparisons").json() == []
    with Session(engine) as session:
        assert session.exec(select(ComparisonRecord)).all() == []


def test_pair_deadline_returns_gateway_timeout_without_saving(client_db, monkeypatch):
    import asyncio

    client, engine = client_db
    register(client, "researcher@example.com")
    preset_id = provider(client)
    paper = upload(client, "paper.md", "COCO top-1 error 40.7%")
    run = upload(client, "run.md", "COCO top-1 error 40.7%")
    calls = []
    cancelled = []

    async def slow_extract(_, source, metric):
        calls.append(source["id"])
        try:
            await asyncio.sleep(0.1)
            return {}
        finally:
            cancelled.append(source["id"])

    monkeypatch.setattr(
        "app.application.service.comparison.COMPARISON_EXTRACTION_TIMEOUT_SECONDS", 0.01,
    )
    monkeypatch.setattr("app.api.comparisons.extract_evidence", slow_extract)
    response = client.post("/api/research/comparisons", json={
        "paper_document_id": paper,
        "run_document_id": run,
        "provider_id": preset_id,
        "metric": "top-1 error",
    })
    assert response.status_code == 504, response.text
    assert set(calls) == {paper, run}
    assert set(cancelled) == {paper, run}
    assert client.get("/api/research/comparisons").json() == []
    with Session(engine) as session:
        assert session.exec(select(ComparisonRecord)).all() == []


def test_pair_extraction_runs_both_sources_within_one_deadline(client_db, monkeypatch):
    import asyncio

    client, _ = client_db
    register(client, "researcher@example.com")
    preset_id = provider(client)
    paper = upload(client, "paper.md", "COCO top-1 error 40.7%")
    run = upload(client, "run.md", "COCO top-1 error 40.7%")
    calls = []
    both_started = asyncio.Event()

    async def wait_for_pair(_, source, metric):
        calls.append(source["id"])
        if len(calls) == 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), timeout=0.2)
        return {}

    monkeypatch.setattr(
        "app.application.service.comparison.COMPARISON_EXTRACTION_TIMEOUT_SECONDS", 0.5,
    )
    monkeypatch.setattr("app.api.comparisons.extract_evidence", wait_for_pair)
    response = client.post("/api/research/comparisons", json={
        "paper_document_id": paper,
        "run_document_id": run,
        "provider_id": preset_id,
        "metric": "top-1 error",
    })
    assert response.status_code == 201, response.text
    assert set(calls) == {paper, run}


def test_disconnect_monitor_cancels_pending_operation():
    import asyncio

    from app.api.comparisons import _cancel_on_disconnect

    class DisconnectedRequest:
        async def is_disconnected(self):
            return True

    async def check():
        operation = asyncio.create_task(asyncio.Event().wait())
        await _cancel_on_disconnect(DisconnectedRequest(), operation)
        with pytest.raises(asyncio.CancelledError):
            await operation

    asyncio.run(check())


def test_api_disconnect_cancels_extraction_and_persists_nothing(client_db, monkeypatch):
    import asyncio

    from app.api.comparisons import create_comparison
    from app.domain.workspace import Account
    from app.schemas.comparison import ComparisonCreate

    client, engine = client_db
    user = register(client, "researcher@example.com")
    preset_id = provider(client)
    paper = upload(client, "paper.md", "COCO top-1 error 40.7%")
    run = upload(client, "run.md", "COCO top-1 error 40.7%")
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def wait_for_disconnect(*_):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    class DisconnectedRequest:
        async def is_disconnected(self):
            return True

    monkeypatch.setattr("app.api.comparisons.extract_evidence", wait_for_disconnect)

    async def invoke():
        with Session(engine) as session, pytest.raises(asyncio.CancelledError):
            await create_comparison(
                DisconnectedRequest(),
                ComparisonCreate(
                    paper_document_id=paper,
                    run_document_id=run,
                    provider_id=preset_id,
                    metric="top-1 error",
                ),
                Account(user["id"], "researcher@example.com", "test-only"),
                session,
            )
        assert started.is_set()
        assert cancelled.is_set()

    asyncio.run(invoke())
    with Session(engine) as session:
        assert session.exec(select(ComparisonRecord)).all() == []


def test_deepseek_extractor_uses_prompted_json_responses_and_fails_closed(monkeypatch):
    import asyncio
    import json

    import httpx

    from app.domain.research import ProviderConfig
    from app.infrastructure.agents import comparison

    requests = []
    original_client = httpx.AsyncClient

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert request.url.path.endswith("/responses")
        assert payload["text"]["format"]["type"] == "json_object"
        assert payload.get("tools", []) == []
        assert payload["store"] is False
        assert payload["reasoning"] == {"effort": "none"}
        answer = {
            "fields": [{
                "key": "split", "value": "test2017",
                "excerpt": "Test2017 does not appear in the source",
                "chunk_id": 13,
            }],
        }
        return httpx.Response(200, json={
            "id": "resp_comparison_1",
            "object": "response",
            "created_at": 1,
            "model": "deepseek-flash",
            "status": "completed",
            "output": [{
                "id": "msg_extraction",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{
                    "type": "output_text",
                    "text": json.dumps(answer),
                    "annotations": [],
                }],
            }],
            "usage": {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20},
        })

    class MockClient(original_client):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(respond))

    monkeypatch.setattr(comparison.httpx, "AsyncClient", MockClient)
    result = asyncio.run(comparison.extract_evidence(
        ProviderConfig(
            1, "Test", "https://api.deepseek.com", "deepseek-flash",
            "placeholder-key", "deepseek",
        ),
        {
            "id": 1,
            "filename": "paper.md",
            "chunks": [{
                "id": 13, "ordinal": 0,
                "content": (
                    "Classi\ufb01cation accuracy on ImageNet-1K. "
                    "IN-1K\n top-1 acc. We report ImageNet-1K top-1 accuracy "
                    "on the valida-\ntion set. ImageNet-22K pre-trained models."
                ),
            }],
        },
        "top-1 accuracy (ConvNeXt-T, Table 1, ImageNet-22K pre-trained row, "
        "evaluated on ImageNet-1K at 224x224)",
    ))
    # The only candidate could not be matched to real source text, and without a
    # cited row no condition may be imported from elsewhere in the document.
    assert result == {}
    assert len(requests) == 1


def test_extractor_propagates_cancellation_and_closes_request(client_db, monkeypatch):
    import asyncio

    import httpx

    from app.domain.research import ProviderConfig
    from app.infrastructure.agents import comparison

    started = asyncio.Event()
    transport_cancelled = asyncio.Event()
    original_client = httpx.AsyncClient

    async def wait_for_cancellation(request):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            transport_cancelled.set()

    class MockClient(original_client):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(wait_for_cancellation))

    monkeypatch.setattr(comparison.httpx, "AsyncClient", MockClient)
    provider_config = ProviderConfig(
        1, "Test", "https://models.example.com/v1", "model", "placeholder-test-key", "custom",
    )
    document = {
        "id": 1,
        "filename": "paper.md",
        "chunks": [{"id": 13, "ordinal": 0, "content": "Dataset COCO"}],
    }

    async def cancel_request():
        task = asyncio.create_task(comparison.extract_evidence(provider_config, document, "mIoU"))
        await asyncio.wait_for(started.wait(), timeout=2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert transport_cancelled.is_set()

    asyncio.run(cancel_request())


def test_comparison_evidence_view_is_limited_to_owned_source_chunks(client_db):
    from app.models.documents import DocumentChunk

    client, engine = client_db
    owner = register(client, "reader@example.com")
    paper_id = upload(client, "paper.md", "Dataset ImageNet, metric top-1 error 22.85%.")
    run_id = upload(client, "run.md", "Dataset ImageNet, metric top-1 error 24.10%.")
    with Session(engine) as session:
        paper_chunk = session.exec(
            select(DocumentChunk).where(DocumentChunk.document_id == paper_id)
        ).first()
        run_chunk = session.exec(
            select(DocumentChunk).where(DocumentChunk.document_id == run_id)
        ).first()
        conversation = Conversation(user_id=owner["id"], title="实验核验")
        session.add(conversation)
        session.flush()
        record = ComparisonRecord(
            conversation_id=conversation.id,
            user_id=owner["id"], paper_document_id=paper_id, run_document_id=run_id,
            paper_name="paper.md", run_name="run.md", metric="top-1 error",
            provider_id=None, fields=[{
                "key": "value", "label": "指标数值",
                "paper": {"value": "22.85%", "excerpt": "top-1 error 22.85%", "chunk_id": paper_chunk.id},
                "run": {"value": "24.10%", "excerpt": "top-1 error 24.10%", "chunk_id": run_chunk.id},
                "status": "mismatch", "review_status": "pending", "note": "",
            }],
        )
        session.add(record)
        session.commit()
        record_id = record.id
        chunk_id = paper_chunk.id

    response = client.get(f"/api/research/comparisons/{record_id}/evidence/paper/value")
    assert response.status_code == 200, response.text
    assert response.json()["filename"] == "paper.md"
    assert "22.85%" in response.json()["content"]
    assert response.json()["chunk_id"] == chunk_id
    assert response.json()["page_number"] is None
    assert client.get(f"/api/research/comparisons/{record_id}/evidence/run/value").status_code == 200
    assert client.get(f"/api/research/comparisons/{record_id}/evidence/other/value").status_code == 404
    assert client.get(f"/api/research/comparisons/{record_id}/evidence/paper/model").status_code == 404

    register(client, "other-reader@example.com")
    assert client.get(f"/api/research/comparisons/{record_id}/evidence/paper/value").status_code == 404
    assert client.get(f"/api/research/comparisons/{record_id}/evidence/run/value").status_code == 404

    client.post("/api/auth/login", json={
        "email": "reader@example.com", "password": "passphrase-123",
    })
    client.delete(f"/api/documents/{paper_id}")
    assert client.get(f"/api/research/comparisons/{record_id}/evidence/paper/value").status_code == 404
    assert client.get(f"/api/research/comparisons/{record_id}").json()["fields"][0]["paper"]["excerpt"]


def test_experiment_checks_share_research_history_and_resource_lifecycle(client_db, monkeypatch):
    client, engine = client_db
    register(client, "unified@example.com")
    selected_provider = provider(client)
    paper = upload(client, "paper.md", "Dataset COCO metric mIoU 84%")
    run = upload(client, "run.md", "Dataset COCO metric mIoU 81%")

    async def extract(_config, source, _metric):
        chunk = source["chunks"][0]
        return {"dataset": Evidence("COCO", chunk["content"], chunk["id"])}

    monkeypatch.setattr("app.api.comparisons.extract_evidence", extract)
    response = client.post("/api/research/comparisons", json={
        "paper_document_id": paper, "run_document_id": run,
        "provider_id": selected_provider, "metric": "mIoU",
    })
    assert response.status_code == 201, response.text
    record = response.json()
    conversation_id = record["conversation_id"]
    history = client.get("/api/research/conversations").json()
    assert len(history) == 1
    assert history[0]["kind"] == "comparison"
    assert history[0]["comparison_id"] == record["id"]
    assert history[0]["id"] == conversation_id
    assert client.get("/api/research/comparisons").json()[0]["conversation_id"] == conversation_id
    # Previously saved clients can still read the same record without creating a duplicate.
    assert client.get(f"/api/comparisons/{record['id']}").json() == client.get(
        f"/api/research/comparisons/{record['id']}"
    ).json()
    assert client.get("/api/comparisons").json() == client.get("/api/research/comparisons").json()
    renamed = client.patch(f"/api/research/conversations/{conversation_id}", json={
        "title": "复查分割模型结果",
    }).json()
    assert renamed["kind"] == "comparison"
    assert renamed["comparison_id"] == record["id"]
    assert renamed["title"] == "复查分割模型结果"
    # A check cannot accidentally be used as an ordinary question-answer conversation.
    assert client.post("/api/research/ask/stream", json={
        "question": "继续研究这个问题", "provider_id": selected_provider,
        "conversation_id": conversation_id,
    }).status_code == 422
    register(client, "other-unified@example.com")
    assert client.get("/api/research/conversations").json() == []
    assert client.delete(f"/api/research/conversations/{conversation_id}").status_code == 404
    assert client.patch(f"/api/research/conversations/{conversation_id}", json={
        "title": "不能改别人的记录",
    }).status_code == 404
    assert client.get(f"/api/research/comparisons/{record['id']}").status_code == 404
    client.post("/api/auth/login", json={
        "email": "unified@example.com", "password": "passphrase-123",
    })
    assert client.delete(f"/api/research/conversations/{conversation_id}").status_code == 204
    assert client.get(f"/api/research/comparisons/{record['id']}").status_code == 404
    assert len(client.get("/api/documents").json()) == 2
    with Session(engine) as session:
        assert not session.exec(select(ComparisonRecord)).all()
        assert not session.exec(select(Conversation)).all()


def test_comparison_and_history_are_rolled_back_together(client_db, monkeypatch):
    from app.infrastructure.repo.comparison import SqlComparisonRepository

    client, engine = client_db
    register(client, "rollback-unified@example.com")
    selected_provider = provider(client)
    paper = upload(client, "paper.md", "Dataset COCO")
    run = upload(client, "run.md", "Dataset COCO")

    async def extract(_config, _source, _metric):
        return {}

    original_create = SqlComparisonRepository.create

    def fail_after_insert(self, *args):
        original_create(self, *args)
        raise RuntimeError("Simulated persistence failure")

    monkeypatch.setattr("app.api.comparisons.extract_evidence", extract)
    monkeypatch.setattr(SqlComparisonRepository, "create", fail_after_insert)
    with pytest.raises(RuntimeError, match="Simulated persistence failure"):
        client.post("/api/research/comparisons", json={
            "paper_document_id": paper, "run_document_id": run,
            "provider_id": selected_provider, "metric": "mIoU",
        })
    with Session(engine) as session:
        assert not session.exec(select(ComparisonRecord)).all()
        assert not session.exec(select(Conversation)).all()


def test_openapi_documents_only_the_integrated_research_endpoints():
    paths = app.openapi()["paths"]
    assert "/api/research/comparisons" in paths
    assert "/api/research/comparisons/{comparison_id}/source-chunks/{side}" in paths
    assert not any(path.startswith("/api/comparisons") for path in paths)
