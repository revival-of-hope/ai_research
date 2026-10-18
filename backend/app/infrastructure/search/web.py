"""Provider-bound official web search; no anonymous search-engine fallback."""

import math
import re
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

import anyio
import httpx

from app.core.endpoints import validate_provider_url
from app.domain.research import ProviderConfig
from app.domain.workspace import InvalidInput

SearchResults = list[dict[str, str]]
SearchCallable = Callable[[str, int], Awaitable[SearchResults]]


class WebSearchError(RuntimeError):
    """Public diagnostics that never contain upstream bodies or credentials."""


def _endpoint(provider: ProviderConfig) -> tuple[str, bool]:
    try:
        base = validate_provider_url(provider.base_url)
        parsed = urlparse(base)
        port = parsed.port
    except InvalidInput as error:
        raise WebSearchError(str(error)) from None
    except ValueError:
        raise WebSearchError("搜索预设的 API 地址无效，请检查 Base URL。") from None
    host = parsed.hostname.lower()
    if host == "api.deepseek.com":
        if parsed.scheme != "https" or port not in (None, 443):
            raise WebSearchError("DeepSeek 官方搜索必须使用 HTTPS 官方地址。")
        if parsed.path.rstrip("/") not in ("", "/v1"):
            raise WebSearchError("DeepSeek 搜索的 Base URL 应为 https://api.deepseek.com。")
        return "https://api.deepseek.com/v1/tools/search", True
    if provider.provider_type == "deepseek":
        raise WebSearchError("DeepSeek 独立搜索需要官方地址 https://api.deepseek.com。")
    if provider.provider_type not in ("openai", "custom"):
        raise WebSearchError("当前预设未提供受支持的官方搜索，请选择 DeepSeek 或 OpenAI 预设。")
    return f"{base}/responses", False


def _status_error(status: int, deepseek: bool) -> WebSearchError:
    if status in (400, 404, 422):
        message = (
            "DeepSeek 搜索接口拒绝请求，请检查官方地址和搜索参数。"
            if deepseek
            else "当前模型或网关不支持 Responses 原生 web_search，请检查模型和接口能力。"
        )
    else:
        message = {
            401: "搜索 API key 未通过验证，请检查当前预设的密钥。",
            402: "搜索服务余额不足，请检查当前服务商账户额度。",
            403: "搜索服务拒绝访问，请检查当前密钥的权限。",
            429: "搜索服务限流或额度不足，请稍后重试。",
        }.get(status, f"搜索服务返回 HTTP {status}，请稍后重试。")
    return WebSearchError(message)


def _url(value: object) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip()
    try:
        parsed = urlparse(value)
        if (
            parsed.scheme in ("http", "https")
            and parsed.hostname
            and not parsed.username
            and not parsed.password
        ):
            return value
    except ValueError:
        pass
    return ""


def _text(value: object, maximum: int) -> str:
    return value.strip()[:maximum] if isinstance(value, str) else ""


def _deepseek_results(body: dict, limit: int) -> SearchResults:
    raw = body.get("results")
    if not isinstance(raw, list):
        raise WebSearchError("DeepSeek 搜索返回格式无法识别，请稍后重试。")
    results = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict) or not (url := _url(item.get("url"))) or url in seen:
            continue
        seen.add(url)
        results.append(
            {
                "title": _text(item.get("title"), 500) or url,
                "url": url,
                "snippet": _text(item.get("summary") or item.get("snippet"), 1200),
                "published": _text(item.get("date"), 100),
            }
        )
        if len(results) >= limit:
            break
    return results


_SENTENCE_END = re.compile(r"[。！？]|[.!?](?=\s|$|[\[\ue000-\uf8ff])")
_CITATION_MARKER = re.compile(r"\[[^\]\r\n]{0,120}\]|[^\r\n]*")


def _has_claim_text(value: str) -> bool:
    return any(character.isalnum() for character in _CITATION_MARKER.sub("", value))


def _citation_context(text: object, citation: dict) -> str:
    """Select local model text using offsets in the original, untrimmed block."""
    start, end = citation.get("start_index"), citation.get("end_index")
    if (
        not isinstance(text, str)
        or type(start) is not int
        or type(end) is not int
        or not 0 <= start < end <= len(text)
        or end - start > 500
        or "\n" in text[start:end]
        or not text[start:end].strip()
    ):
        return ""
    paragraph_start = text.rfind("\n", 0, start) + 1
    paragraph_end = text.find("\n", end)
    if paragraph_end == -1:
        paragraph_end = len(text)
    boundaries = [
        paragraph_start + match.end()
        for match in _SENTENCE_END.finditer(text[paragraph_start:paragraph_end])
    ]
    preceding = [boundary for boundary in boundaries if boundary <= start]
    left = preceding[-1] if preceding else paragraph_start
    if preceding and not _has_claim_text(text[left:start]):
        # Providers commonly place the citation marker just after sentence punctuation.
        left = preceding[-2] if len(preceding) > 1 else paragraph_start
        right = end
    else:
        right = next((boundary for boundary in boundaries if boundary >= end), paragraph_end)
    if right - left > 500:
        left = max(left, start - 250)
        right = min(right, left + 500)
        if end > right:
            left, right = end - 500, end
    fragment = text[left:right].strip()
    return fragment if _has_claim_text(fragment) else ""


def _openai_results(body: dict, limit: int) -> SearchResults:
    output = body.get("output")
    if (
        not isinstance(output, list)
        or body.get("error")
        or body.get("status") in ("failed", "cancelled", "in_progress", "queued")
    ):
        raise WebSearchError("搜索模型返回格式无法识别，请稍后重试。")
    calls = [
        item for item in output if isinstance(item, dict) and item.get("type") == "web_search_call"
    ]
    if not calls or not any(item.get("status") == "completed" for item in calls):
        raise WebSearchError("当前模型或网关未完成原生 web_search，无法提供联网证据。")
    results: dict[str, dict[str, str]] = {}
    fragments: dict[str, list[str]] = {}
    # Annotations carry titles. Their text is model output, not a page excerpt.
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "output_text":
                continue
            text = block.get("text")
            annotations = block.get("annotations", [])
            if not isinstance(annotations, list):
                continue
            for citation in annotations:
                if not isinstance(citation, dict) or citation.get("type") != "url_citation":
                    continue
                if url := _url(citation.get("url")):
                    result = results.setdefault(
                        url,
                        {
                            "title": _text(citation.get("title"), 500) or url,
                            "url": url,
                            "snippet": "",
                            "published": "",
                        },
                    )
                    fragment = _citation_context(text, citation)
                    matching = fragments.setdefault(url, [])
                    if fragment and fragment not in matching and len(matching) < 2:
                        matching.append(fragment)
                        result["snippet"] = "搜索模型生成的摘要（非网页原文）：" + "\n".join(
                            matching
                        )
    for call in calls:
        action = call.get("action")
        if not isinstance(action, dict) or not isinstance(action.get("sources"), list):
            continue
        for source in action["sources"]:
            if isinstance(source, dict) and (url := _url(source.get("url"))) and url not in results:
                results[url] = {"title": url, "url": url, "snippet": "", "published": ""}
    return list(results.values())[:limit]


def _usage(body: dict) -> dict[str, int] | None:
    raw = body.get("usage")
    if not isinstance(raw, dict):
        return None
    usage = {}
    for name in ("input_tokens", "output_tokens", "total_tokens"):
        value = raw.get(name)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            usage[name] = value
    if not usage:
        return None
    usage.setdefault("input_tokens", 0)
    usage.setdefault("output_tokens", 0)
    usage.setdefault("total_tokens", usage["input_tokens"] + usage["output_tokens"])
    return usage


def make_web_search(
    provider: ProviderConfig,
    *,
    client: httpx.AsyncClient | None = None,
    timeout: float = 30,
    on_model_request: Callable[[], None] | None = None,
    on_usage: Callable[[dict[str, int]], None] | None = None,
) -> SearchCallable:
    """Bind the decrypted run snapshot; callbacks account for extra Responses usage.

    A supplied client remains owned by its caller. All actual I/O is asynchronous;
    cancellation propagates, and the deadline also covers injected transports.
    """
    endpoint, deepseek = _endpoint(provider)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Search timeout must be positive and finite")

    async def search(query: str, limit: int = 6) -> SearchResults:
        query = query.strip()
        if not query:
            raise WebSearchError("搜索关键词不能为空。")
        limit = max(1, min(50, limit))
        if deepseek:
            payload = {"query": query[:128], "count": limit, "need_content": False}
        else:
            payload = {
                "model": provider.model,
                "input": query,
                "instructions": (
                    "Search for the query and provide a concise evidence summary with URL citations."
                ),
                "tools": [{"type": "web_search", "search_context_size": "low"}],
                "tool_choice": "required",
                "max_tool_calls": 1,
                "reasoning": {"effort": "medium"},
                "max_output_tokens": 4000,
                "include": ["web_search_call.action.sources"],
                "store": False,
            }
            if on_model_request is not None:
                on_model_request()

        async def request(http: httpx.AsyncClient) -> httpx.Response:
            return await http.post(
                endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {provider.api_key}"},
                timeout=timeout,
                follow_redirects=False,
            )

        try:
            with anyio.fail_after(timeout):
                if client is None:
                    async with httpx.AsyncClient() as http:
                        response = await request(http)
                else:
                    response = await request(client)
        except (TimeoutError, httpx.TimeoutException):
            raise WebSearchError("联网搜索超时，请稍后重试或缩小搜索范围。") from None
        except httpx.HTTPError:
            raise WebSearchError("无法连接搜索服务，请检查当前预设地址和服务器网络。") from None
        if response.status_code != 200:
            raise _status_error(response.status_code, deepseek)
        try:
            body = response.json()
        except ValueError:
            raise WebSearchError("搜索服务返回的 JSON 格式无法识别。") from None
        if not isinstance(body, dict):
            raise WebSearchError("搜索服务返回格式无法识别。")
        if not deepseek and on_usage is not None and (usage := _usage(body)) is not None:
            on_usage(usage)
        return _deepseek_results(body, limit) if deepseek else _openai_results(body, limit)

    return search
