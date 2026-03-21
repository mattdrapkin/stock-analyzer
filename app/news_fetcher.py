"""
News fetching module.

Primary source : SerpAPI Google News (https://serpapi.com) — requires SERPAPI_KEY env var.

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

import serpapi
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)

SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5.4-nano")

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


def _llm_competitor_query(
    company_name: str,
    ticker: str,
    sector: Optional[str],
    industry: Optional[str],
) -> str:
    """Use GPT to identify specific public competitors and build a targeted search query."""
    if not OPENAI_API_KEY:
        return _competitor_query(sector, industry)

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        prompt = (
            f"You are a financial research assistant. Given the company '{company_name}' "
            f"(ticker: {ticker}), sector: {sector or 'unknown'}, industry: {industry or 'unknown'}, "
            f"list the 4-5 most direct publicly-traded competitors by company name. "
            f"Return ONLY a comma-separated list of company names, nothing else. "
            f"Example format: Apple, Microsoft, Google, Meta"
        )
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        competitors_str = response.choices[0].message.content.strip()
        competitors = [c.strip() for c in competitors_str.split(",") if c.strip()]
        if not competitors:
            return _competitor_query(sector, industry)
        name_parts = " OR ".join(f'"{c}"' for c in competitors[:5])
        logger.debug(f"LLM competitor query for {ticker}: {name_parts}")
        return f"({name_parts}) AND (earnings OR merger OR acquisition OR results OR outlook OR stock)"
    except (OpenAIError, Exception) as e:
        logger.warning(f"LLM competitor query failed, falling back to static: {e}")
        return _competitor_query(sector, industry)


def _llm_macro_query(
    company_name: str,
    ticker: str,
    sector: Optional[str],
    industry: Optional[str],
) -> str:
    """Use GPT to generate a sophisticated macro/economic query tailored to the company's sector."""
    if not OPENAI_API_KEY:
        return _macro_query()

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        prompt = (
            f"You are a financial research assistant. Given the company '{company_name}' "
            f"(ticker: {ticker}), sector: {sector or 'unknown'}, industry: {industry or 'unknown'}, "
            f"generate a Google News search query string using OR/AND operators that captures "
            f"the most relevant macroeconomic trends, regulatory changes, and geopolitical factors "
            f"that would most affect this specific company's stock price. "
            f"Focus on factors specific to this sector and industry rather than generic macro terms. "
            f"Return ONLY the raw search query string, no explanation, no surrounding quotes."
        )
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        query = response.choices[0].message.content.strip().strip('"')
        if not query:
            return _macro_query()
        logger.debug(f"LLM macro query for {ticker}: {query}")
        return query
    except (OpenAIError, Exception) as e:
        logger.warning(f"LLM macro query failed, falling back to static: {e}")
        return _macro_query()


# ── SerpAPI client ────────────────────────────────────────────────────────────

def _fetch_serpapi(
    query: str,
    from_date: date,
    to_date: date,
    max_results: int = 10,
) -> List[Dict]:
    """Hit the SerpAPI Google News endpoint and return normalised articles."""
    if not SERPAPI_KEY:
        logger.debug("SerpAPI key not configured, returning empty results")
        return []

    if not query.strip():
        logger.warning("Empty query provided to SerpAPI")
        return []

    if from_date > to_date:
        logger.error(f"Invalid date range: from_date {from_date} > to_date {to_date}")
        return []

    if max_results <= 0:
        logger.warning(f"Invalid max_results {max_results}, using default 10")
        max_results = 10

    dated_query = f"{query} after:{from_date.isoformat()} before:{to_date.isoformat()}"

    try:
        client = serpapi.Client(api_key=SERPAPI_KEY)
        results = client.search({
            "engine": "google_news",
            "q": dated_query,
            "hl": "en",
            "gl": "us",
        })
        news_results = results.get("news_results", [])
    except Exception as e:
        logger.error(f"SerpAPI request failed: {e}")
        return []

    if not isinstance(news_results, list):
        logger.error("SerpAPI returned non-list news_results")
        return []

    logger.debug(f"SerpAPI returned {len(news_results)} results for query: {query[:50]}...")

    from_dt = datetime(from_date.year, from_date.month, from_date.day, 0, 0, 0)
    to_dt = datetime(to_date.year, to_date.month, to_date.day, 23, 59, 59)

    articles = []
    for i, item in enumerate(news_results):
        try:
            title = item.get("title", "") or ""
            if not title:
                logger.debug(f"Skipping article {i} with empty title")
                continue

            source_obj = item.get("source", {})
            if not isinstance(source_obj, dict):
                source_name = "Unknown"
            else:
                source_name = source_obj.get("name", "Unknown") or "Unknown"

            url = item.get("link", "") or ""
            if url and not isinstance(url, str):
                url = ""

            published_at = _parse_datetime(item.get("iso_date"))

            # Client-side date filtering
            if published_at and not (from_dt <= published_at <= to_dt):
                logger.debug(f"Skipping article outside date window: {published_at}")
                continue

            summary = item.get("snippet", "") or ""
            if isinstance(summary, str):
                summary = summary[:600].strip()
            else:
                summary = ""

            articles.append({
                "title": title.strip(),
                "source": source_name.strip(),
                "url": url or None,
                "published_at": published_at,
                "summary": summary,
            })

            if len(articles) >= max_results:
                break

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

def has_serpapi_key() -> bool:
    return bool(SERPAPI_KEY)


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
    for a in _fetch_serpapi(q, from_date, to_date, max_per_category):
        a["category"] = "company"
        all_articles.append(a)

    # ── Competitor / industry (medium) ────────────────────────────────────────
    if include_competitors:
        q = _llm_competitor_query(company_name, ticker, sector, industry)
        for a in _fetch_serpapi(q, from_date, to_date, max_per_category):
            a["category"] = "competitor"
            all_articles.append(a)

    # ── Macro / political (hard) ──────────────────────────────────────────────
    if include_macro:
        for a in _fetch_serpapi(_llm_macro_query(company_name, ticker, sector, industry), from_date, to_date, max_per_category):
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
    for a in _fetch_serpapi(q, from_date, to_date, max_per_category):
        a["category"] = "company"
        all_articles.append(a)

    if include_competitors:
        q = _llm_competitor_query(company_name, ticker, sector, industry)
        for a in _fetch_serpapi(q, from_date, to_date, max_per_category):
            a["category"] = "competitor"
            all_articles.append(a)

    if include_macro:
        for a in _fetch_serpapi(_llm_macro_query(company_name, ticker, sector, industry), from_date, to_date, max_per_category):
            a["category"] = "macro"
            all_articles.append(a)

    return all_articles
