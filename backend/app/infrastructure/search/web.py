import re

from anyio import to_thread
from ddgs import DDGS


class WebSearchError(RuntimeError):
    pass


_NEWS_QUERY = re.compile(
    r"(?:今日|今天|最新|热点|新闻|实时|刚刚|today|latest|news|breaking|current)",
    re.IGNORECASE,
)


def _search_sync(query: str, limit: int) -> list[dict[str, str]]:
    client = DDGS(timeout=15)
    if _NEWS_QUERY.search(query):
        raw_results = client.news(
            query=query,
            region="wt-wt",
            safesearch="moderate",
            timelimit="d",
            max_results=limit,
            backend="duckduckgo",
        )
    else:
        raw_results = client.text(
            query=query,
            region="wt-wt",
            safesearch="moderate",
            max_results=limit,
            backend="duckduckgo",
        )

    results: list[dict[str, str]] = []
    for item in raw_results or []:
        url = str(item.get("href") or item.get("url") or "").strip()
        if not url:
            continue
        results.append(
            {
                "title": str(item.get("title") or "Untitled").strip(),
                "url": url,
                "snippet": str(item.get("body") or item.get("description") or "")[:1200],
                "published": str(item.get("date") or "").strip(),
            }
        )
    return results


async def web_search(query: str, limit: int = 6) -> list[dict[str, str]]:
    """Run DDGS off the event loop and fail visibly when search is unavailable."""
    try:
        results = await to_thread.run_sync(_search_sync, query, limit, abandon_on_cancel=True)
    except Exception as error:
        raise WebSearchError(
            "联网搜索失败。请确认服务器可以访问 DuckDuckGo，或稍后重试。"
        ) from error
    if not results:
        raise WebSearchError("联网搜索没有返回结果，请换一个更具体的关键词后重试。")
    return results
