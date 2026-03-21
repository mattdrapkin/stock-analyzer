"""Integration tests for the news aggregator service.

These tests make REAL API calls to each configured provider.
Each test is automatically skipped if the corresponding API key is not set.

Run with:
    pytest tests/test_news_aggregator/test_integration.py -v
"""

import os
from datetime import date, timedelta

import pytest

from app.services.news_aggregator.providers.newsapi import NewsAPIProvider
from app.services.news_aggregator.providers.gnews import GNewsProvider
from app.services.news_aggregator.providers.jina import JinaProvider
from app.services.news_aggregator.providers.exa import ExaProvider
from app.services.news_aggregator.aggregator import (
    fetch_news_for_movement,
    fetch_news_for_period,
    has_any_news_key,
    get_configured_providers,
)

ARTICLE_KEYS = {"title", "source", "url", "published_at", "summary"}
QUERY = "Apple AAPL stock"
TO_DATE = date.today()
FROM_DATE = TO_DATE - timedelta(days=7)


def _assert_articles(articles, label):
    assert isinstance(articles, list), f"{label}: expected list, got {type(articles)}"
    assert len(articles) >= 1, f"{label}: expected at least 1 article, got 0"
    for a in articles:
        assert ARTICLE_KEYS.issubset(a.keys()), (
            f"{label}: article missing keys {ARTICLE_KEYS - a.keys()}"
        )
        assert isinstance(a["title"], str) and a["title"], f"{label}: blank title"
        assert isinstance(a["source"], str), f"{label}: source is not a str"
        assert isinstance(a["summary"], str), f"{label}: summary is not a str"


# ── Individual providers ───────────────────────────────────────────────────────

@pytest.mark.skipif(not os.getenv("NEWS_API_KEY"), reason="NEWS_API_KEY not set")
def test_newsapi_fetches_articles():
    provider = NewsAPIProvider()
    articles = provider.fetch(QUERY, FROM_DATE, TO_DATE, max_results=3)
    _assert_articles(articles, "NewsAPI")


@pytest.mark.skipif(not os.getenv("GNEWS_API_KEY"), reason="GNEWS_API_KEY not set")
def test_gnews_fetches_articles():
    provider = GNewsProvider()
    articles = provider.fetch(QUERY, FROM_DATE, TO_DATE, max_results=3)
    _assert_articles(articles, "GNews")


@pytest.mark.skipif(not os.getenv("JINA_API_KEY"), reason="JINA_API_KEY not set")
def test_jina_fetches_articles():
    provider = JinaProvider()
    articles = provider.fetch(QUERY, FROM_DATE, TO_DATE, max_results=3)
    _assert_articles(articles, "Jina AI")


@pytest.mark.skipif(not os.getenv("EXA_API_KEY"), reason="EXA_API_KEY not set")
def test_exa_fetches_articles():
    provider = ExaProvider()
    articles = provider.fetch(QUERY, FROM_DATE, TO_DATE, max_results=3)
    _assert_articles(articles, "Exa AI")


# ── Aggregator ─────────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    not any(os.getenv(k) for k in ("NEWS_API_KEY", "GNEWS_API_KEY", "JINA_API_KEY", "EXA_API_KEY")),
    reason="No news API keys configured",
)
def test_aggregator_has_configured_providers():
    assert has_any_news_key()
    providers = get_configured_providers()
    assert isinstance(providers, list)
    assert len(providers) >= 1


@pytest.mark.skipif(
    not any(os.getenv(k) for k in ("NEWS_API_KEY", "GNEWS_API_KEY", "JINA_API_KEY", "EXA_API_KEY")),
    reason="No news API keys configured",
)
def test_fetch_news_for_movement_returns_articles():
    articles = fetch_news_for_movement(
        movement_date=TO_DATE - timedelta(days=3),
        company_name="Apple",
        ticker="AAPL",
        max_per_category=3,
    )
    _assert_articles(articles, "fetch_news_for_movement")
    assert all(a["category"] == "company" for a in articles)


@pytest.mark.skipif(
    not any(os.getenv(k) for k in ("NEWS_API_KEY", "GNEWS_API_KEY", "JINA_API_KEY", "EXA_API_KEY")),
    reason="No news API keys configured",
)
def test_fetch_news_for_period_returns_articles():
    articles = fetch_news_for_period(
        from_date=FROM_DATE,
        to_date=TO_DATE,
        company_name="Apple",
        ticker="AAPL",
        max_per_category=3,
    )
    _assert_articles(articles, "fetch_news_for_period")
    assert all(a["category"] == "company" for a in articles)
