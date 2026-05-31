"""
Basket Analysis: Compare multiple securities to find the biggest movers over a period.
"""

import json
import logging
import os
from datetime import date
from typing import Dict, List, Optional

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


# Structured JSON prompt for basket news fetching
BASKET_NEWS_SYSTEM_PROMPT = """\
Return ONLY valid JSON: {"ticker_news": {"TICKER": [{"title": "...", "summary": "...", "date": "YYYY-MM-DD", "source_name": "...", "url": "https://...", "category": "company|competitor|macro", "relevance": "..."}]}}.

Rules: Find news for 50%+ of tickers. 2-3 articles per ticker. category must be company/competitor/macro. No markdown or extra text.
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
) -> Dict[str, List[NewsCard]]:
    """
    Fetch news for multiple tickers in a single batch OpenAI call using Responses API with web_search tool.
    
    Args:
        ticker_info: List of dicts with 'ticker' and 'company_name' keys
        from_date: Start date for news search
        to_date: End date for news search
        include_competitors: Whether to include competitor/industry news
        include_macro: Whether to include macro/geopolitical news
        prioritize: Whether these are priority tickers (biggest winners/losers)
    
    Returns:
        Dict mapping ticker symbols to lists of NewsCard objects
    """
    if not OPENAI_API_KEY:
        logger.debug("OpenAI API key not configured, returning empty results")
        return {}

    if not ticker_info:
        return {}

    try:
        ticker_list = [f"{info['ticker']} ({info['company_name']})" for info in ticker_info]
        ticker_str = ", ".join(ticker_list)

        categories = ["company events"]
        if include_competitors:
            categories.append("competitor/industry")
        if include_macro:
            categories.append("macro")
        categories_str = ", ".join(categories)

        priority_context = ""
        if prioritize:
            priority_context = (
                "These are the biggest winners and losers in the basket. "
                "PRIORITIZE finding news for these tickers as they are the most significant movers. "
            )

        prompt = (
            f"News for {ticker_str} "
            f"{from_date.isoformat()} to {to_date.isoformat()}. "
            f"{priority_context}"
            f"Topics: {categories_str}. "
            f"2-3 articles per ticker. 50%+ coverage."
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
    
    # Batch fetch news for top N biggest movers in a single API call
    if include_news and ticker_info_list:
        # Prioritize top N biggest movers for news fetching (configurable via BASKET_NEWS_TOP_N)
        top_n = min(BASKET_NEWS_TOP_N, len(results))
        top_movers = results[:top_n]
        top_ticker_info = [
            {'ticker': r.ticker, 'company_name': r.company_name}
            for r in top_movers
        ]
        
        logger.info(f"Fetching batch news for top {top_n} biggest movers out of {len(results)} total")
        try:
            batch_news = fetch_basket_news_batch(
                ticker_info=top_ticker_info,
                from_date=start_date,
                to_date=end_date,
                include_competitors=include_competitors,
                include_macro=include_macro,
                prioritize=True,  # Flag to indicate these are priority tickers
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
