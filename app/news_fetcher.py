"""
News fetching module.

Primary source : NewsAPI (https://newsapi.org) — requires NEWSAPI_KEY env var.

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

from newsapi import NewsApiClient
from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)

NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY", "")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5.4-nano")

# How many days before / after a movement to search for news
DEFAULT_DAYS_BEFORE = 2
DEFAULT_DAYS_AFTER = 1


# ── Query builders ────────────────────────────────────────────────────────────

def _company_query(company_name: str, ticker: str) -> str:
    """Simple query targeting the specific company."""
    if not company_name and not ticker:
        logger.warning("Empty company_name and ticker provided for company query")
        return ""

    parts = []
    if company_name:
        safe_name = company_name.replace('"', "").strip()
        if safe_name:
            parts.append(f'"{safe_name}"')
    if ticker:
        parts.append(f'"{ticker.upper()}"')

    return " OR ".join(parts) if parts else ""


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


# ── NewsAPI client ────────────────────────────────────────────────────────────

def _fetch_newsapi(
    query: str,
    from_date: date,
    to_date: date,
    max_results: int = 10,
) -> List[Dict]:
    """Hit the NewsAPI /everything endpoint and return normalised articles."""
    if not NEWSAPI_KEY:
        logger.debug("NewsAPI key not configured, returning empty results")
        return []

    if not query.strip():
        logger.warning("Empty query provided to NewsAPI")
        return []

    if from_date > to_date:
        logger.error(f"Invalid date range: from_date {from_date} > to_date {to_date}")
        return []

    if max_results <= 0:
        logger.warning(f"Invalid max_results {max_results}, using default 10")
        max_results = 10

    try:
        client = NewsApiClient(api_key=NEWSAPI_KEY)
        response = client.get_everything(
            q=query,
            from_param=from_date.isoformat(),
            to=to_date.isoformat(),
            language="en",
            sort_by="relevancy",
            page_size=min(max_results * 3, 100),
        )
    except Exception as e:
        logger.error(f"NewsAPI request failed: {e}")
        return []

    if response.get("status") != "ok":
        logger.error(f"NewsAPI returned error: {response.get('message', 'unknown')}")
        return []

    raw_articles = response.get("articles", []) or []
    logger.debug(f"NewsAPI returned {len(raw_articles)} results for query: {query[:50]}...")

    articles = []
    for i, item in enumerate(raw_articles):
        try:
            title = item.get("title", "") or ""
            if not title or title == "[Removed]":
                continue

            source_obj = item.get("source", {})
            source_name = (source_obj.get("name") or "Unknown") if isinstance(source_obj, dict) else "Unknown"

            url = item.get("url", "") or ""

            published_at = _parse_datetime(item.get("publishedAt"))

            summary = item.get("description") or item.get("content") or ""
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

def has_newsapi_key() -> bool:
    return bool(NEWSAPI_KEY)


def fetch_mock_news_for_movement(
    movement_date: date,
    company_name: str,
    ticker: str,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    include_competitors: bool = False,
    include_macro: bool = False,
    max_per_category: int = 5,
) -> List[Dict]:
    """
    Generate mock news articles for testing purposes.
    
    Returns realistic-looking news articles with categories based on the flags.
    """
    from datetime import timedelta
    import random
    
    mock_articles = []
    
    # Company-specific news
    company_news = [
        {
            "title": f"{company_name} Reports Strong Quarterly Earnings, Stock Surges",
            "source": "Bloomberg",
            "url": f"https://example.com/{ticker.lower()}-earnings",
            "published_at": movement_date,
            "summary": f"{company_name} announced better-than-expected quarterly results, beating analyst estimates on both revenue and earnings per share. The company raised its full-year guidance, citing strong demand across all product lines.",
            "category": "company"
        },
        {
            "title": f"{company_name} Announces New Product Line, Investors React Positively",
            "source": "Reuters",
            "url": f"https://example.com/{ticker.lower()}-product",
            "published_at": movement_date - timedelta(days=1),
            "summary": f"{company_name} unveiled its latest product innovation, promising to revolutionize the market. Analysts believe this could drive significant revenue growth in the coming quarters.",
            "category": "company"
        },
        {
            "title": f"Analysts Upgrade {company_name} Stock on Strong Outlook",
            "source": "CNBC",
            "url": f"https://example.com/{ticker.lower()}-upgrade",
            "published_at": movement_date + timedelta(days=1),
            "summary": f"Major investment banks have upgraded their price targets for {company_name}, citing improved operational efficiency and market positioning. The stock has gained momentum following the positive coverage.",
            "category": "company"
        }
    ]
    
    for article in company_news[:max_per_category]:
        mock_articles.append(article)
    
    # Competitor/industry news
    if include_competitors:
        industry_name = industry or sector or "Technology"
        competitor_news = [
            {
                "title": f"{industry_name} Sector Sees Consolidation Wave",
                "source": "Wall Street Journal",
                "url": "https://example.com/sector-consolidation",
                "published_at": movement_date,
                "summary": f"The {industry_name} industry is undergoing significant consolidation as larger players acquire smaller competitors. This trend is expected to reshape the competitive landscape.",
                "category": "competitor"
            },
            {
                "title": f"Competitor Announces Strategic Partnership in {industry_name}",
                "source": "Financial Times",
                "url": "https://example.com/competitor-partnership",
                "published_at": movement_date - timedelta(days=1),
                "summary": f"A major competitor in the {industry_name} space has formed a strategic partnership to expand its market reach. Industry analysts are watching closely for potential competitive implications.",
                "category": "competitor"
            }
        ]
        
        for article in competitor_news[:max_per_category]:
            mock_articles.append(article)
    
    # Macro news
    if include_macro:
        macro_news = [
            {
                "title": "Federal Reserve Signals Potential Rate Adjustments",
                "source": "Reuters",
                "url": "https://example.com/fed-rates",
                "published_at": movement_date,
                "summary": "The Federal Reserve has indicated it may adjust interest rates in the coming months based on economic data. Markets are reacting to the possibility of changes in monetary policy.",
                "category": "macro"
            },
            {
                "title": "Inflation Data Shows Mixed Signals Across Economy",
                "source": "Bloomberg",
                "url": "https://example.com/inflation-data",
                "published_at": movement_date - timedelta(days=1),
                "summary": "Latest inflation readings present a mixed picture, with some sectors showing price stability while others continue to experience upward pressure. Economists are divided on the implications for future policy.",
                "category": "macro"
            }
        ]
        
        for article in macro_news[:max_per_category]:
            mock_articles.append(article)
    
    return mock_articles


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
        q = _llm_competitor_query(company_name, ticker, sector, industry)
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
        q = _llm_competitor_query(company_name, ticker, sector, industry)
        for a in _fetch_newsapi(q, from_date, to_date, max_per_category):
            a["category"] = "competitor"
            all_articles.append(a)

    if include_macro:
        for a in _fetch_newsapi(_macro_query(), from_date, to_date, max_per_category):
            a["category"] = "macro"
            all_articles.append(a)

    return all_articles
