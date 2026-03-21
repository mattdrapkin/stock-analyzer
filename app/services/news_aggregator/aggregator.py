"""News aggregator with provider fallback logic.

Provider priority: NewsAPI → GNews → Jina AI → Exa AI

For each query, providers are tried in order until one returns results.
If all configured providers fail or return nothing, an empty list is returned.
"""

import logging
from datetime import date, timedelta
from typing import List, Dict, Optional

from .providers.newsapi import NewsAPIProvider
from .providers.gnews import GNewsProvider
from .providers.jina import JinaProvider
from .providers.exa import ExaProvider
from .queries import company_query, competitor_query, macro_query

logger = logging.getLogger(__name__)

DEFAULT_DAYS_BEFORE = 2
DEFAULT_DAYS_AFTER = 1

_PROVIDERS = [
    NewsAPIProvider(),
    GNewsProvider(),
    JinaProvider(),
    ExaProvider(),
]


def _fetch_with_fallback(
    query: str,
    from_date: date,
    to_date: date,
    max_results: int = 10,
) -> List[Dict]:
    """Try each configured provider in priority order.

    Returns the first non-empty result set.  Falls back to the next provider
    when a provider is unconfigured, raises an exception, or returns no results.
    """
    if not query.strip():
        logger.warning("Empty query provided to news aggregator")
        return []

    for provider in _PROVIDERS:
        if not provider.is_available():
            continue
        try:
            results = provider.fetch(query, from_date, to_date, max_results)
            if results:
                logger.debug(
                    f"[{provider.name}] returned {len(results)} articles — "
                    f"query: {query[:60]!r}"
                )
                return results
            logger.debug(
                f"[{provider.name}] returned no results, trying next provider"
            )
        except Exception as e:
            logger.warning(
                f"[{provider.name}] raised unexpected error: {e} — trying next provider"
            )

    logger.warning(f"All providers exhausted with no results for query: {query[:80]!r}")
    return []


# ── Public helpers ─────────────────────────────────────────────────────────────

def has_any_news_key() -> bool:
    """Return True if at least one news provider is configured."""
    return any(p.is_available() for p in _PROVIDERS)


def get_configured_providers() -> List[str]:
    """Return names of all currently configured providers, in priority order."""
    return [p.name for p in _PROVIDERS if p.is_available()]


# ── Public fetch functions ─────────────────────────────────────────────────────

def fetch_news_for_movement(
    movement_date: date,
    company_name: str,
    ticker: str,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    include_competitors: bool = False,
    include_macro: bool = False,
    days_before: int = DEFAULT_DAYS_BEFORE,
    days_after: int = DEFAULT_DAYS_AFTER,
    max_per_category: int = 5,
) -> List[Dict]:
    """Fetch news articles relevant to a single major-movement day.

    Searches [movement_date - days_before, movement_date + days_after] across
    up to three categories.  Providers are tried in fallback order per query.

    Args:
        movement_date: The date of the stock movement.
        company_name: Name of the company (required).
        ticker: Stock ticker symbol (required).
        sector: Optional sector for competitor news.
        industry: Optional industry for competitor news.
        include_competitors: Whether to fetch competitor/industry news.
        include_macro: Whether to fetch macro/political news.
        days_before: Days before movement_date to search.
        days_after: Days after movement_date to search.
        max_per_category: Maximum articles per category.

    Returns:
        List of normalised article dicts, each with an added 'category' field.
    """
    if not company_name or not ticker:
        logger.error("company_name and ticker are required for news fetching")
        return []

    if days_before < 0 or days_after < 0:
        logger.error(f"Invalid days_before/days_after: {days_before}/{days_after}")
        return []

    if max_per_category <= 0:
        logger.warning(f"Invalid max_per_category {max_per_category}, using default 5")
        max_per_category = 5

    from_date = movement_date - timedelta(days=days_before)
    to_date = movement_date + timedelta(days=days_after)

    logger.debug(
        f"Fetching news for {ticker} around {movement_date} ({from_date} to {to_date})"
    )

    all_articles: List[Dict] = []

    q = company_query(company_name, ticker)
    for a in _fetch_with_fallback(q, from_date, to_date, max_per_category):
        a["category"] = "company"
        all_articles.append(a)

    if include_competitors:
        q = competitor_query(sector, industry)
        for a in _fetch_with_fallback(q, from_date, to_date, max_per_category):
            a["category"] = "competitor"
            all_articles.append(a)

    if include_macro:
        for a in _fetch_with_fallback(macro_query(), from_date, to_date, max_per_category):
            a["category"] = "macro"
            all_articles.append(a)

    return all_articles


def fetch_news_for_period(
    from_date: date,
    to_date: date,
    company_name: str,
    ticker: str,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    include_competitors: bool = False,
    include_macro: bool = False,
    max_per_category: int = 10,
) -> List[Dict]:
    """Fetch news for an entire date range (used to build LLM chat context).

    Args:
        from_date: Start date for news search.
        to_date: End date for news search.
        company_name: Name of the company (required).
        ticker: Stock ticker symbol (required).
        sector: Optional sector for competitor news.
        industry: Optional industry for competitor news.
        include_competitors: Whether to fetch competitor/industry news.
        include_macro: Whether to fetch macro/political news.
        max_per_category: Maximum articles per category.

    Returns:
        List of normalised article dicts, each with an added 'category' field.
    """
    if not company_name or not ticker:
        logger.error("company_name and ticker are required for news fetching")
        return []

    if from_date > to_date:
        logger.error(f"Invalid date range: from_date {from_date} > to_date {to_date}")
        return []

    if max_per_category <= 0:
        logger.warning(f"Invalid max_per_category {max_per_category}, using default 10")
        max_per_category = 10

    logger.debug(f"Fetching news for {ticker} from {from_date} to {to_date}")
    all_articles: List[Dict] = []

    q = company_query(company_name, ticker)
    for a in _fetch_with_fallback(q, from_date, to_date, max_per_category):
        a["category"] = "company"
        all_articles.append(a)

    if include_competitors:
        q = competitor_query(sector, industry)
        for a in _fetch_with_fallback(q, from_date, to_date, max_per_category):
            a["category"] = "competitor"
            all_articles.append(a)

    if include_macro:
        for a in _fetch_with_fallback(macro_query(), from_date, to_date, max_per_category):
            a["category"] = "macro"
            all_articles.append(a)

    return all_articles
