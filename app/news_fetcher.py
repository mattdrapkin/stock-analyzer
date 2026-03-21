"""
News fetching module.

Primary source : NewsAPI (https://newsapi.org) — requires NEWS_API_KEY env var.
Fallback source: yfinance built-in Yahoo Finance news feed (no key needed,
                 but returns only the ~10 most recent articles with no
                 date-range filtering).

News categories
---------------
- company   (easy)   : company-specific events — earnings, launches, lawsuits
- competitor (medium): sector/industry moves, competitor earnings
- macro      (hard)  : Fed, rates, inflation, geopolitical events
"""

import os
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
NEWSAPI_BASE: str = "https://newsapi.org/v2/everything"

# How many days before / after a movement to search for news
DEFAULT_DAYS_BEFORE = 2
DEFAULT_DAYS_AFTER = 1


# ── Query builders ────────────────────────────────────────────────────────────

def _company_query(company_name: str, ticker: str) -> str:
    """Narrow query targeting the specific company."""
    safe_name = company_name.replace('"', "")
    return f'"{safe_name}" OR "{ticker.upper()}" stock'


def _competitor_query(sector: Optional[str], industry: Optional[str]) -> str:
    """Broad query for sector/industry news."""
    parts = []
    if industry:
        parts.append(f'"{industry}"')
    if sector:
        parts.append(f'"{sector}"')
    base = " OR ".join(parts) if parts else "stock market"
    return f"({base}) AND (earnings OR merger OR acquisition OR results OR outlook)"


def _macro_query() -> str:
    """Query for macro / political events that move markets."""
    return (
        "Federal Reserve OR interest rate OR inflation OR GDP OR recession "
        "OR trade war OR tariff OR geopolitical OR central bank OR rate hike "
        "OR rate cut OR jobs report OR unemployment"
    )


# ── NewsAPI client ────────────────────────────────────────────────────────────

def _fetch_newsapi(
    query: str,
    from_date: date,
    to_date: date,
    max_results: int = 10,
) -> List[Dict]:
    """Hit the NewsAPI /everything endpoint and return normalised articles."""
    if not NEWS_API_KEY:
        return []

    params = {
        "q": query,
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
        "language": "en",
        "sortBy": "relevancy",
        "pageSize": min(max_results, 100),
        "apiKey": NEWS_API_KEY,
    }

    try:
        with httpx.Client(timeout=12) as client:
            resp = client.get(NEWSAPI_BASE, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning(f"NewsAPI HTTP error {e.response.status_code}: {e.response.text[:200]}")
        return []
    except Exception as e:
        logger.warning(f"NewsAPI request failed: {e}")
        return []

    articles = []
    for a in data.get("articles", []):
        title = a.get("title", "") or ""
        if title in ("[Removed]", ""):
            continue
        articles.append(
            {
                "title": title,
                "source": (a.get("source") or {}).get("name", "Unknown"),
                "url": a.get("url", ""),
                "published_at": _parse_datetime(a.get("publishedAt")),
                "summary": (a.get("description") or a.get("content") or "")[:600],
            }
        )
    return articles


def _parse_datetime(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


# ── Public interface ──────────────────────────────────────────────────────────

def has_newsapi_key() -> bool:
    return bool(NEWS_API_KEY)


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
    """
    Fetch news articles relevant to a single major-movement day.

    Searches a window of [movement_date - days_before, movement_date + days_after]
    across up to three categories depending on the flags passed.
    """
    from_date = movement_date - timedelta(days=days_before)
    to_date = movement_date + timedelta(days=days_after)

    all_articles: List[Dict] = []

    # ── Company-specific (always on) ─────────────────────────────────────────
    q = _company_query(company_name, ticker)
    for a in _fetch_newsapi(q, from_date, to_date, max_per_category):
        a["category"] = "company"
        all_articles.append(a)

    # ── Competitor / industry (medium) ────────────────────────────────────────
    if include_competitors:
        q = _competitor_query(sector, industry)
        for a in _fetch_newsapi(q, from_date, to_date, max_per_category):
            a["category"] = "competitor"
            all_articles.append(a)

    # ── Macro / political (hard) ──────────────────────────────────────────────
    if include_macro:
        for a in _fetch_newsapi(_macro_query(), from_date, to_date, max_per_category):
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
    """
    Fetch news for an entire date range (used to build LLM chat context).
    Similar to fetch_news_for_movement but over a wider window.
    """
    all_articles: List[Dict] = []

    q = _company_query(company_name, ticker)
    for a in _fetch_newsapi(q, from_date, to_date, max_per_category):
        a["category"] = "company"
        all_articles.append(a)

    if include_competitors:
        q = _competitor_query(sector, industry)
        for a in _fetch_newsapi(q, from_date, to_date, max_per_category):
            a["category"] = "competitor"
            all_articles.append(a)

    if include_macro:
        for a in _fetch_newsapi(_macro_query(), from_date, to_date, max_per_category):
            a["category"] = "macro"
            all_articles.append(a)

    return all_articles
