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
import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple

from openai import OpenAI, OpenAIError

from .rate_limit_utils import RateLimitError, is_rate_limit_error, create_rate_limit_error, get_rate_limiter, retry_with_exponential_backoff

logger = logging.getLogger(__name__)

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_SEARCH_MODEL: str = os.getenv("OPENAI_SEARCH_MODEL", "gpt-5.5")
OPENAI_SEARCH_CONTEXT_SIZE: str = os.getenv("OPENAI_SEARCH_CONTEXT_SIZE", "medium")

# How many days before / after a movement to search for news
DEFAULT_DAYS_BEFORE = 2
DEFAULT_DAYS_AFTER = 1


# ── Structured JSON prompt ────────────────────────────────────────────────────

STRUCTURED_NEWS_SYSTEM_PROMPT = """\
You are a financial research assistant with real-time web search access.
Your task is to find news articles that explain a stock's price movements.

You MUST respond ONLY with a valid JSON object — no markdown, no code blocks, no preamble.

Required JSON format:
{
  "articles": [
    {
      "title": "Exact headline of the article",
      "summary": "One sentence capturing the key investment takeaway",
      "date": "YYYY-MM-DD",
      "source_name": "Publication name (e.g. Bloomberg, Reuters, WSJ, CNBC)",
      "url": "https://full-url-to-article",
      "category": "company",
      "relevance": "One sentence explaining why this likely impacted the stock price"
    }
  ]
}

Rules:
- Return 5 to 10 of the most impactful articles ordered by date descending
- category must be exactly one of: "company", "competitor", "macro"
- date must be in YYYY-MM-DD format, or null if unknown
- url must be a real, complete URL starting with https://, or null if unavailable
- title, summary, and relevance must be non-empty strings
- Do not include any text outside the JSON object
"""


def _parse_news_cards_from_response(content: str) -> List[Dict]:
    """Parse structured news cards from an OpenAI JSON response."""
    if not content:
        return []

    text = content.strip()
    # Strip markdown code fences if the model wrapped the JSON
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
        text = text.strip()

    # Store original content for error logging
    response_content = text

    try:
        data = json.loads(text)
        articles = data.get("articles", [])
        if not isinstance(articles, list):
            return []

        validated: List[Dict] = []
        for article in articles:
            if not isinstance(article, dict):
                continue
            title = (article.get("title") or "").strip()
            summary = (article.get("summary") or "").strip()
            if not title or not summary:
                logger.debug(f"Skipping article with missing title or summary: {article}")
                continue

            cat = article.get("category", "company")
            if cat not in ("company", "competitor", "macro"):
                cat = "company"

            url = article.get("url") or None
            if url and not url.startswith("http"):
                url = None

            # Normalize date to YYYY-MM-DD format
            date_str = article.get("date")
            if date_str:
                parsed_date_str = date_str
                try:
                    # Try YYYY-MM-DD format first
                    parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    parsed_date_str = parsed_date.isoformat()
                except ValueError:
                    try:
                        # Try other common formats
                        for fmt in ("%B %d, %Y", "%d %B %Y", "%m/%d/%Y", "%Y/%m/%d"):
                            try:
                                parsed_date = datetime.strptime(date_str, fmt).date()
                                parsed_date_str = parsed_date.isoformat()
                                break
                            except ValueError:
                                continue
                        else:
                            # All formats failed
                            logger.debug(f"Could not parse date '{date_str}', setting to None")
                            parsed_date_str = None
                    except Exception:
                        logger.debug(f"Error parsing date '{date_str}', setting to None")
                        parsed_date_str = None
                date_str = parsed_date_str

            validated.append({
                "title": title,
                "summary": summary,
                "date": date_str,
                "source_name": (article.get("source_name") or "").strip() or None,
                "url": url,
                "category": cat,
                "relevance": (article.get("relevance") or "").strip() or None,
            })
        return validated
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"Failed to parse structured news cards from OpenAI response: {e}")
        logger.debug(f"Response content that failed parsing: {response_content[:500] if 'response_content' in locals() else 'N/A'}")
        return []


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


# ── Responses API output parsing ─────────────────────────────────────────────

def _extract_from_response(response) -> Tuple[str, List[str], List[str]]:
    """
    Parse a Responses API response object.

    The output list contains two item types (per API docs):
      - web_search_call  → exposes the search query via action.query
      - message          → contains assistant text (output_text) and
                           url_citation annotations

    Returns:
        Tuple of (text, source_urls, search_queries)
    """
    text = ""
    source_urls: List[str] = []
    search_queries: List[str] = []

    if not hasattr(response, "output") or not response.output:
        return text, source_urls, search_queries

    for item in response.output:
        item_type = getattr(item, "type", None)

        if item_type == "web_search_call":
            action = getattr(item, "action", None)
            if action:
                query = getattr(action, "query", None)
                if query:
                    search_queries.append(query)

        elif item_type == "message":
            content_list = getattr(item, "content", None) or []
            for block in content_list:
                if getattr(block, "type", None) == "output_text":
                    text = getattr(block, "text", "") or ""
                    for ann in (getattr(block, "annotations", None) or []):
                        if getattr(ann, "type", None) == "url_citation":
                            url = getattr(ann, "url", None)
                            if url:
                                source_urls.append(url)

    source_urls = list(dict.fromkeys(source_urls))      # deduplicate, preserve order
    search_queries = list(dict.fromkeys(search_queries))
    return text, source_urls, search_queries


# ── OpenAI Responses API web search ───────────────────────────────────────────

def _batch_search_with_openai(
    company_name: str,
    ticker: str,
    from_date: date,
    to_date: date,
    include_competitors: bool = False,
    include_macro: bool = False,
    movement_dates: Optional[List[date]] = None,
) -> List[Dict]:
    """
    Perform a single structured batch web search for a ticker across the entire date range using Responses API.

    Returns:
        List of news card dicts with keys: title, summary, date, source_name, url, category, relevance
    """
    if not OPENAI_API_KEY:
        logger.debug("OpenAI API key not configured, returning empty results")
        return []

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)

        categories = [
            "company-specific events (earnings, product launches, executive changes, "
            "lawsuits, regulatory actions, analyst upgrades/downgrades)"
        ]
        if include_competitors:
            categories.append(
                "competitor and industry developments (competitor earnings, M&A, "
                "market share changes, sector-wide trends)"
            )
        if include_macro:
            categories.append(
                "macroeconomic events (Federal Reserve decisions, interest rate changes, "
                "inflation data, GDP reports, geopolitical events)"
            )

        categories_str = "; ".join(categories)

        # Build prompt with priority dates
        prompt_parts = [
            f"Find the most impactful news articles about {company_name} ({ticker}) "
            f"published between {from_date.isoformat()} and {to_date.isoformat()}. "
            f"Cover: {categories_str}. "
            f"Focus on news that would explain significant stock price movements."
        ]

        if movement_dates:
            date_strs = [d.isoformat() for d in movement_dates]
            prompt_parts.append(
                f" CRITICAL: Prioritize finding at least one article for each of these major movement dates: "
                f"{', '.join(date_strs)}. These are the days with the largest stock price swings."
            )

        prompt = " ".join(prompt_parts)

        # Use exponential backoff retry with rate limiting
        rate_limiter = get_rate_limiter()
        
        def make_api_call():
            # Use Responses API with web_search tool
            result = client.responses.create(
                model=OPENAI_SEARCH_MODEL,
                instructions=STRUCTURED_NEWS_SYSTEM_PROMPT,
                input=prompt,
                tools=[{"type": "web_search", "search_context_size": OPENAI_SEARCH_CONTEXT_SIZE}],
                tool_choice="required",  # Require web search for news fetching
            )
            return result

        response = retry_with_exponential_backoff(
            make_api_call,
            max_retries=5,
            initial_delay=1.0,
            max_delay=60.0,
            rate_limiter=rate_limiter,
        )

        content, _, _ = _extract_from_response(response)
        cards = _parse_news_cards_from_response(content)
        logger.debug(f"Structured batch search returned {len(cards)} news cards for {ticker}")
        return cards

    except OpenAIError as e:
        if is_rate_limit_error(e):
            logger.warning(f"Rate limit hit in batch web search: {e}")
            raise create_rate_limit_error(e) from e
        logger.error(f"OpenAI batch web search failed: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in batch web search: {e}")
        return []


def _search_with_openai(
    search_prompt: str,
    category: str,
) -> Tuple[str, List[str], List[str]]:
    """
    Use OpenAI Responses API with web_search tool to find news.
    
    Returns:
        Tuple of (ai_summary, sources, search_queries)
    """
    if not OPENAI_API_KEY:
        logger.debug("OpenAI API key not configured, returning empty results")
        return ("", [], [])

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Use exponential backoff retry with rate limiting
        rate_limiter = get_rate_limiter()
        
        def make_api_call():
            # Use Responses API with web_search tool
            system_prompt = "You are a financial research assistant. Search for and summarize relevant news articles. Always include direct source URLs in your response. IMPORTANT: This is a web application interface, not a conversational chat. Never offer follow-up actions, suggest what the user can do next, or ask if they want additional information. Provide a complete, self-contained response."
            result = client.responses.create(
                model=OPENAI_SEARCH_MODEL,
                instructions=system_prompt,
                input=search_prompt,
                tools=[{"type": "web_search", "search_context_size": OPENAI_SEARCH_CONTEXT_SIZE}],
                tool_choice="required",  # Require web search for news fetching
            )
            return result

        response = retry_with_exponential_backoff(
            make_api_call,
            max_retries=5,
            initial_delay=1.0,
            max_delay=60.0,
            rate_limiter=rate_limiter,
        )

        ai_summary, sources, search_queries = _extract_from_response(response)
        logger.debug(f"Web search for {category}: found {len(sources)} sources")
        return (ai_summary, sources, search_queries)
        
    except OpenAIError as e:
        if is_rate_limit_error(e):
            logger.warning(f"Rate limit hit in web search for {category}: {e}")
            raise create_rate_limit_error(e) from e
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
    movement_dates: Optional[List[date]] = None,
) -> List[Dict]:
    """
    Fetch structured news cards for an entire date range in a single batch query.

    Returns:
        List of news card dicts with keys: title, summary, date, source_name,
        url, category, relevance
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

    logger.debug(f"Fetching structured news cards for {ticker} from {from_date} to {to_date}")

    return _batch_search_with_openai(
        company_name=company_name,
        ticker=ticker,
        from_date=from_date,
        to_date=to_date,
        include_competitors=include_competitors,
        include_macro=include_macro,
        movement_dates=movement_dates,
    )


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
