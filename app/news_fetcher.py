"""
News fetching module using OpenAI Responses API with web_search tool.

This module leverages OpenAI's web search capability to find relevant news
with direct source citations and AI-generated summaries.

News categories
---------------
- company   (easy)   : company-specific events — earnings, launches, lawsuits
- competitor (medium): sector/industry moves, competitor earnings
- macro      (hard)  : Fed, rates, inflation, geopolitical events
"""

import os
import logging
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple

from openai import OpenAI, OpenAIError

logger = logging.getLogger(__name__)

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_SEARCH_MODEL: str = os.getenv("OPENAI_SEARCH_MODEL", "gpt-5-search-api")

# How many days before / after a movement to search for news
DEFAULT_DAYS_BEFORE = 2
DEFAULT_DAYS_AFTER = 1


# ── Query builders ────────────────────────────────────────────────────────────

def _build_company_search_prompt(
    company_name: str,
    ticker: str,
    movement_date: date,
    from_date: date,
    to_date: date,
) -> str:
    """Build search prompt for company-specific news."""
    return (
        f"Find recent news articles about {company_name} ({ticker}) "
        f"between {from_date.isoformat()} and {to_date.isoformat()}. "
        f"Focus on company-specific events like earnings reports, product launches, "
        f"executive changes, lawsuits, regulatory actions, or major announcements "
        f"that could explain stock price movements around {movement_date.isoformat()}."
    )


def _build_competitor_search_prompt(
    company_name: str,
    ticker: str,
    sector: Optional[str],
    industry: Optional[str],
    movement_date: date,
    from_date: date,
    to_date: date,
) -> str:
    """Build search prompt for competitor/industry news."""
    industry_info = industry or sector or "the industry"
    return (
        f"Find news about competitors and industry trends in {industry_info} "
        f"between {from_date.isoformat()} and {to_date.isoformat()}. "
        f"Focus on competitor earnings, mergers, acquisitions, market share changes, "
        f"or sector-wide developments that could impact {company_name} ({ticker}) "
        f"around {movement_date.isoformat()}."
    )


def _build_macro_search_prompt(
    movement_date: date,
    from_date: date,
    to_date: date,
) -> str:
    """Build search prompt for macro/geopolitical news."""
    return (
        f"Find major macroeconomic and geopolitical news between "
        f"{from_date.isoformat()} and {to_date.isoformat()}. "
        f"Focus on Federal Reserve decisions, interest rate changes, inflation data, "
        f"GDP reports, unemployment figures, trade policy, tariffs, or major "
        f"geopolitical events that could impact stock markets around {movement_date.isoformat()}."
    )


# ── OpenAI Chat Completions with web search ────────────────────────────────────

def _batch_search_with_openai(
    company_name: str,
    ticker: str,
    from_date: date,
    to_date: date,
    include_competitors: bool = False,
    include_macro: bool = False,
) -> Dict[str, Tuple[str, List[str]]]:
    """
    Perform a single batch web search for a ticker across the entire date range.
    This is much more efficient than searching per-movement.
    
    Returns:
        Dict mapping category to (ai_summary, sources) tuples
    """
    if not OPENAI_API_KEY:
        logger.debug("OpenAI API key not configured, returning empty results")
        return {}
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Build a comprehensive search prompt for the entire period
        prompt_parts = [
            f"Find and summarize all major news about {company_name} ({ticker}) "
            f"between {from_date.isoformat()} and {to_date.isoformat()}. "
            f"Focus on events that could explain significant stock price movements: "
            f"earnings reports, product launches, executive changes, lawsuits, "
            f"regulatory actions, or major announcements."
        ]
        
        if include_competitors:
            prompt_parts.append(
                " Also include competitor and industry news that could impact the stock."
            )
        
        if include_macro:
            prompt_parts.append(
                " Also include major macroeconomic events (Fed decisions, interest rates, "
                "inflation, geopolitical events) that could impact stock markets."
            )
        
        prompt_parts.append(
            " Provide a comprehensive summary organized by date, with direct source URLs. "
            "Focus on the most impactful news events."
        )
        
        prompt = " ".join(prompt_parts)
        
        response = client.chat.completions.create(
            model=OPENAI_SEARCH_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a financial research assistant. Search for and summarize relevant news articles across a time period. Always include direct source URLs in your response. Organize by date and focus on the most impactful events."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
        )
        
        ai_summary = response.choices[0].message.content or ""
        
        # Extract sources
        import re
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = list(set(re.findall(url_pattern, ai_summary)))
        
        # Return as a single "company" category summary
        return {
            "company": (ai_summary, urls)
        }
        
    except OpenAIError as e:
        logger.error(f"OpenAI batch web search failed: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error in batch web search: {e}")
        return {}


def _search_with_openai(
    search_prompt: str,
    category: str,
) -> Tuple[str, List[str], List[str]]:
    """
    Use OpenAI Chat Completions API with search-enabled model to find news.
    
    Returns:
        Tuple of (ai_summary, sources, search_queries)
    """
    if not OPENAI_API_KEY:
        logger.debug("OpenAI API key not configured, returning empty results")
        return ("", [], [])

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Use Chat Completions with search-enabled model
        # Search-enabled models automatically perform web search and include citations
        response = client.chat.completions.create(
            model=OPENAI_SEARCH_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a financial research assistant. Search for and summarize relevant news articles. Always include direct source URLs in your response."
                },
                {
                    "role": "user",
                    "content": search_prompt
                }
            ],
        )
        
        ai_summary = response.choices[0].message.content or ""
        
        # Extract sources from the response if available
        sources = []
        search_queries = []
        
        # Search models typically include citations in the response
        # We'll parse URLs from the summary as a fallback
        import re
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, ai_summary)
        sources = list(set(urls))  # Deduplicate
        
        logger.debug(f"Web search for {category}: found {len(sources)} sources")
        return (ai_summary, sources, search_queries)
        
    except OpenAIError as e:
        logger.error(f"OpenAI web search failed for {category}: {e}")
        return ("", [], [])
    except Exception as e:
        logger.error(f"Unexpected error in web search for {category}: {e}")
        return ("", [], [])


# ── Public interface ──────────────────────────────────────────────────────────

def has_openai_key() -> bool:
    return bool(OPENAI_API_KEY)


def fetch_batch_news_for_period(
    company_name: str,
    ticker: str,
    from_date: date,
    to_date: date,
    include_competitors: bool = False,
    include_macro: bool = False,
) -> List[Dict]:
    """
    Fetch news summaries for an entire date range in a single batch query.
    This is much more efficient than per-movement queries and avoids rate limits.
    
    Returns:
        List of summary dictionaries with 'category', 'ai_summary', 'sources'
    """
    if not OPENAI_API_KEY:
        logger.warning("OpenAI API key not configured, cannot fetch news summaries")
        return []
    
    if not company_name or not ticker:
        logger.error("company_name and ticker are required for news fetching")
        return []
    
    if from_date > to_date:
        logger.error(f"Invalid date range: from_date {from_date} > to_date {to_date}")
        return []
    
    logger.debug(f"Fetching batch news for {ticker} from {from_date} to {to_date}")
    
    results = _batch_search_with_openai(
        company_name=company_name,
        ticker=ticker,
        from_date=from_date,
        to_date=to_date,
        include_competitors=include_competitors,
        include_macro=include_macro,
    )
    
    summaries = []
    for category, (ai_summary, sources) in results.items():
        if ai_summary:
            summaries.append({
                "category": category,
                "ai_summary": ai_summary,
                "sources": sources,
                "search_queries": [],
            })
    
    return summaries


def fetch_news_summaries_for_movement(
    movement_date: date,
    company_name: str,
    ticker: str,
    sector: Optional[str] = None,
    industry: Optional[str] = None,
    include_competitors: bool = False,
    include_macro: bool = False,
    days_before: int = DEFAULT_DAYS_BEFORE,
    days_after: int = DEFAULT_DAYS_AFTER,
) -> List[Dict]:
    """
    Fetch AI-generated news summaries with citations using OpenAI web search.
    
    Returns a list of summary dictionaries with:
    - category: NewsCategory value
    - ai_summary: AI-generated summary text
    - sources: List of source URLs
    - search_queries: List of search queries used
    """
    if not OPENAI_API_KEY:
        logger.warning("OpenAI API key not configured, cannot fetch news summaries")
        return []
    
    if not company_name or not ticker:
        logger.error("company_name and ticker are required for news fetching")
        return []
    
    from_date = movement_date - timedelta(days=days_before)
    to_date = movement_date + timedelta(days=days_after)
    
    logger.debug(f"Fetching news summaries for {ticker} around {movement_date} "
                f"({from_date} to {to_date})")
    
    summaries = []
    
    # Company-specific news (always included)
    company_prompt = _build_company_search_prompt(
        company_name, ticker, movement_date, from_date, to_date
    )
    ai_summary, sources, queries = _search_with_openai(company_prompt, "company")
    if ai_summary:
        summaries.append({
            "category": "company",
            "ai_summary": ai_summary,
            "sources": sources,
            "search_queries": queries,
        })
    
    # Competitor/industry news
    if include_competitors:
        competitor_prompt = _build_competitor_search_prompt(
            company_name, ticker, sector, industry, movement_date, from_date, to_date
        )
        ai_summary, sources, queries = _search_with_openai(competitor_prompt, "competitor")
        if ai_summary:
            summaries.append({
                "category": "competitor",
                "ai_summary": ai_summary,
                "sources": sources,
                "search_queries": queries,
            })
    
    # Macro news
    if include_macro:
        macro_prompt = _build_macro_search_prompt(movement_date, from_date, to_date)
        ai_summary, sources, queries = _search_with_openai(macro_prompt, "macro")
        if ai_summary:
            summaries.append({
                "category": "macro",
                "ai_summary": ai_summary,
                "sources": sources,
                "search_queries": queries,
            })
    
    return summaries


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
    Fetch news summaries using OpenAI web search.
    
    This is now a wrapper around fetch_news_summaries_for_movement for backward compatibility.
    Returns summaries instead of individual articles.
    
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
        max_per_category: Ignored (kept for backward compatibility)
    
    Returns:
        List of summary dictionaries with 'category', 'ai_summary', 'sources', 'search_queries'
    """
    return fetch_news_summaries_for_movement(
        movement_date=movement_date,
        company_name=company_name,
        ticker=ticker,
        sector=sector,
        industry=industry,
        include_competitors=include_competitors,
        include_macro=include_macro,
        days_before=days_before,
        days_after=days_after,
    )


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
    Fetch news summaries for an entire date range using OpenAI web search.
    
    Args:
        from_date: Start date for news search
        to_date: End date for news search
        company_name: Name of the company (required)
        ticker: Stock ticker symbol (required)
        sector: Optional sector for competitor news
        industry: Optional industry for competitor news
        include_competitors: Whether to fetch competitor/industry news
        include_macro: Whether to fetch macro/political news
        max_per_category: Ignored (kept for backward compatibility)
    
    Returns:
        List of summary dictionaries with 'category', 'ai_summary', 'sources', 'search_queries'
    """
    if not OPENAI_API_KEY:
        logger.warning("OpenAI API key not configured, cannot fetch news summaries")
        return []
    
    if not company_name or not ticker:
        logger.error("company_name and ticker are required for news fetching")
        return []
    
    if from_date > to_date:
        logger.error(f"Invalid date range: from_date {from_date} > to_date {to_date}")
        return []
    
    logger.debug(f"Fetching news summaries for {ticker} from {from_date} to {to_date}")
    
    summaries = []
    
    # Company-specific news
    company_prompt = _build_company_search_prompt(
        company_name, ticker, to_date, from_date, to_date
    )
    ai_summary, sources, queries = _search_with_openai(company_prompt, "company")
    if ai_summary:
        summaries.append({
            "category": "company",
            "ai_summary": ai_summary,
            "sources": sources,
            "search_queries": queries,
        })
    
    # Competitor/industry news
    if include_competitors:
        competitor_prompt = _build_competitor_search_prompt(
            company_name, ticker, sector, industry, to_date, from_date, to_date
        )
        ai_summary, sources, queries = _search_with_openai(competitor_prompt, "competitor")
        if ai_summary:
            summaries.append({
                "category": "competitor",
                "ai_summary": ai_summary,
                "sources": sources,
                "search_queries": queries,
            })
    
    # Macro news
    if include_macro:
        macro_prompt = _build_macro_search_prompt(to_date, from_date, to_date)
        ai_summary, sources, queries = _search_with_openai(macro_prompt, "macro")
        if ai_summary:
            summaries.append({
                "category": "macro",
                "ai_summary": ai_summary,
                "sources": sources,
                "search_queries": queries,
            })
    
    return summaries
