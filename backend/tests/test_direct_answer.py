"""Verify quick chat uses one real SDK request, without a research team."""

import asyncio
import json

import httpx
import pytest
from openai import AsyncOpenAI

from app.domain.research import (
    HistoryMessage,
    PreparedResearch,
    ProviderConfig,
    ResearchCommand,
    ResearchError,
)
from app.infrastructure.agents.answer import DirectAnswerRunner
from app.infrastructure.search.web import WebSearchError


def prepared(*, provider="openai", web=False, local=False):
    return PreparedResearch(
        run_id="quick-run",
        conversation_id=1,
        user_id=1,
        command=ResearchCommand("你好，请回答这个问题", mode="quick", web_search=web),
        provider=ProviderConfig(
            1,
            provider,
            "https://api.deepseek.com" if provider == "deepseek" else "https://api.openai.com/v1",
            "deepseek-flash" if provider == "deepseek" else "model",
            "private-test-key",
            provider,
        ),
        history=(
            HistoryMessage("user", "Earlier question"),
            HistoryMessage("assistant", "Earlier answer"),
        ),
        local_chunks=({"filename": "notes.txt", "document_id": 7, "content": "Local evidence"},)
        if local
        else (),
    )


def frames(*, answer="你好！", native=False, terminal="completed", omit_sources=False):
    annotation = {
        "type": "url_citation",
        "title": "官方来源",
        "url": "https://example.com/source",
        "start_index": 0,
        "end_index": len(answer),
    }
    events = [{"type": "response.reasoning_text.delta", "delta": "PRIVATE_THINKING"}]
    if native:
        events.append(
            {
                "type": "response.web_search_call.in_progress",
                "item_id": "ws_1",
                "output_index": 0,
                "sequence_number": 1,
            }
        )
    events.append(
        {
            "type": "response.output_text.delta",
            "delta": answer,
            "item_id": "msg_1",
            "output_index": 0,
            "content_index": 0,
            "sequence_number": 2,
        }
    )
    if terminal:
        output = [
            {"type": "reasoning", "id": "rs_1", "summary": []},
            {
                "type": "message",
                "id": "msg_1",
                "role": "assistant",
                "status": "completed",
                "content": [
                    {
                        "type": "output_text",
                        "text": answer,
                        "annotations": [annotation] if native else [],
                    }
                ],
            },
        ]
        if native:
            output.insert(
                0,
                {
                    "type": "web_search_call",
                    "id": "ws_1",
                    "status": "completed",
                    "action": {
                        "type": "search",
                        "query": "question",
                        "sources": None
                        if omit_sources
                        else [{"type": "url", "url": annotation["url"]}],
                    },
                },
            )
        events.append(
            {
                "type": f"response.{terminal}",
                "sequence_number": 3,
                "response": {
                    "id": "resp_1",
                    "object": "response",
                    "created_at": 1,
                    "model": "model",
                    "status": terminal,
                    "output": output,
                    "usage": {"input_tokens": 20, "output_tokens": 10, "total_tokens": 30},
                },
            }
        )
    return "".join(f"data: {json.dumps(event, ensure_ascii=False)}\n\n" for event in events)


def test_quick_answer_is_one_medium_request_with_history_and_no_research():
    requests = []

    def respond(request):
        assert request.url.path == "/v1/responses"
        payload = json.loads(request.content)
        requests.append(payload)
        assert payload["reasoning"] == {"effort": "medium"}
        assert payload["input"][0] == {"role": "user", "content": "Earlier question"}
        assert payload["input"][-1]["content"] == "你好，请回答这个问题"
        assert not payload.get("tools")
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=frames())

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = AsyncOpenAI(
                base_url="https://api.openai.com/v1", api_key="test", http_client=http
            )
            runner = DirectAnswerRunner(prepared(), client=client)
            events = [event async for event in runner.stream()]
            assert [event.type for event in events] == ["content"]
            assert runner.result.content == "你好！"
            assert runner.result.usage == {
                "input_tokens": 20,
                "output_tokens": 10,
                "total_tokens": 30,
                "requests": 1,
                "searches": 0,
                "agents": 0,
                "tool_calls": 0,
            }
            assert "PRIVATE_THINKING" not in str(events)

    asyncio.run(scenario())
    assert len(requests) == 1


def test_quick_openai_search_is_in_the_same_request_and_preserves_citations():
    def respond(request):
        payload = json.loads(request.content)
        assert payload["tools"] == [{"type": "web_search"}]
        assert payload["max_tool_calls"] == 1
        assert payload["include"] == ["web_search_call.action.sources"]
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, text=frames(native=True)
        )

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = AsyncOpenAI(
                base_url="https://api.openai.com/v1", api_key="test", http_client=http
            )
            runner = DirectAnswerRunner(prepared(web=True), client=client)
            events = [event async for event in runner.stream()]
            assert not {"agent", "plan", "progress"} & {event.type for event in events}
            assert runner.result.usage["requests"] == 1
            assert runner.result.usage["searches"] == 1
            assert runner.result.sources[0]["url"] == "https://example.com/source"

    asyncio.run(scenario())


def test_native_search_nullable_sources_still_preserves_annotation_citations():
    async def scenario():
        def respond(request):
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=frames(native=True, omit_sources=True),
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = AsyncOpenAI(
                base_url="https://api.openai.com/v1", api_key="test", http_client=http
            )
            runner = DirectAnswerRunner(prepared(web=True), client=client)
            _ = [event async for event in runner.stream()]
            assert runner.result.content == "你好！"
            assert runner.result.sources[0]["title"] == "官方来源"
            assert runner.result.usage["searches"] == 1

    asyncio.run(scenario())


def test_quick_deepseek_search_and_selected_documents_feed_one_model_call():
    calls = []

    async def search(query, limit):
        calls.append("search")
        return [{"title": "Evidence", "url": "https://example.com", "snippet": "Search evidence"}]

    def respond(request):
        calls.append("model")
        payload = json.loads(request.content)
        assert "tools" not in payload  # Flash does not support the native search tool.
        assert (
            "[Local 1]" in payload["instructions"] and "Local evidence" in payload["instructions"]
        )
        assert "[Web 1]" in payload["instructions"] and "Search evidence" in payload["instructions"]
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=frames())

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = AsyncOpenAI(
                base_url="https://api.deepseek.com", api_key="test", http_client=http
            )
            runner = DirectAnswerRunner(
                prepared(provider="deepseek", web=True, local=True), client=client, search=search
            )
            events = [event async for event in runner.stream()]
            assert not {"agent", "plan", "progress"} & {event.type for event in events}
            assert runner.result.usage["agents"] == 0
            assert [source["label"] for source in runner.result.sources] == ["Local 1", "Web 1"]

    asyncio.run(scenario())
    assert calls == ["search", "model"]


@pytest.mark.parametrize("terminal", ["", "incomplete", "failed"])
def test_truncated_or_failed_model_stream_is_never_success(terminal):
    async def scenario():
        def respond(request):
            return httpx.Response(
                200, headers={"content-type": "text/event-stream"}, text=frames(terminal=terminal)
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = AsyncOpenAI(
                base_url="https://api.openai.com/v1", api_key="test", http_client=http
            )
            runner = DirectAnswerRunner(prepared(), client=client)
            with pytest.raises(ResearchError):
                _ = [event async for event in runner.stream()]

    asyncio.run(scenario())


@pytest.mark.parametrize("status", [401, 403, 429])
def test_direct_sdk_http_errors_are_specific_and_do_not_expose_body(status):
    async def scenario():
        def respond(request):
            return httpx.Response(status, json={"error": {"message": "PRIVATE_UPSTREAM_KEY"}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = AsyncOpenAI(
                base_url="https://api.openai.com/v1",
                api_key="test",
                http_client=http,
                max_retries=0,
            )
            runner = DirectAnswerRunner(prepared(), client=client)
            with pytest.raises(ResearchError) as failure:
                _ = [event async for event in runner.stream()]
            assert "PRIVATE_UPSTREAM_KEY" not in str(failure.value)
            assert {401: "API key 未通过验证", 403: "服务商拒绝访问", 429: "服务商限流"}[
                status
            ] in str(failure.value)

    asyncio.run(scenario())


def test_cancelling_quick_chat_closes_the_inflight_response_stream():
    async def scenario():
        started = asyncio.Event()
        closed = asyncio.Event()

        class WaitingStream(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield frames(terminal="").encode()
                started.set()
                await asyncio.Event().wait()

            async def aclose(self):
                closed.set()

        def respond(request):
            return httpx.Response(
                200, headers={"content-type": "text/event-stream"}, stream=WaitingStream()
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = AsyncOpenAI(
                base_url="https://api.openai.com/v1", api_key="test", http_client=http
            )
            runner = DirectAnswerRunner(prepared(), client=client)

            async def consume():
                return [event async for event in runner.stream()]

            task = asyncio.create_task(consume())
            await asyncio.wait_for(started.wait(), 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert closed.is_set()
            assert runner.result.usage["requests"] == 1

    asyncio.run(scenario())


def test_deepseek_search_errors_keep_their_safe_actionable_message():
    async def scenario():
        async def failed_search(query, limit):
            raise WebSearchError("搜索服务限流或额度不足，请稍后重试。")

        def no_model_request(request):
            pytest.fail("Do not generate an answer after the required search fails")

        async with httpx.AsyncClient(transport=httpx.MockTransport(no_model_request)) as http:
            client = AsyncOpenAI(
                base_url="https://api.deepseek.com", api_key="test", http_client=http
            )
            runner = DirectAnswerRunner(
                prepared(provider="deepseek", web=True), client=client, search=failed_search
            )
            with pytest.raises(ResearchError, match="搜索服务限流或额度不足"):
                _ = [event async for event in runner.stream()]
            assert runner.result.usage["requests"] == 0

    asyncio.run(scenario())


def test_completed_response_is_not_downgraded_by_a_broken_tail_connection():
    async def scenario():
        closed = asyncio.Event()

        class BrokenTail(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield frames().encode()
                raise httpx.ReadError("Socket failed after a valid completed event")

            async def aclose(self):
                closed.set()

        def respond(request):
            return httpx.Response(
                200, headers={"content-type": "text/event-stream"}, stream=BrokenTail()
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
            client = AsyncOpenAI(
                base_url="https://api.openai.com/v1", api_key="test", http_client=http
            )
            runner = DirectAnswerRunner(prepared(), client=client)
            _ = [event async for event in runner.stream()]
            assert runner.result.content == "你好！"
            assert closed.is_set()

    asyncio.run(scenario())
