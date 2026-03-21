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
    if not company_name or not ticker:
        logger.warning("Empty company_name or ticker provided for company query")
        return ""
    
    safe_name = company_name.replace('"', "").strip()
    if not safe_name:
        logger.warning("Company name becomes empty after sanitization")
        return f'"{ticker.upper()}" stock'
    
    return f'"{safe_name}" OR "{ticker.upper()}" stock'


def _competitor_query(sector: Optional[str], industry: Optional[str]) -> str:
    """Broad query for sector/industry news."""
    parts = []
    
    if industry:
        industry_clean = industry.strip().replace('"', "")
        if industry_clean:
            parts.append(f'"{industry_clean}"')
        else:
            logger.warning("Industry becomes empty after sanitization")
    
    if sector:
        sector_clean = sector.strip().replace('"', "")
        if sector_clean:
            parts.append(f'"{sector_clean}"')
        else:
            logger.warning("Sector becomes empty after sanitization")
    
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
        logger.debug("NewsAPI key not configured, returning empty results")
        return []
    
    if not query.strip():
        logger.warning("Empty query provided to NewsAPI")
        return []
    
    # Validate date range
    if from_date > to_date:
        logger.error(f"Invalid date range: from_date {from_date} > to_date {to_date}")
        return []
    
    # Validate max_results
    if max_results <= 0:
        logger.warning(f"Invalid max_results {max_results}, using default 10")
        max_results = 10
    elif max_results > 100:
        logger.warning(f"max_results {max_results} exceeds API limit, capping at 100")
        max_results = 100

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
    
        # Validate response structure
        if not isinstance(data, dict):
            logger.error("NewsAPI returned non-dict response")
            return []
        
        if "articles" not in data:
            logger.error("NewsAPI response missing 'articles' field")
            return []
        
        articles_data = data.get("articles", [])
        if not isinstance(articles_data, list):
            logger.error("NewsAPI 'articles' field is not a list")
            return []
        
        logger.debug(f"NewsAPI returned {len(articles_data)} articles for query: {query[:50]}...")
        
    except httpx.HTTPStatusError as e:
        error_msg = f"NewsAPI HTTP error {e.response.status_code}"
        if e.response.status_code == 429:
            error_msg += " - Rate limit exceeded"
            logger.error(
                f"{error_msg}. Response: {e.response.text[:200]}. "
                f"Please check your NewsAPI plan limits and consider reducing request frequency."
            )
        elif e.response.status_code == 401:
            error_msg += " - Invalid API key"
            logger.error(f"{error_msg}. Please check your NEWS_API_KEY environment variable.")
        elif e.response.status_code == 400:
            error_msg += " - Bad request"
            logger.warning(f"{error_msg}: {e.response.text[:200]}. Query: {query[:100]}")
        else:
            logger.warning(f"{error_msg}: {e.response.text[:200]}")
        return []
    except httpx.TimeoutException as e:
        logger.error(f"NewsAPI request timeout after 12s: {e}")
        return []
    except httpx.RequestError as e:
        logger.error(f"NewsAPI request failed: {e}")
        return []
    except ValueError as e:
        logger.error(f"NewsAPI JSON decode error: {e}")
        return []
    except Exception as e:
        logger.exception(f"Unexpected error in NewsAPI request: {e}")
        return []

    articles = []
    for i, a in enumerate(articles_data):
        try:
            title = a.get("title", "") or ""
            if title in ("[Removed]", ""):
                logger.debug(f"Skipping removed/empty article {i}")
                continue
            
            source_obj = a.get("source", {})
            if not isinstance(source_obj, dict):
                logger.debug(f"Invalid source object for article {i}: {source_obj}")
                source_name = "Unknown"
            else:
                source_name = source_obj.get("name", "Unknown") or "Unknown"
            
            url = a.get("url", "")
            if url and not isinstance(url, str):
                logger.debug(f"Invalid URL type for article {i}: {type(url)}")
                url = ""
            
            published_at = _parse_datetime(a.get("publishedAt"))
            
            # Handle summary/content with fallback
            summary = a.get("description", "") or a.get("content", "") or ""
            if isinstance(summary, str):
                summary = summary[:600].strip()
            else:
                logger.debug(f"Invalid summary type for article {i}: {type(summary)}")
                summary = ""
            
            articles.append({
                "title": title.strip(),
                "source": source_name.strip(),
                "url": url or None,
                "published_at": published_at,
                "summary": summary,
            })
            
        except Exception as e:
            logger.warning(f"Error processing article {i}: {e}")
            continue
    
    logger.debug(f"Successfully processed {len(articles)} valid articles")
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
    
    Args:
        movement_date: The date of the stock movement
        company_name: Name of the company (required)
        ticker: Stock ticker symbol (required)
        sector: Optional sector for competitor news
        industry: Optional industry for competitor news
        include_competitors: Whether to fetch competitor/industry news
        include_macro: Whether to fetch macro/political news
        days_before: Days before movement_date to search
        days_after: Days after movement_date to search
        max_per_category: Maximum articles per category
    
    Returns:
        List of normalized article dictionaries with 'category' field
    """
    # Validate inputs
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
    
    logger.debug(f"Fetching news for {ticker} around {movement_date} "
                f"({from_date} to {to_date})")

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
    
    Args:
        from_date: Start date for news search
        to_date: End date for news search
        company_name: Name of the company (required)
        ticker: Stock ticker symbol (required)
        sector: Optional sector for competitor news
        industry: Optional industry for competitor news
        include_competitors: Whether to fetch competitor/industry news
        include_macro: Whether to fetch macro/political news
        max_per_category: Maximum articles per category
    
    Returns:
        List of normalized article dictionaries with 'category' field
    """
    # Validate inputs
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
