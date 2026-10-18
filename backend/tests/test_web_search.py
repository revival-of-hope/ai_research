"""Deterministic contracts: all HTTP uses MockTransport, never paid live APIs."""

import asyncio
import json
import traceback
from dataclasses import replace

import httpx
import pytest

from app.domain.research import BudgetExceeded, ProviderConfig
from app.infrastructure.search.web import WebSearchError, make_web_search

DEEPSEEK = ProviderConfig(
    id=1,
    name="My DeepSeek",
    base_url="https://api.deepseek.com",
    model="deepseek-flash",
    api_key="snapshot-deepseek-key",
    provider_type="deepseek",
)
OPENAI = replace(
    DEEPSEEK,
    id=2,
    name="My OpenAI",
    base_url="https://api.openai.com/v1",
    model="my-search-capable-model",
    api_key="snapshot-openai-key",
    provider_type="openai",
)


def deepseek_result(**overrides):
    return {
        "rerank_score": 2.4,
        "title": "Release",
        "url": "https://example.com/release",
        "snippet": "Short search snippet",
        "summary": "Longer search summary for the model",
        "content": "",
        "site_name": "Example",
        "site_icon": None,
        "date": "2026-10-17T09:00:00Z",
        "authority": 3,
        **overrides,
    }


def openai_response():
    return {
        "status": "completed",
        "output": [
            {
                "type": "web_search_call",
                "status": "completed",
                "action": {
                    "type": "search",
                    "queries": ["release"],
                    "sources": [
                        {"type": "url", "url": "https://example.com/release"},
                        {"type": "url", "url": "https://example.com/uncited"},
                    ],
                },
            },
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "Model-written evidence summary with citations.",
                        "annotations": [
                            {
                                "type": "url_citation",
                                "title": "Release",
                                "url": "https://example.com/release",
                                "start_index": 30,
                                "end_index": 40,
                            }
                        ],
                    }
                ],
            },
        ],
        "usage": {"input_tokens": 80, "output_tokens": 20, "total_tokens": 100},
    }


def search_openai_text(text, annotations):
    body = openai_response()
    body["output"][1]["content"] = [
        {"type": "output_text", "text": text, "annotations": annotations}
    ]

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
        ) as client:
            return await make_web_search(OPENAI, client=client)("query", 10)

    return asyncio.run(run())


def indexed_citation(text, marker, url):
    start = text.index(marker)
    return {
        "type": "url_citation",
        "url": url,
        "title": "Indexed source",
        "start_index": start,
        "end_index": start + len(marker),
    }


def test_citation_offsets_bind_each_source_to_its_own_paragraph():
    text = "  The lunar mission launched in June. [1]\n\nThe battery trial doubled cycle life. [2]"
    results = search_openai_text(
        text,
        [
            indexed_citation(text, "[1]", "https://example.com/lunar"),
            indexed_citation(text, "[2]", "https://example.com/battery"),
        ],
    )
    lunar, battery = results[:2]
    assert "lunar mission" in lunar["snippet"]
    assert "battery" not in lunar["snippet"]
    assert "battery trial" in battery["snippet"]
    assert "lunar" not in battery["snippet"]
    assert battery["snippet"].startswith("搜索模型生成的摘要（非网页原文）：")


def test_citation_offsets_bind_sentences_within_the_same_paragraph():
    text = "Lunar launch succeeded. [1] Battery cells lasted longer. [2]"
    results = search_openai_text(
        text,
        [
            indexed_citation(text, "[1]", "https://example.com/lunar"),
            indexed_citation(text, "[2]", "https://example.com/battery"),
        ],
    )
    assert "Battery" not in results[0]["snippet"]
    assert "Lunar" not in results[1]["snippet"]
    assert "Battery cells lasted longer" in results[1]["snippet"]


def test_citation_after_character_1100_uses_its_later_section():
    text = "Earlier unrelated background. " * 80 + "\n\nThe distant trial reduced cost. [2]"
    citation = indexed_citation(text, "[2]", "https://example.com/distant")
    assert citation["start_index"] > 1100

    results = search_openai_text(text, [citation])

    assert "distant trial reduced cost" in results[0]["snippet"]
    assert "Earlier unrelated" not in results[0]["snippet"]
    assert len(results[0]["snippet"]) <= 1050


def test_adjacent_citations_stay_with_the_preceding_claim():
    text = "Lunar launch succeeded. [1] [2] Battery research is unrelated."
    results = search_openai_text(
        text,
        [
            indexed_citation(text, "[1]", "https://example.com/lunar-one"),
            indexed_citation(text, "[2]", "https://example.com/lunar-two"),
        ],
    )
    assert all("Lunar launch succeeded" in item["snippet"] for item in results[:2])
    assert all("Battery" not in item["snippet"] for item in results[:2])


@pytest.mark.parametrize(
    ("start", "end"),
    [(None, None), (-1, 5), (0, 10000), (8, 3), (0, 0), ("0", 5), (True, 5), (0, False)],
)
def test_unreliable_citation_offsets_leave_the_source_snippet_empty(start, end):
    citation = {
        "type": "url_citation",
        "url": "https://example.com/unreliable",
        "title": "Source with invalid offsets",
        "start_index": start,
        "end_index": end,
    }

    results = search_openai_text("Two unrelated claims. [1]", [citation])

    assert results[0]["title"] == "Source with invalid offsets"
    assert results[0]["snippet"] == ""


def test_citation_range_crossing_paragraphs_does_not_mix_claims():
    text = "Claim one.\n\nClaim two."
    citation = indexed_citation(text, text, "https://example.com/uncertain")

    assert search_openai_text(text, [citation])[0]["snippet"] == ""


def test_citation_marker_without_an_associated_claim_leaves_snippet_empty():
    text = "[1]"
    citation = indexed_citation(text, text, "https://example.com/no-claim")

    assert search_openai_text(text, [citation])[0]["snippet"] == ""


def test_same_url_merges_only_its_matching_fragments_and_deduplicates_them():
    text = "The trial increased revenue. [1]\n\nThe follow-up reduced cost. [2]"
    first = indexed_citation(text, "[1]", "https://example.com/shared")
    second = indexed_citation(text, "[2]", "https://example.com/shared")

    results = search_openai_text(text, [first, first, second])

    assert len([item for item in results if item["url"] == first["url"]]) == 1
    assert results[0]["snippet"].count("trial increased revenue") == 1
    assert results[0]["snippet"].count("follow-up reduced cost") == 1


@pytest.mark.parametrize("base", ["https://api.deepseek.com", "https://api.deepseek.com/v1/"])
def test_deepseek_uses_documented_search_endpoint_and_snapshot_key(base):
    def handle(request):
        assert str(request.url) == "https://api.deepseek.com/v1/tools/search"
        assert request.headers["Authorization"] == "Bearer snapshot-deepseek-key"
        assert request.headers["Content-Type"] == "application/json"
        assert json.loads(request.content) == {
            "query": 'V4 site:example.com "release"',
            "count": 5,
            "need_content": False,
        }
        return httpx.Response(200, json={"results": [deepseek_result()]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            calls = []
            search = make_web_search(
                replace(DEEPSEEK, base_url=base),
                client=client,
                on_model_request=lambda: calls.append("model"),
                on_usage=lambda _: calls.append("usage"),
            )
            results = await search('  V4 site:example.com "release"  ', 5)
            assert not client.is_closed
            assert calls == []
            assert results == [
                {
                    "title": "Release",
                    "url": "https://example.com/release",
                    "snippet": "Longer search summary for the model",
                    "published": "2026-10-17T09:00:00Z",
                }
            ]

    asyncio.run(run())


@pytest.mark.parametrize(("limit", "count"), [(0, 1), (80, 50)])
def test_deepseek_limits_unicode_query_and_result_count(limit, count):
    def handle(request):
        payload = json.loads(request.content)
        assert payload["query"] == "研究😀" * 42 + "研究"
        assert len(payload["query"]) == 128
        assert payload["count"] == count
        return httpx.Response(200, json={"results": []})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            assert (
                await make_web_search(DEEPSEEK, client=client)("  " + "研究😀" * 100, limit) == []
            )

    asyncio.run(run())


def test_deepseek_filters_invalid_urls_deduplicates_and_bounds_snippets():
    items = [
        None,
        deepseek_result(url="javascript:alert(1)"),
        deepseek_result(url="https://key:secret@example.com/"),
        deepseek_result(summary="", date=None),
        deepseek_result(summary="duplicate"),
        deepseek_result(url="https://example.com/second", summary="x" * 2000),
        deepseek_result(url="https://example.com/third"),
    ]

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"results": items}))
        ) as client:
            results = await make_web_search(DEEPSEEK, client=client)("query", 2)
            assert len(results) == 2
            assert results[0]["snippet"] == "Short search snippet"
            assert results[0]["published"] == ""
            assert len(results[1]["snippet"]) == 1200

    asyncio.run(run())


@pytest.mark.parametrize(
    "provider",
    [OPENAI, replace(OPENAI, provider_type="custom", base_url="https://gateway.example/v1")],
)
def test_responses_forces_one_native_search_and_reports_model_usage(provider):
    order = []

    def handle(request):
        order.append("http")
        assert str(request.url) == provider.base_url + "/responses"
        assert request.headers["Authorization"] == "Bearer " + provider.api_key
        payload = json.loads(request.content)
        assert payload["model"] == provider.model
        assert payload["input"] == "release"
        assert payload["tools"] == [{"type": "web_search", "search_context_size": "low"}]
        assert payload["tool_choice"] == "required"
        assert payload["max_tool_calls"] == 1
        assert payload["reasoning"] == {"effort": "medium"}
        assert payload["max_output_tokens"] == 4000
        assert payload["include"] == ["web_search_call.action.sources"]
        assert payload["store"] is False
        return httpx.Response(200, json=openai_response())

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            usage = []
            results = await make_web_search(
                provider,
                client=client,
                on_model_request=lambda: order.append("reserve"),
                on_usage=usage.append,
            )("release", 5)
            assert order == ["reserve", "http"]
            assert usage == [{"input_tokens": 80, "output_tokens": 20, "total_tokens": 100}]
            assert [item["url"] for item in results] == [
                "https://example.com/release",
                "https://example.com/uncited",
            ]
            assert results[0]["title"] == "Release"
            assert results[0]["snippet"].startswith("搜索模型生成的摘要（非网页原文）：")
            assert results[1]["snippet"] == ""
            assert results[1]["published"] == ""

    asyncio.run(run())


def test_budget_refusal_prevents_any_extra_model_request():
    def reserve():
        raise BudgetExceeded("request budget")

    def handle(_):
        pytest.fail("No request may be sent after budget refusal")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with pytest.raises(BudgetExceeded, match="request budget"):
                await make_web_search(OPENAI, client=client, on_model_request=reserve)("query", 5)

    asyncio.run(run())


@pytest.mark.parametrize("status", [400, 401, 402, 403, 404, 422, 429, 500, 504])
@pytest.mark.parametrize("provider", [DEEPSEEK, OPENAI])
def test_upstream_errors_are_visible_and_never_leak_body_or_key(status, provider):
    secret = "UPSTREAM-SECRET-DO-NOT-SHOW"

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(status, text=secret + provider.api_key)
            )
        ) as client:
            with pytest.raises(WebSearchError) as raised:
                await make_web_search(provider, client=client)("query", 5)
            diagnostic = "".join(traceback.format_exception(raised.value))
            assert secret not in diagnostic
            assert provider.api_key not in diagnostic
            if status == 401:
                assert "key" in str(raised.value)
            if status == 402:
                assert "余额" in str(raised.value)
            if status == 429:
                assert "限流" in str(raised.value)

    asyncio.run(run())


def test_redirect_never_forwards_snapshot_key_to_another_host():
    calls = []

    def handle(request):
        calls.append(str(request.url))
        return httpx.Response(307, headers={"Location": "https://untrusted.example/search"})

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handle), follow_redirects=True
        ) as client:
            with pytest.raises(WebSearchError, match="307"):
                await make_web_search(DEEPSEEK, client=client)("query", 5)
            assert calls == ["https://api.deepseek.com/v1/tools/search"]

    asyncio.run(run())


@pytest.mark.parametrize("body", [[], {}, {"results": {}}, {"results": None}])
def test_malformed_deepseek_responses_fail_explicitly(body):
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
        ) as client:
            with pytest.raises(WebSearchError, match="格式"):
                await make_web_search(DEEPSEEK, client=client)("query", 5)

    asyncio.run(run())


def test_invalid_json_does_not_echo_raw_response():
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, text="secret-invalid-json"))
        ) as client:
            with pytest.raises(WebSearchError, match="JSON") as raised:
                await make_web_search(DEEPSEEK, client=client)("query", 5)
            assert "secret-invalid-json" not in str(raised.value)
            assert raised.value.__suppress_context__

    asyncio.run(run())


def test_model_that_does_not_actually_search_cannot_supply_web_evidence():
    body = openai_response()
    body["output"] = body["output"][1:]

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
        ) as client:
            usage = []
            with pytest.raises(WebSearchError, match="未完成原生"):
                await make_web_search(OPENAI, client=client, on_usage=usage.append)("query", 5)
            assert usage[0]["total_tokens"] == 100

    asyncio.run(run())


def test_failed_model_response_still_reports_consumed_usage_without_returning_evidence():
    body = openai_response()
    body["status"] = "failed"

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body))
        ) as client:
            usage = []
            with pytest.raises(WebSearchError):
                await make_web_search(OPENAI, client=client, on_usage=usage.append)("query", 5)
            assert usage[0]["total_tokens"] == 100

    asyncio.run(run())


def test_concurrent_factories_keep_each_users_decrypted_snapshot_key():
    seen = []

    async def handle(request):
        seen.append((json.loads(request.content)["model"], request.headers["Authorization"]))
        await asyncio.sleep(0)
        return httpx.Response(200, json=openai_response())

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            first = make_web_search(replace(OPENAI, model="user-a", api_key="key-a"), client=client)
            second = make_web_search(
                replace(OPENAI, model="user-b", api_key="key-b"), client=client
            )
            await asyncio.gather(first("first", 1), second("second", 1))
        assert set(seen) == {("user-a", "Bearer key-a"), ("user-b", "Bearer key-b")}

    asyncio.run(run())


@pytest.mark.parametrize(
    "provider",
    [
        replace(DEEPSEEK, base_url="https://unverified.example"),
        replace(OPENAI, provider_type="qwen"),
    ],
)
def test_unsupported_provider_is_rejected_without_fallback(provider):
    with pytest.raises(WebSearchError):
        make_web_search(provider)


@pytest.mark.parametrize("query", ["", " \n "])
def test_blank_query_is_rejected_before_network(query):
    async def run():
        with pytest.raises(WebSearchError, match="不能为空"):
            await make_web_search(DEEPSEEK)(query, 5)

    asyncio.run(run())


@pytest.mark.parametrize(
    "base",
    [
        "http://api.deepseek.com",
        "https://api.deepseek.com:secret",
        "https://api.deepseek.com/other",
    ],
)
def test_invalid_official_search_url_fails_before_any_http(base):
    with pytest.raises(WebSearchError) as raised:
        make_web_search(replace(DEEPSEEK, base_url=base))
    assert "secret" not in str(raised.value)


def test_async_deadline_cancels_a_transport_that_ignores_httpx_timeout():
    async def run():
        stopped = asyncio.Event()

        async def handle(_):
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with pytest.raises(WebSearchError, match="超时"):
                await make_web_search(DEEPSEEK, client=client, timeout=0.02)("query", 5)
            assert stopped.is_set()

    asyncio.run(run())


def test_caller_cancellation_propagates_to_inflight_http_without_error_wrapping():
    async def run():
        entered, stopped = asyncio.Event(), asyncio.Event()

        async def handle(_):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            task = asyncio.create_task(make_web_search(DEEPSEEK, client=client)("query", 5))
            await asyncio.wait_for(entered.wait(), 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert stopped.is_set()

    asyncio.run(run())


@pytest.mark.parametrize("failure", [httpx.ReadTimeout, httpx.ConnectError])
def test_transport_exception_details_are_suppressed(failure):
    def handle(request):
        raise failure("network-log-with-secret-key", request=request)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            with pytest.raises(WebSearchError) as raised:
                await make_web_search(DEEPSEEK, client=client)("query", 5)
            diagnostic = "".join(traceback.format_exception(raised.value))
            assert "network-log-with-secret-key" not in diagnostic
            assert raised.value.__suppress_context__

    asyncio.run(run())
