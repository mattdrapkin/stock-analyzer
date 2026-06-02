"""
Basket Analysis: Compare multiple securities to find the biggest movers over a period.
"""

import json
import logging
import os
from datetime import date
from typing import Dict, List, Optional, Tuple

import pandas as pd
from openai import OpenAIError

from .models import BasketAnalysisResponse, BasketTickerResult, NewsCard
from .news_parsing import (
    news_card_from_dict,
    parse_article_dict,
    strip_markdown_fences,
    strip_markdown_formatting,
)
from .openai_client import (
    OPENAI_API_KEY,
    RateLimitError,
    call_chat_completions,
    call_responses_api,
    has_openai_key,
)
from .stock_data import fetch_price_history, get_ticker_info

logger = logging.getLogger(__name__)

# Configurable limit for news fetching on biggest movers
BASKET_NEWS_TOP_N: int = int(os.getenv("BASKET_NEWS_TOP_N", "10"))

# Maximum number of tickers to include in a single news batch
BASKET_NEWS_MAX_BATCH_SIZE: int = int(os.getenv("BASKET_NEWS_MAX_BATCH_SIZE", "20"))


# Structured JSON prompt for basket news fetching (combined selection + news finding)
BASKET_NEWS_SYSTEM_PROMPT = """\
You are a financial research assistant with real-time web search access.
Your task is to identify which securities in a basket are most likely to have meaningful news, then find that news.

You MUST respond ONLY with a valid JSON object — no markdown, no code blocks, no preamble.

Required JSON format:
{
  "ticker_news": {
    "TICKER1": [
      {
        "title": "Exact headline of the article",
        "summary": "One sentence capturing the key investment takeaway",
        "date": "YYYY-MM-DD",
        "source_name": "Publication name (e.g. Bloomberg, Reuters, WSJ, CNBC)",
        "url": "https://full-url-to-article",
        "category": "company",
        "relevance": "One sentence explaining why this likely impacted the stock price"
      }
    ],
    "TICKER2": [...]
  }
}

Selection criteria for which tickers to find news for:
- Prioritize securities with significant price movements (absolute % change > 5%)
- Include securities that might be affected by sector-wide or macro events
- Favor securities with higher trading volume or market cap
- Aim for 10-15 tickers maximum, but fewer if movements are insignificant
- If fewer than 5 tickers have meaningful movements, select only those
- If more than 15 have significant movements, select the most impactful ones

News finding rules:
- Find 2-3 articles per selected ticker (fewer if no significant news available)
- category must be exactly one of: "company", "competitor", "macro"
- date must be in YYYY-MM-DD format, or null if unknown
- url must be a real, complete URL starting with https://, or null if unavailable
- title, summary, and relevance must be non-empty strings
- If a ticker has no meaningful news, omit it from the response entirely
- Do not include any text outside the JSON object
"""




def _parse_basket_news_cards_from_response(content: str) -> Dict[str, List[Dict]]:
    """Parse structured news cards from an OpenAI JSON response for basket."""
    if not content:
        return {}

    text = strip_markdown_fences(content)

    # Repair truncated JSON by closing any unclosed brackets/braces/strings
    open_braces = text.count('{')
    close_braces = text.count('}')
    open_brackets = text.count('[')
    close_brackets = text.count(']')
    text += ']' * (open_brackets - close_brackets)
    text += '}' * (open_braces - close_braces)
    if text.count('"') % 2 != 0:
        text += '"'

    # Progressively truncate from the end until valid JSON is found
    original_length = len(text)
    for i in range(min(original_length, 1000)):
        try:
            data = json.loads(text)
            ticker_news = data.get("ticker_news", {})
            if not isinstance(ticker_news, dict):
                return {}

            validated: Dict[str, List[Dict]] = {}
            for ticker, articles in ticker_news.items():
                if not isinstance(articles, list):
                    continue
                validated[ticker] = [
                    parsed
                    for article in articles
                    if (parsed := parse_article_dict(article)) is not None
                ]

            logger.info(
                "Successfully parsed basket news after truncating %d characters",
                original_length - len(text),
            )
            return validated
        except json.JSONDecodeError:
            text = text[:-1]
            if not text:
                logger.warning(
                    "Failed to parse basket news: text became empty after %d attempts", i
                )
                return {}
        except (KeyError, TypeError) as e:
            logger.warning("Failed to process basket news after JSON parsing: %s", e)
            logger.debug("Response content that caused processing error: %s", text[:500])
            return {}

    logger.warning(
        "Failed to parse basket news after %d attempts", min(original_length, 1000)
    )
    return {}


def fetch_basket_news_batch(
    ticker_info: List[Dict[str, str]],
    from_date: date,
    to_date: date,
    include_competitors: bool = False,
    include_macro: bool = False,
    prioritize: bool = False,
    ticker_results: Optional[List[BasketTickerResult]] = None,
) -> Dict[str, List[NewsCard]]:
    """
    Fetch news for multiple tickers in a single batch OpenAI call using Responses API with web_search tool.
    
    The AI will intelligently select which tickers have meaningful news based on their performance.
    
    Args:
        ticker_info: List of dicts with 'ticker' and 'company_name' keys
        from_date: Start date for news search
        to_date: End date for news search
        include_competitors: Whether to include competitor/industry news
        include_macro: Whether to include macro/geopolitical news
        prioritize: Whether these are priority tickers (biggest winners/losers)
        ticker_results: Optional list of BasketTickerResult with performance data for intelligent selection
    
    Returns:
        Dict mapping ticker symbols to lists of NewsCard objects
    """
    if not OPENAI_API_KEY:
        logger.debug("OpenAI API key not configured, returning empty results")
        return {}

    if not ticker_info:
        return {}

    try:
        categories = ["company events"]
        if include_competitors:
            categories.append("competitor/industry")
        if include_macro:
            categories.append("macro")
        categories_str = ", ".join(categories)

        # Build detailed ticker context with performance data if available
        if ticker_results:
            ticker_context = []
            for info in ticker_info:
                # Find matching result
                result = next((r for r in ticker_results if r.ticker == info['ticker']), None)
                if result:
                    movement_str = f"{abs(result.total_change_pct):.1f}%" if result.total_change_pct else "N/A"
                    ticker_context.append(
                        f"- {result.ticker} ({result.company_name or 'N/A'}): {result.direction} {movement_str}, "
                        f"Sector: {result.sector or 'N/A'}, Industry: {result.industry or 'N/A'}"
                    )
                else:
                    ticker_context.append(
                        f"- {info['ticker']} ({info['company_name']}): Performance data not available"
                    )
            
            prompt = (
                f"Analyze the following {len(ticker_info)} securities and find news for those most likely to have "
                f"meaningful coverage that explains their price movements:\n\n"
                f"{chr(10).join(ticker_context)}\n\n"
                f"Date range: {from_date.isoformat()} to {to_date.isoformat()}. "
                f"Topics: {categories_str}. "
                f"Use the selection criteria in the system prompt to determine which tickers warrant news coverage."
            )
        else:
            # Fallback to simple format if no performance data
            ticker_list = [f"{info['ticker']} ({info['company_name']})" for info in ticker_info]
            ticker_str = ", ".join(ticker_list)
            
            prompt = (
                f"News for {ticker_str} "
                f"{from_date.isoformat()} to {to_date.isoformat()}. "
                f"Topics: {categories_str}. "
                f"Find news for tickers most likely to have meaningful coverage."
            )

        content, _, _ = call_responses_api(
            instructions=BASKET_NEWS_SYSTEM_PROMPT,
            prompt=prompt,
        )
        logger.debug(f"Basket news response length: {len(content)}")
        raw_news_dict = _parse_basket_news_cards_from_response(content)

        result: Dict[str, List[NewsCard]] = {
            ticker: [news_card_from_dict(card) for card in raw_cards]
            for ticker, raw_cards in raw_news_dict.items()
        }

        logger.debug(f"Batch news fetch returned news for {len(result)} tickers")
        return result

    except RateLimitError:
        raise
    except OpenAIError as e:
        logger.error(f"OpenAI batch basket news fetch failed: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error in batch basket news fetch: {e}")
        return {}


def generate_basket_holistic_summary(
    basket_response: BasketAnalysisResponse,
) -> Optional[str]:
    """
    Generate an AI-powered holistic summary explaining why the basket moved the way it did.
    
    Aggregates news from all stocks and identifies common themes like sector-wide movements,
    macro events, and company-specific news that drove the basket's performance.
    
    Returns None if OpenAI API key is not configured or if there's an error.
    Returns an error message string if there's insufficient context to generate a meaningful summary.
    """
    if not OPENAI_API_KEY:
        logger.debug("OpenAI API key not configured, skipping holistic summary generation")
        return None
    
    # Collect all news cards from all stocks
    all_news_cards: List[NewsCard] = []
    for result in basket_response.results:
        all_news_cards.extend(result.news_cards)
    
    # Check if we have sufficient news context
    if not all_news_cards:
        logger.debug("No news cards available for holistic summary")
        return None
    
    # Check if we have meaningful news coverage (at least 3 articles)
    if len(all_news_cards) < 3:
        logger.debug(f"Insufficient news cards for holistic summary: {len(all_news_cards)}")
        return None
    
    # Check if there are significant movements to explain
    significant_movers = [r for r in basket_response.results if r.total_change_pct is not None and abs(r.total_change_pct) >= 2.0]
    if not significant_movers:
        logger.debug("No significant movements found in basket")
        return None
    
    # Build context for the AI
    # Group news by category
    from .models import NewsCategory
    
    company_news = [c for c in all_news_cards if c.category == NewsCategory.COMPANY]
    competitor_news = [c for c in all_news_cards if c.category == NewsCategory.COMPETITOR]
    macro_news = [c for c in all_news_cards if c.category == NewsCategory.MACRO]
    
    # Build ticker performance summary
    ticker_summaries = []
    for result in basket_response.results[:5]:  # Top 5 movers
        ticker_summaries.append(
            f"- {result.ticker} ({result.company_name or 'N/A'}): "
            f"{result.direction} {abs(result.total_change_pct):.1f}% "
            f"(${result.start_price:.2f} → ${result.end_price:.2f})"
        )
    
    # Build news summary
    news_summary_parts = []
    
    if company_news:
        news_summary_parts.append(f"Company-specific news ({len(company_news)} articles):")
        for card in company_news[:5]:
            news_summary_parts.append(f"  - {card.ticker if hasattr(card, 'ticker') else 'Stock'}: {card.title}")
    
    if competitor_news:
        news_summary_parts.append(f"Competitor/industry news ({len(competitor_news)} articles):")
        for card in competitor_news[:3]:
            news_summary_parts.append(f"  - {card.title}")
    
    if macro_news:
        news_summary_parts.append(f"Macro/geopolitical news ({len(macro_news)} articles):")
        for card in macro_news[:3]:
            news_summary_parts.append(f"  - {card.title}")
    
    context = f"""
Basket Analysis Summary:
Period: {basket_response.period_start} to {basket_response.period_end}
Total stocks analyzed: {basket_response.total_analyzed}

Top performers:
{chr(10).join(ticker_summaries)}

News coverage:
{chr(10).join(news_summary_parts)}

Please provide a holistic summary in TWO CLEAR SEPARATE PARAGRAPHS:

**First paragraph (1-2 sentences):** Explain the BROAD THEME driving the basket's overall movement. Focus on sector-wide trends, macro factors, commodity prices, or industry dynamics that affected most stocks. Be concise and high-level.

**Second paragraph (2-3 sentences):** Provide more detailed analysis of specific securities and company-specific factors. Explain why the biggest movers moved significantly and any notable company-specific news.

Format your response as:
[BROAD THEME PARAGRAPH]

[DETAILED ANALYSIS PARAGRAPH]

IMPORTANT: This is a web application interface, not a conversational chat. Never offer follow-up actions, suggest what the user can do next, or ask if they want additional information. Provide a complete, self-contained response.
"""
    
    try:
        summary = call_chat_completions(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert financial analyst. Provide concise, insightful summaries "
                        "of basket performance based on news and price data. "
                        "IMPORTANT: This is a web application interface, not a conversational chat. "
                        "Never offer follow-up actions, suggest what the user can do next, or ask if "
                        "they want additional information. Provide a complete, self-contained response."
                    ),
                },
                {"role": "user", "content": context},
            ],
            temperature=0.3,
        )
        summary = strip_markdown_formatting(summary)
        logger.debug(f"Generated basket holistic summary: {summary[:100]}...")
        return summary
    except OpenAIError as e:
        logger.warning(f"OpenAI API error generating basket holistic summary: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error generating basket holistic summary: {e}")
        return None


def enrich_basket(
    results: List[BasketTickerResult],
    start_date: date,
    end_date: date,
    include_competitors: bool = False,
    include_macro: bool = False,
    basket_name: Optional[str] = None,
) -> Tuple[Dict[str, List[NewsCard]], Optional[str]]:
    """
    AI-powered enrichment for already-computed basket results.

    Fetches news and generates a holistic summary without re-fetching price data.
    Intended to be called in the background after the fast price-data phase.

    Returns:
        Tuple of (ticker_news_dict, holistic_summary)
    """
    if not has_openai_key():
        logger.debug("OpenAI API key not configured, skipping basket enrichment")
        return {}, None

    if not results:
        return {}, None

    ticker_info_list = [
        {"ticker": r.ticker, "company_name": r.company_name or r.ticker}
        for r in results
    ]

    top_n = min(BASKET_NEWS_MAX_BATCH_SIZE, len(results))

    try:
        batch_news = fetch_basket_news_batch(
            ticker_info=ticker_info_list[:top_n],
            from_date=start_date,
            to_date=end_date,
            include_competitors=include_competitors,
            include_macro=include_macro,
            prioritize=True,
            ticker_results=results[:top_n],
        )
    except RateLimitError:
        logger.warning("Rate limit hit during basket enrichment news fetch")
        return {}, None
    except Exception as e:
        logger.error(f"Error during basket enrichment news fetch: {e}")
        return {}, None

    # Build enriched results for holistic summary generation
    enriched_results = [
        r.model_copy(update={"news_cards": batch_news.get(r.ticker, [])})
        for r in results
    ]

    temp_response = BasketAnalysisResponse(
        tickers=[r.ticker for r in results],
        period_start=start_date,
        period_end=end_date,
        results=enriched_results,
        total_analyzed=len(enriched_results),
        news_source="OpenAI Web Search",
        basket_name=basket_name,
    )
    holistic_summary = generate_basket_holistic_summary(temp_response)

    return batch_news, holistic_summary


def analyze_basket(
    tickers: List[str],
    start_date: date,
    end_date: date,
    include_news: bool = False,
    include_competitors: bool = False,
    include_macro: bool = False,
    basket_id: Optional[str] = None,
    basket_name: Optional[str] = None,
) -> BasketAnalysisResponse:
    """
    Analyze a basket of tickers over a date range to find the biggest movers.
    
    For each ticker, calculates the total percentage change from the first
    trading day to the last trading day in the period, then sorts by
    absolute percentage change to identify the biggest movers.
    
    If include_news is True, fetches news articles for all tickers in a single batch call.
    """
    results: List[BasketTickerResult] = []
    failed_tickers: List[str] = []
    news_source = "None"
    
    # Determine news source
    if include_news:
        if has_openai_key():
            news_source = "OpenAI Web Search"
        else:
            logger.warning("OpenAI API key not configured, skipping news fetch")
            include_news = False
    
    # First pass: fetch price data and company info for all tickers
    ticker_info_list: List[Dict[str, str]] = []
    
    for ticker in tickers:
        ticker = ticker.upper().strip()
        if not ticker:
            continue
            
        try:
            # Fetch price history
            df = fetch_price_history(ticker, start_date, end_date)
            
            if df.empty:
                logger.warning(f"No price data for {ticker}")
                failed_tickers.append(ticker)
                continue
            
            # Get first and last close prices
            start_price = float(df.iloc[0]['Close'])
            end_price = float(df.iloc[-1]['Close'])

            # Validate price data - check for NaN or invalid values
            if pd.isna(start_price) or pd.isna(end_price) or start_price <= 0 or end_price <= 0:
                logger.warning(f"Invalid price data for {ticker}: start={start_price}, end={end_price}")
                failed_tickers.append(ticker)
                continue

            # Calculate total percentage change
            total_change_pct = ((end_price - start_price) / start_price) * 100
            direction = "up" if total_change_pct >= 0 else "down"
            
            # Get company info
            info = get_ticker_info(ticker)
            company_name = info.get("company_name") or ticker
            sector = info.get("sector")
            industry = info.get("industry")
            
            # Store for batch news fetch
            ticker_info_list.append({
                'ticker': ticker,
                'company_name': company_name
            })
            
            results.append(
                BasketTickerResult(
                    ticker=ticker,
                    company_name=company_name,
                    sector=sector,
                    industry=industry,
                    start_price=round(start_price, 2),
                    end_price=round(end_price, 2),
                    total_change_pct=round(total_change_pct, 2),
                    direction=direction,
                    news_cards=[],  # Will be filled in batch
                )
            )
        except Exception as e:
            logger.warning(f"Failed to analyze {ticker}: {e}")
            failed_tickers.append(ticker)
            continue
    
    # Sort by absolute percentage change (biggest movers first) BEFORE news fetching
    # Filter out results with None total_change_pct (shouldn't happen due to validation, but defensive)
    valid_results = [r for r in results if r.total_change_pct is not None]
    valid_results.sort(key=lambda x: abs(x.total_change_pct), reverse=True)
    results = valid_results
    
    # Batch fetch news - let AI select which tickers have meaningful news
    if include_news and ticker_info_list:
        # Pass top N tickers (or all if fewer) to AI, which will decide which have meaningful news
        top_n = min(BASKET_NEWS_MAX_BATCH_SIZE, len(results))
        ticker_info_for_news = [
            {'ticker': r.ticker, 'company_name': r.company_name}
            for r in results[:top_n]
        ]
        
        logger.info(f"Fetching batch news for {len(ticker_info_for_news)} tickers (AI will select which have meaningful news)")
        try:
            batch_news = fetch_basket_news_batch(
                ticker_info=ticker_info_for_news,
                from_date=start_date,
                to_date=end_date,
                include_competitors=include_competitors,
                include_macro=include_macro,
                prioritize=True,  # Flag to indicate these are priority tickers
                ticker_results=results[:top_n],  # Pass performance data for intelligent selection
            )
            
            logger.info(f"Batch news fetch returned data for {len(batch_news)} tickers")
            
            # Attach news cards to corresponding results
            for result in results:
                if result.ticker in batch_news:
                    result.news_cards = batch_news[result.ticker]
                    logger.info(f"Attached {len(result.news_cards)} news cards to {result.ticker}")
                else:
                    logger.info(f"No news found for {result.ticker}")
        except RateLimitError as e:
            logger.warning(f"Rate limit hit in batch news fetch: {e}")
            news_source = "OpenAI Web Search (Rate Limited)"
            # Continue without news
        except Exception as e:
            logger.warning(f"Failed to fetch batch news: {e}")
            # Continue without news
    else:
        logger.info(f"Skipping news fetch - include_news={include_news}, ticker_info_list length={len(ticker_info_list)}")
    
    # Log failed tickers
    if failed_tickers:
        logger.info(f"Failed to analyze tickers: {', '.join(failed_tickers)}")
    
    # Build response
    response = BasketAnalysisResponse(
        tickers=[t.upper().strip() for t in tickers if t.strip()],
        period_start=start_date,
        period_end=end_date,
        results=results,
        total_analyzed=len(results),
        news_source=news_source,
        basket_name=basket_name,
    )
    
    # Generate holistic summary if news was fetched
    if include_news and news_source == "OpenAI Web Search":
        response.holistic_summary = generate_basket_holistic_summary(response)
    
    return response
