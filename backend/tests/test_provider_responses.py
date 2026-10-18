"""Exercise the real Responses SDK against deterministic, local HTTP transports."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.core.crypto import encrypt_secret
from app.domain.workspace import ModelPreset
from app.infrastructure.agents import catalog, probe
from app.infrastructure.agents.errors import provider_error_message
from app.infrastructure.agents.research import ResearchPlan
from app.infrastructure.agents.settings import responses_settings


def test_responses_uses_medium_thinking_and_returns_structured_plan():
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert request.url.path == "/responses"
        assert payload["reasoning"]["effort"] == "medium"
        assert payload["store"] is False
        return httpx.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 1,
                "model": "deepseek-flash",
                "status": "completed",
                "output": [
                    {
                        "id": "fc_test",
                        "type": "function_call",
                        "call_id": "call_test",
                        "name": payload["tools"][0]["name"],
                        "arguments": json.dumps({"steps": [{"title": "查证", "task": "核查证据"}]}),
                        "status": "completed",
                    }
                ],
                "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
            },
        )

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = AsyncOpenAI(
                base_url="https://api.deepseek.com",
                api_key="test-key",
                http_client=http,
                max_retries=0,
            )
            agent = Agent(
                OpenAIResponsesModel(
                    "deepseek-flash", provider=OpenAIProvider(openai_client=client)
                ),
                output_type=ResearchPlan,
                model_settings=responses_settings(),
            )
            result = await agent.run("制定研究计划")
            assert result.output.steps[0].title == "查证"

    asyncio.run(scenario())
    assert len(requests) == 1
    assert responses_settings()["openai_reasoning_effort"] == "medium"


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 429, 500])
def test_probe_does_not_leak_sdk_runtime_exception_bodies(monkeypatch, status):
    original = httpx.AsyncClient

    def respond(request):
        return httpx.Response(status, json={"error": {"message": "PRIVATE_KEY_AND_PROMPT"}})

    class MockClient(original):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(respond))

    monkeypatch.setattr(probe.httpx, "AsyncClient", MockClient)
    preset = ModelPreset(
        None,
        1,
        "DeepSeek",
        "https://api.deepseek.com",
        "deepseek-flash",
        encrypt_secret("test-key"),
        provider_type="deepseek",
    )
    with pytest.raises(RuntimeError) as failure:
        asyncio.run(probe.probe_provider(preset))
    assert "PRIVATE_KEY_AND_PROMPT" not in str(failure.value)
    assert str(failure.value) == provider_error_message(ModelHTTPError(status, "deepseek-flash"))


@pytest.mark.parametrize(
    "body", [{"data": [{"id": "z"}, {"id": "a"}, {"id": "z"}]}, {"data": []}, {"bad": "payload"}]
)
def test_models_api_validation_and_authentication(monkeypatch, body):
    original = httpx.AsyncClient

    def respond(request):
        assert request.method == "GET"
        assert request.url.path == "/models"
        assert request.headers["Authorization"] == "Bearer test-key"
        return httpx.Response(200, json=body)

    monkeypatch.setattr(
        catalog.httpx,
        "AsyncClient",
        lambda **kwargs: original(
            **kwargs,
            transport=httpx.MockTransport(respond),
        ),
    )
    if body.get("data"):
        assert asyncio.run(catalog.discover_models("https://api.deepseek.com", "test-key")) == [
            "a",
            "z",
        ]
    else:
        with pytest.raises(RuntimeError):
            asyncio.run(catalog.discover_models("https://api.deepseek.com", "test-key"))
