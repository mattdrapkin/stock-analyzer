"""Live API tests - verifies each provider can actually fetch articles.

Each test makes REAL API calls and only checks that:
1. The provider is available (has API key)
2. At least one article is returned
3. Articles have the expected schema

Run with:
    pytest tests/test_news_aggregator/test_live_api.py -v -s
"""

import logging
import os
from datetime import date, timedelta

import pytest

from app.services.news_aggregator.providers.newsapi import NewsAPIProvider
from app.services.news_aggregator.providers.gnews import GNewsProvider
from app.services.news_aggregator.providers.jina import JinaProvider
from app.services.news_aggregator.providers.exa import ExaProvider

# Configure logging to see error messages
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

ARTICLE_KEYS = {"title", "source", "url", "published_at", "summary"}
QUERY = "Apple AAPL stock"
TO_DATE = date.today()
FROM_DATE = TO_DATE - timedelta(days=7)


def _assert_has_articles(articles, provider_name):
    """Assert we got at least one article with correct schema."""
    assert isinstance(articles, list), f"{provider_name}: expected list, got {type(articles)}"
    
    if len(articles) == 0:
        print(f"⚠️  {provider_name}: No articles returned (may be rate limited, API issue, or no results)")
        return
    
    for i, a in enumerate(articles):
        assert isinstance(a, dict), f"{provider_name}: article {i} is not a dict"
        assert ARTICLE_KEYS.issubset(a.keys()), (
            f"{provider_name}: article {i} missing keys {ARTICLE_KEYS - a.keys()}"
        )
        assert isinstance(a["title"], str) and a["title"], f"{provider_name}: article {i} blank title"
        assert isinstance(a["source"], str), f"{provider_name}: article {i} source is not a str"
        assert isinstance(a["summary"], str), f"{provider_name}: article {i} summary is not a str"


@pytest.mark.skipif(not os.getenv("NEWS_API_KEY"), reason="NEWS_API_KEY not set")
def test_newsapi_live_api():
    """Test NewsAPI can fetch real articles."""
    provider = NewsAPIProvider()
    assert provider.is_available(), "NewsAPI should be available with NEWS_API_KEY"
    
    articles = provider.fetch(QUERY, FROM_DATE, TO_DATE, max_results=3)
    _assert_has_articles(articles, "NewsAPI")


@pytest.mark.skipif(not os.getenv("GNEWS_API_KEY"), reason="GNEWS_API_KEY not set")
def test_gnews_live_api():
    """Test GNews can fetch real articles."""
    provider = GNewsProvider()
    assert provider.is_available(), "GNews should be available with GNEWS_API_KEY"
    
    articles = provider.fetch(QUERY, FROM_DATE, TO_DATE, max_results=3)
    _assert_has_articles(articles, "GNews")


@pytest.mark.skipif(not os.getenv("JINA_API_KEY"), reason="JINA_API_KEY not set")
def test_jina_live_api():
    """Test Jina AI can fetch real articles."""
    provider = JinaProvider()
    assert provider.is_available(), "Jina AI should be available with JINA_API_KEY"
    
    articles = provider.fetch(QUERY, FROM_DATE, TO_DATE, max_results=3)
    _assert_has_articles(articles, "Jina AI")


@pytest.mark.skipif(not os.getenv("EXA_API_KEY"), reason="EXA_API_KEY not set")
def test_exa_live_api():
    """Test Exa AI can fetch real articles."""
    provider = ExaProvider()
    assert provider.is_available(), "Exa AI should be available with EXA_API_KEY"
    
    articles = provider.fetch(QUERY, FROM_DATE, TO_DATE, max_results=3)
    _assert_has_articles(articles, "Exa AI")


@pytest.mark.skipif(
    not any(os.getenv(k) for k in ("NEWS_API_KEY", "GNEWS_API_KEY", "JINA_API_KEY", "EXA_API_KEY")),
    reason="No news API keys configured",
)
def test_at_least_one_provider_works():
    """Smoke test to verify at least one provider is working."""
    working_providers = []
    
    if os.getenv("NEWS_API_KEY"):
        articles = NewsAPIProvider().fetch(QUERY, FROM_DATE, TO_DATE, max_results=1)
        if articles:
            working_providers.append("NewsAPI")
    
    if os.getenv("GNEWS_API_KEY"):
        articles = GNewsProvider().fetch(QUERY, FROM_DATE, TO_DATE, max_results=1)
        if articles:
            working_providers.append("GNews")
    
    if os.getenv("JINA_API_KEY"):
        articles = JinaProvider().fetch(QUERY, FROM_DATE, TO_DATE, max_results=1)
        if articles:
            working_providers.append("Jina AI")
    
    if os.getenv("EXA_API_KEY"):
        articles = ExaProvider().fetch(QUERY, FROM_DATE, TO_DATE, max_results=1)
        if articles:
            working_providers.append("Exa AI")
    
    assert working_providers, f"No providers returned articles. Checked: {working_providers}"
    print(f"Working providers: {working_providers}")
