"""Unit tests for individual news provider implementations.

Each provider is tested with mocked HTTP responses to verify:
- is_available() correctly reflects whether an API key is configured
- fetch() returns correctly normalised article dicts
- fetch() handles HTTP errors gracefully without raising
"""

import os
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.services.news_aggregator.providers.newsapi import NewsAPIProvider
from app.services.news_aggregator.providers.gnews import GNewsProvider
from app.services.news_aggregator.providers.jina import JinaProvider
from app.services.news_aggregator.providers.exa import ExaProvider

ARTICLE_KEYS = {"title", "source", "url", "published_at", "summary"}
FROM_DATE = date(2024, 1, 13)
TO_DATE = date(2024, 1, 15)
QUERY = "Apple AAPL stock"


def _mock_client(json_data):
    """Return a mock httpx.Client context manager that yields json_data."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = json_data
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value.get.return_value = mock_resp
    mock_cm.__enter__.return_value.post.return_value = mock_resp
    mock_cm.__exit__.return_value = False
    return mock_cm


def _assert_valid_articles(articles):
    assert isinstance(articles, list)
    assert len(articles) >= 1
    for a in articles:
        assert isinstance(a, dict)
        assert ARTICLE_KEYS.issubset(a.keys()), f"Missing keys: {ARTICLE_KEYS - a.keys()}"
        assert isinstance(a["title"], str) and a["title"]
        assert isinstance(a["source"], str)
        assert isinstance(a["summary"], str)


# ── NewsAPI ────────────────────────────────────────────────────────────────────

class TestNewsAPIProvider:
    _NEWSAPI_RESPONSE = {
        "status": "ok",
        "articles": [
            {
                "title": "Apple Stock Surges on Strong Earnings",
                "source": {"name": "Reuters"},
                "url": "https://reuters.com/apple-earnings",
                "publishedAt": "2024-01-14T10:00:00Z",
                "description": "Apple shares climbed after beating expectations.",
            }
        ],
    }

    def test_is_available_without_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NEWS_API_KEY", None)
            provider = NewsAPIProvider()
            assert not provider.is_available()

    def test_is_available_with_key(self):
        with patch.dict(os.environ, {"NEWS_API_KEY": "test-key"}):
            provider = NewsAPIProvider()
            assert provider.is_available()

    def test_fetch_returns_empty_when_unavailable(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NEWS_API_KEY", None)
            provider = NewsAPIProvider()
            result = provider.fetch(QUERY, FROM_DATE, TO_DATE)
            assert result == []

    def test_fetch_returns_normalised_articles(self):
        with patch.dict(os.environ, {"NEWS_API_KEY": "test-key"}):
            provider = NewsAPIProvider()
            mock_cm = _mock_client(self._NEWSAPI_RESPONSE)
            with patch("app.services.news_aggregator.providers.newsapi.httpx.Client", return_value=mock_cm):
                articles = provider.fetch(QUERY, FROM_DATE, TO_DATE)
            _assert_valid_articles(articles)
            assert articles[0]["title"] == "Apple Stock Surges on Strong Earnings"
            assert articles[0]["source"] == "Reuters"

    def test_fetch_returns_empty_on_http_error(self):
        import httpx
        with patch.dict(os.environ, {"NEWS_API_KEY": "test-key"}):
            provider = NewsAPIProvider()
            mock_cm = MagicMock()
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "401", request=MagicMock(), response=MagicMock(status_code=401)
            )
            mock_cm.__enter__.return_value.get.return_value = mock_resp
            mock_cm.__exit__.return_value = False
            with patch("app.services.news_aggregator.providers.newsapi.httpx.Client", return_value=mock_cm):
                result = provider.fetch(QUERY, FROM_DATE, TO_DATE)
            assert result == []

    def test_fetch_skips_removed_articles(self):
        response = {
            "status": "ok",
            "articles": [
                {"title": "[Removed]", "source": {"name": "Removed"}, "url": None, "publishedAt": None, "description": ""},
                {"title": "Valid Article", "source": {"name": "BBC"}, "url": "https://bbc.com/news", "publishedAt": "2024-01-14T10:00:00Z", "description": "Summary."},
            ],
        }
        with patch.dict(os.environ, {"NEWS_API_KEY": "test-key"}):
            provider = NewsAPIProvider()
            with patch("app.services.news_aggregator.providers.newsapi.httpx.Client", return_value=_mock_client(response)):
                articles = provider.fetch(QUERY, FROM_DATE, TO_DATE)
        assert len(articles) == 1
        assert articles[0]["title"] == "Valid Article"


# ── GNews ──────────────────────────────────────────────────────────────────────

class TestGNewsProvider:
    _GNEWS_RESPONSE = {
        "articles": [
            {
                "title": "Apple Q1 Earnings Beat Estimates",
                "source": {"name": "Bloomberg"},
                "url": "https://bloomberg.com/apple-q1",
                "publishedAt": "2024-01-14T08:30:00Z",
                "description": "Apple reported record Q1 revenue.",
            }
        ]
    }

    def test_is_available_without_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GNEWS_API_KEY", None)
            provider = GNewsProvider()
            assert not provider.is_available()

    def test_is_available_with_key(self):
        with patch.dict(os.environ, {"GNEWS_API_KEY": "test-key"}):
            provider = GNewsProvider()
            assert provider.is_available()

    def test_fetch_returns_empty_when_unavailable(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GNEWS_API_KEY", None)
            provider = GNewsProvider()
            result = provider.fetch(QUERY, FROM_DATE, TO_DATE)
            assert result == []

    def test_fetch_returns_normalised_articles(self):
        with patch.dict(os.environ, {"GNEWS_API_KEY": "test-key"}):
            provider = GNewsProvider()
            with patch("app.services.news_aggregator.providers.gnews.httpx.Client", return_value=_mock_client(self._GNEWS_RESPONSE)):
                articles = provider.fetch(QUERY, FROM_DATE, TO_DATE)
            _assert_valid_articles(articles)
            assert articles[0]["title"] == "Apple Q1 Earnings Beat Estimates"
            assert articles[0]["source"] == "Bloomberg"

    def test_fetch_returns_empty_on_http_error(self):
        import httpx
        with patch.dict(os.environ, {"GNEWS_API_KEY": "test-key"}):
            provider = GNewsProvider()
            mock_cm = MagicMock()
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "403", request=MagicMock(), response=MagicMock(status_code=403)
            )
            mock_cm.__enter__.return_value.get.return_value = mock_resp
            mock_cm.__exit__.return_value = False
            with patch("app.services.news_aggregator.providers.gnews.httpx.Client", return_value=mock_cm):
                result = provider.fetch(QUERY, FROM_DATE, TO_DATE)
            assert result == []


# ── Jina AI ────────────────────────────────────────────────────────────────────

class TestJinaProvider:
    _JINA_RESPONSE = {
        "data": [
            {
                "title": "Apple Vision Pro Launch Coverage",
                "url": "https://techcrunch.com/apple-vision-pro",
                "publishedTime": "2024-01-14T09:00:00Z",
                "description": "Apple launched its Vision Pro headset.",
            }
        ]
    }

    def test_is_available_without_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JINA_API_KEY", None)
            provider = JinaProvider()
            assert not provider.is_available()

    def test_is_available_with_key(self):
        with patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
            provider = JinaProvider()
            assert provider.is_available()

    def test_fetch_returns_empty_when_unavailable(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JINA_API_KEY", None)
            provider = JinaProvider()
            result = provider.fetch(QUERY, FROM_DATE, TO_DATE)
            assert result == []

    def test_fetch_returns_normalised_articles(self):
        with patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
            provider = JinaProvider()
            with patch("app.services.news_aggregator.providers.jina.httpx.Client", return_value=_mock_client(self._JINA_RESPONSE)):
                articles = provider.fetch(QUERY, FROM_DATE, TO_DATE)
            _assert_valid_articles(articles)
            assert articles[0]["title"] == "Apple Vision Pro Launch Coverage"
            assert "techcrunch.com" in articles[0]["source"]

    def test_fetch_injects_date_range_into_query(self):
        """Jina has no native date filter — verify date context is appended to the query."""
        with patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
            provider = JinaProvider()
            mock_cm = _mock_client(self._JINA_RESPONSE)
            with patch("app.services.news_aggregator.providers.jina.httpx.Client", return_value=mock_cm):
                provider.fetch(QUERY, FROM_DATE, TO_DATE)
            call_kwargs = mock_cm.__enter__.return_value.get.call_args
            sent_query = call_kwargs[1]["params"]["q"]
            assert "January 13 2024" in sent_query
            assert "January 15 2024" in sent_query

    def test_fetch_returns_empty_on_http_error(self):
        import httpx
        with patch.dict(os.environ, {"JINA_API_KEY": "test-key"}):
            provider = JinaProvider()
            mock_cm = MagicMock()
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "401", request=MagicMock(), response=MagicMock(status_code=401)
            )
            mock_cm.__enter__.return_value.get.return_value = mock_resp
            mock_cm.__exit__.return_value = False
            with patch("app.services.news_aggregator.providers.jina.httpx.Client", return_value=mock_cm):
                result = provider.fetch(QUERY, FROM_DATE, TO_DATE)
            assert result == []


# ── Exa AI ─────────────────────────────────────────────────────────────────────

class TestExaProvider:
    _EXA_RESPONSE = {
        "results": [
            {
                "title": "Apple Hits $3 Trillion Market Cap",
                "url": "https://wsj.com/apple-3-trillion",
                "publishedDate": "2024-01-14T12:00:00Z",
                "highlights": ["Apple reached a $3 trillion valuation.", "Shares rose 2%."],
            }
        ]
    }

    def test_is_available_without_key(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EXA_API_KEY", None)
            provider = ExaProvider()
            assert not provider.is_available()

    def test_is_available_with_key(self):
        with patch.dict(os.environ, {"EXA_API_KEY": "test-key"}):
            provider = ExaProvider()
            assert provider.is_available()

    def test_fetch_returns_empty_when_unavailable(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("EXA_API_KEY", None)
            provider = ExaProvider()
            result = provider.fetch(QUERY, FROM_DATE, TO_DATE)
            assert result == []

    def test_fetch_returns_normalised_articles(self):
        with patch.dict(os.environ, {"EXA_API_KEY": "test-key"}):
            provider = ExaProvider()
            with patch("app.services.news_aggregator.providers.exa.httpx.Client", return_value=_mock_client(self._EXA_RESPONSE)):
                articles = provider.fetch(QUERY, FROM_DATE, TO_DATE)
            _assert_valid_articles(articles)
            assert articles[0]["title"] == "Apple Hits $3 Trillion Market Cap"
            assert "sj.com" in articles[0]["source"]
            assert "Apple reached a $3 trillion valuation." in articles[0]["summary"]

    def test_fetch_uses_post_not_get(self):
        """Exa uses a POST request — verify the correct HTTP method is called."""
        with patch.dict(os.environ, {"EXA_API_KEY": "test-key"}):
            provider = ExaProvider()
            mock_cm = _mock_client(self._EXA_RESPONSE)
            with patch("app.services.news_aggregator.providers.exa.httpx.Client", return_value=mock_cm):
                provider.fetch(QUERY, FROM_DATE, TO_DATE)
            mock_cm.__enter__.return_value.post.assert_called_once()
            mock_cm.__enter__.return_value.get.assert_not_called()

    def test_fetch_returns_empty_on_http_error(self):
        import httpx
        with patch.dict(os.environ, {"EXA_API_KEY": "test-key"}):
            provider = ExaProvider()
            mock_cm = MagicMock()
            mock_resp = MagicMock()
            mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "401", request=MagicMock(), response=MagicMock(status_code=401)
            )
            mock_cm.__enter__.return_value.post.return_value = mock_resp
            mock_cm.__exit__.return_value = False
            with patch("app.services.news_aggregator.providers.exa.httpx.Client", return_value=mock_cm):
                result = provider.fetch(QUERY, FROM_DATE, TO_DATE)
            assert result == []
