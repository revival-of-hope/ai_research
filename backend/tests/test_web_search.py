from app.infrastructure.search import web


class FakeDDGS:
    def __init__(self, timeout: int):
        assert timeout == 15

    def news(self, **kwargs):
        assert kwargs["backend"] == "duckduckgo"
        assert kwargs["timelimit"] == "d"
        return [
            {
                "title": "Today",
                "url": "https://example.com/today",
                "body": "Latest update",
                "date": "2026-09-22",
            }
        ]

    def text(self, **kwargs):
        assert kwargs["backend"] == "duckduckgo"
        return [
            {
                "title": "Paper",
                "href": "https://example.com/paper",
                "body": "Research result",
            }
        ]


def test_ddgs_uses_news_search_for_fresh_queries(monkeypatch):
    monkeypatch.setattr(web, "DDGS", FakeDDGS)

    results = web._search_sync("今日热点新闻", 6)

    assert results[0]["url"] == "https://example.com/today"
    assert results[0]["published"] == "2026-09-22"


def test_ddgs_uses_text_search_for_regular_queries(monkeypatch):
    monkeypatch.setattr(web, "DDGS", FakeDDGS)

    results = web._search_sync("vision transformer", 6)

    assert results[0]["title"] == "Paper"
    assert results[0]["snippet"] == "Research result"
