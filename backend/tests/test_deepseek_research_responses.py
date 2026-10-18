"""Exercise DeepSeek research through the real SDK, including the tool-return turn."""

import asyncio
import json

import httpx
import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior

from app.domain.research import PreparedResearch, ProviderConfig, ResearchCommand
from app.infrastructure.agents import research


def response(output, index):
    return {
        "id": f"resp_{index}",
        "object": "response",
        "created_at": 1,
        "model": "deepseek-flash",
        "status": "completed",
        "output": output,
        "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
    }


def function(name, arguments, index):
    return {
        "id": f"fc_{index}",
        "type": "function_call",
        "call_id": f"call_{index}",
        "name": name,
        "arguments": json.dumps(arguments),
        "status": "completed",
    }


def reasoning(index):
    return {
        "id": f"rs_{index}",
        "type": "reasoning",
        "summary": [],
        "content": [{"type": "reasoning_text", "text": "PRIVATE_REASONING"}],
    }


def text(message):
    return {
        "id": "msg_report",
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": message, "annotations": []}],
    }


def stream_response(message, index):
    item = text(message)
    events = [
        {"type": "response.created", "response": response([], index)},
        {
            "type": "response.output_item.added",
            "output_index": 0,
            "item": {**item, "status": "in_progress", "content": []},
        },
        {
            "type": "response.content_part.added",
            "item_id": item["id"],
            "output_index": 0,
            "content_index": 0,
            "part": {"type": "output_text", "text": "", "annotations": []},
        },
        {
            "type": "response.output_text.delta",
            "item_id": item["id"],
            "output_index": 0,
            "content_index": 0,
            "delta": message,
        },
        {"type": "response.completed", "response": response([item], index)},
    ]
    return httpx.Response(
        200,
        headers={"content-type": "text/event-stream"},
        text="".join(
            f"event: {event['type']}\ndata: {json.dumps({**event, 'sequence_number': number})}\n\n"
            for number, event in enumerate(events)
        ),
    )


@pytest.mark.parametrize(
    ("provider_type", "base_url", "expected_choice"),
    [
        ("deepseek", "https://api.deepseek.com", "auto"),
        ("custom", "https://api.deepseek.com/v1", "auto"),  # Existing saved presets.
        ("deepseek", "https://gateway.example.com/v1", "auto"),
        ("openai", "https://api.openai.com/v1", "required"),
    ],
)
@pytest.mark.parametrize("web", [False, True])
@pytest.mark.parametrize("researcher_tool", ["search_web", "delegate_research"])
def test_research_sdk_contract_and_tool_history(
    monkeypatch, provider_type, base_url, expected_choice, web, researcher_tool
):
    original_client = httpx.AsyncClient
    requests = []
    tool_requested = False

    def respond(request):
        nonlocal tool_requested
        payload = json.loads(request.content)
        requests.append(payload)
        assert request.url.path.endswith("/responses")
        assert payload["reasoning"] == {"effort": "medium"}
        assert payload["store"] is False
        assert not any(tool["type"] == "web_search" for tool in payload.get("tools", []))
        if payload["stream"]:
            return stream_response(
                "Research report [Web 1]." if web else "Research report.", len(requests)
            )
        # Simulate rejection of the suspected forced-tool / thinking combination.
        if expected_choice == "auto" and payload.get("tool_choice") not in (None, "auto"):
            return httpx.Response(
                400, json={"error": {"message": "tool_choice required with thinking"}}
            )
        if expected_choice == "auto":
            output_format = payload["text"]["format"]
            assert output_format["type"] == "json_schema"
            assert output_format["strict"] is False
            assert not any(tool["name"] == "final_result" for tool in payload.get("tools", []))
            properties = output_format["schema"]["properties"]
            if payload.get("tools"):
                assert payload["tool_choice"] == "auto"
            else:
                assert "tool_choice" not in payload
        else:
            assert payload["tool_choice"] == expected_choice
            output_tool = next(tool for tool in payload["tools"] if tool["name"] == "final_result")
            properties = output_tool["parameters"]["properties"]
        index = len(requests)
        if "steps" in properties:
            arguments = {"steps": [{"title": "核查", "task": "Check the evidence"}]}
        elif "summary" in properties:
            if not tool_requested:
                tool_requested = True
                arguments = (
                    {"query": "Evidence"}
                    if researcher_tool == "search_web"
                    else {"task": "Check a focused subquestion"}
                )
                return httpx.Response(
                    200,
                    json=response(
                        [reasoning(index), function(researcher_tool, arguments, index)],
                        index,
                    ),
                )
            # Thinking stays in the run-scoped tool history, never in public events.
            calls = [item for item in payload["input"] if item.get("type") == "function_call"]
            results = [
                item for item in payload["input"] if item.get("type") == "function_call_output"
            ]
            if calls:  # A child starts a fresh context; its parent resumes the tool.
                assert calls[0]["call_id"] == results[0]["call_id"]
                assert any(
                    item.get("type") == "reasoning" and item.get("content")
                    for item in payload["input"]
                )
            arguments = {
                "summary": "Checked",
                "source_labels": ["Web 1"] if web else [],
                "gaps": [],
            }
        else:
            assert "assessment" in properties
            arguments = {"assessment": "Evidence checked", "gaps": [], "conflicts": []}
        output = (
            [text(json.dumps(arguments))]
            if expected_choice == "auto"
            else [function(output_tool["name"], arguments, index)]
        )
        return httpx.Response(200, json=response(output, index))

    class MockClient(original_client):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(respond))

    monkeypatch.setattr(research.httpx, "AsyncClient", MockClient)

    async def search(query, limit):
        return [{"title": "Evidence", "url": "https://example.com/evidence", "snippet": "Fact"}]

    prepared = PreparedResearch(
        "deepseek-contract",
        1,
        1,
        ResearchCommand("你好", max_agents=2, max_depth=1, web_search=web),
        ProviderConfig(1, "dp", base_url, "deepseek-flash", "test-key", provider_type),
        (),
        (),
    )
    runner = research.PydanticResearchRunner(prepared, search=search)

    async def run():
        return [event async for event in runner.stream()]

    events = asyncio.run(run())
    assert events[-1].data["stage"] == "completed"
    assert "Research report" in runner.result.content
    expected_requests = 6 if researcher_tool == "delegate_research" else 5
    assert runner.result.usage["requests"] == len(requests) == expected_requests
    assert runner.result.usage["total_tokens"] == 30 * expected_requests
    assert tool_requested
    assert "PRIVATE_REASONING" not in json.dumps(runner.result.events)
    assert "PRIVATE_REASONING" not in runner.result.content
    expected_agents = {
        "supervisor",
        "researcher-1",
        "reviewer",
        "synthesizer",
    }
    if researcher_tool == "delegate_research":
        expected_agents.add("researcher-2")
    assert {event.data["id"] for event in events if event.type == "agent"} == expected_agents


@pytest.mark.parametrize(
    ("role", "invalid", "valid"),
    [
        ("supervisor", {"steps": []}, {"steps": [{"title": "核查", "task": "Check evidence"}]}),
        (
            "researcher",
            {"summary": "Checked", "source_labels": ["Web 999"]},
            {"summary": "Checked", "source_labels": [], "gaps": []},
        ),
        ("reviewer", {"gaps": []}, {"assessment": "Checked", "gaps": [], "conflicts": []}),
    ],
)
@pytest.mark.parametrize("always_invalid", [False, True])
def test_native_output_keeps_validation_and_bounded_retries(
    monkeypatch, role, invalid, valid, always_invalid
):
    original_client = httpx.AsyncClient
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert payload["text"]["format"]["type"] == "json_schema"
        assert payload.get("tool_choice") in (None, "auto")
        arguments = invalid if len(requests) == 1 or always_invalid else valid
        return httpx.Response(200, json=response([text(json.dumps(arguments))], len(requests)))

    class MockClient(original_client):
        def __init__(self, **kwargs):
            super().__init__(**kwargs, transport=httpx.MockTransport(respond))

    monkeypatch.setattr(research.httpx, "AsyncClient", MockClient)
    prepared = PreparedResearch(
        "deepseek-validation",
        1,
        1,
        ResearchCommand("核查证据"),
        ProviderConfig(
            1, "dp", "https://api.deepseek.com", "deepseek-flash", "test-key", "deepseek"
        ),
        (),
        (),
    )
    runner = research.PydanticResearchRunner(prepared)

    async def run():
        runner._build_agents()
        try:
            result = await runner._agents[role].run(
                "Research the evidence",
                deps=research.ResearcherDeps(runner, "researcher-1", 0),
                usage=runner.usage,
                usage_limits=runner._usage_limits,
            )
            assert result.output.model_dump() == valid
        finally:
            await runner._client.close()

    if always_invalid:
        with pytest.raises(UnexpectedModelBehavior):
            asyncio.run(run())
    else:
        asyncio.run(run())
    assert len(requests) == runner.budget.requests == 2
