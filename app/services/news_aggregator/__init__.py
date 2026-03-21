"""News aggregator package.

Provides a unified interface for fetching news across multiple providers
(NewsAPI, GNews, Jina AI, Exa AI) with automatic fallback between them.

Public interface
----------------
fetch_news_for_movement  — fetch news around a specific movement date
fetch_news_for_period    — fetch news over a date range
has_any_news_key         — True if at least one provider is configured
get_configured_providers — names of all configured providers in priority order
"""

from .aggregator import (
    fetch_news_for_movement,
    fetch_news_for_period,
    has_any_news_key,
    get_configured_providers,
)

__all__ = [
    "fetch_news_for_movement",
    "fetch_news_for_period",
    "has_any_news_key",
    "get_configured_providers",
]
