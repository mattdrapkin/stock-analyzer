"""Compatibility shim — the news fetching logic now lives in
app.services.news_aggregator.  Import from there for new code.
"""

from .services.news_aggregator import (
    fetch_news_for_movement,
    fetch_news_for_period,
    has_any_news_key,
    get_configured_providers,
)
from .services.news_aggregator.providers.newsapi import NewsAPIProvider as _NewsAPIProvider


def has_newsapi_key() -> bool:
    """Return True if NEWS_API_KEY is configured (backward-compat helper)."""
    return _NewsAPIProvider().is_available()


__all__ = [
    "fetch_news_for_movement",
    "fetch_news_for_period",
    "has_newsapi_key",
    "has_any_news_key",
    "get_configured_providers",
]
