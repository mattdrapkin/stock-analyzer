"""
Basket Analysis: Compare multiple securities to find the biggest movers over a period.
"""

import logging
import os
import json
from datetime import date, datetime
from typing import List, Dict, Optional

from openai import OpenAI, OpenAIError

from .models import BasketAnalysisResponse, BasketTickerResult, NewsCard
from .stock_data import fetch_price_history, get_ticker_info
from .news_fetcher import fetch_batch_news_for_period, has_openai_key, RateLimitError

logger = logging.getLogger(__name__)

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_SEARCH_MODEL: str = os.getenv("OPENAI_SEARCH_MODEL", "gpt-5-search-api")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5.4-nano")


# Structured JSON prompt for basket news fetching
BASKET_NEWS_SYSTEM_PROMPT = """\
Return ONLY valid JSON: {"ticker_news": {"TICKER": [{"title": "...", "summary": "...", "date": "YYYY-MM-DD", "source_name": "...", "url": "https://...", "category": "company|competitor|macro", "relevance": "..."}]}}.

Rules: Find news for 50%+ of tickers. 2-3 articles per ticker. category must be company/competitor/macro. No markdown or extra text.
"""


def _parse_basket_news_cards_from_response(content: str) -> Dict[str, List[Dict]]:
    """Parse structured news cards from an OpenAI JSON response for basket."""
    import re
    
    if not content:
        return {}

    text = content.strip()
    # Strip markdown code fences if the model wrapped the JSON
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
        text = text.strip()

    try:
        data = json.loads(text)
        ticker_news = data.get("ticker_news", {})
        if not isinstance(ticker_news, dict):
            return {}

        validated: Dict[str, List[Dict]] = {}
        for ticker, articles in ticker_news.items():
            if not isinstance(articles, list):
                continue
            
            validated_articles = []
            for article in articles:
                if not isinstance(article, dict):
                    continue
                
                title = (article.get("title") or "").strip()
                summary = (article.get("summary") or "").strip()
                if not title or not summary:
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
                    try:
                        parsed_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                        date_str = parsed_date.isoformat()
                    except ValueError:
                        date_str = None

                validated_articles.append({
                    "title": title,
                    "summary": summary,
                    "date": date_str,
                    "source_name": (article.get("source_name") or "").strip() or None,
                    "url": url,
                    "category": cat,
                    "relevance": (article.get("relevance") or "").strip() or None,
                })
            
            validated[ticker] = validated_articles
        return validated
    except (json.JSONDecodeError, KeyError, TypeError):
        logger.warning("Failed to parse structured basket news cards from OpenAI response")
        return {}


def fetch_basket_news_batch(
    ticker_info: List[Dict[str, str]],
    from_date: date,
    to_date: date,
    include_competitors: bool = False,
    include_macro: bool = False,
) -> Dict[str, List[NewsCard]]:
    """
    Fetch news for multiple tickers in a single batch OpenAI call.
    
    Args:
        ticker_info: List of dicts with 'ticker' and 'company_name' keys
        from_date: Start date for news search
        to_date: End date for news search
        include_competitors: Whether to include competitor/industry news
        include_macro: Whether to include macro/geopolitical news
    
    Returns:
        Dict mapping ticker symbols to lists of NewsCard objects
    """
    if not OPENAI_API_KEY:
        logger.debug("OpenAI API key not configured, returning empty results")
        return {}

    if not ticker_info:
        return {}

    try:
        client = OpenAI(api_key=OPENAI_API_KEY)

        # Build prompt with all tickers
        ticker_list = [f"{info['ticker']} ({info['company_name']})" for info in ticker_info]
        ticker_str = ", ".join(ticker_list)

        categories = ["company events"]
        if include_competitors:
            categories.append("competitor/industry")
        if include_macro:
            categories.append("macro")
        categories_str = ", ".join(categories)

        prompt = (
            f"News for {ticker_str} "
            f"{from_date.isoformat()} to {to_date.isoformat()}. "
            f"Topics: {categories_str}. "
            f"2-3 articles per ticker. 50%+ coverage."
        )

        response = client.chat.completions.create(
            model=OPENAI_SEARCH_MODEL,
            messages=[
                {"role": "system", "content": BASKET_NEWS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content or ""
        logger.info(f"OpenAI response (first 300 chars): {content[:300]}")
        raw_news_dict = _parse_basket_news_cards_from_response(content)
        
        # Convert to NewsCard objects
        from .models import NewsCategory
        result: Dict[str, List[NewsCard]] = {}
        
        for ticker, raw_cards in raw_news_dict.items():
            news_cards = []
            for card in raw_cards:
                cat_str = card.get("category", "company")
                try:
                    cat = NewsCategory(cat_str)
                except ValueError:
                    cat = NewsCategory.COMPANY
                
                news_cards.append(NewsCard(
                    title=card.get("title", ""),
                    summary=card.get("summary", ""),
                    date=card.get("date") or None,
                    source_name=card.get("source_name") or None,
                    url=card.get("url") or None,
                    category=cat,
                    relevance=card.get("relevance") or None,
                ))
            result[ticker] = news_cards
        
        logger.debug(f"Batch news fetch returned news for {len(result)} tickers")
        return result

    except OpenAIError as e:
        if hasattr(e, 'status_code') and e.status_code == 429:
            logger.warning(f"Rate limit hit in batch basket news fetch: {e}")
            raise RateLimitError(f"Rate limit reached: {e}") from e
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
    """
    if not OPENAI_API_KEY:
        logger.debug("OpenAI API key not configured, skipping holistic summary generation")
        return None
    
    # Collect all news cards from all stocks
    all_news_cards: List[NewsCard] = []
    for result in basket_response.results:
        all_news_cards.extend(result.news_cards)
    
    if not all_news_cards:
        logger.debug("No news cards available for holistic summary")
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

Please provide a 2-3 sentence holistic summary explaining:
1. Overall basket movement direction and key drivers
2. Common themes across stocks (sector trends, macro events, company-specific news)
3. Why the biggest movers moved significantly

Be concise and focus on the most impactful factors.
"""
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert financial analyst. Provide concise, insightful summaries of basket performance based on news and price data."
                },
                {
                    "role": "user",
                    "content": context
                }
            ],
            temperature=0.3,
        )
        
        summary = completion.choices[0].message.content or ""
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
            
            # Calculate total percentage change
            total_change_pct = ((end_price - start_price) / start_price) * 100
            direction = "up" if total_change_pct >= 0 else "down"
            
            # Get company info
            info = get_ticker_info(ticker)
            company_name = info.get("company_name") or ticker
            
            # Store for batch news fetch
            ticker_info_list.append({
                'ticker': ticker,
                'company_name': company_name
            })
            
            results.append(
                BasketTickerResult(
                    ticker=ticker,
                    company_name=company_name,
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
    
    # Batch fetch news for all tickers in a single API call
    if include_news and ticker_info_list:
        logger.info(f"Fetching batch news for {len(ticker_info_list)} tickers")
        try:
            batch_news = fetch_basket_news_batch(
                ticker_info=ticker_info_list,
                from_date=start_date,
                to_date=end_date,
                include_competitors=include_competitors,
                include_macro=include_macro,
            )
            
            logger.info(f"Batch news fetch returned data for {len(batch_news)} tickers")
            
            # Attach news cards to corresponding results
            for result in results:
                if result.ticker in batch_news:
                    result.news_cards = batch_news[result.ticker]
                    logger.info(f"Attached {len(result.news_cards)} news cards to {result.ticker}")
                else:
                    logger.warning(f"No news found for {result.ticker}")
        except RateLimitError as e:
            logger.warning(f"Rate limit hit in batch news fetch: {e}")
            news_source = "OpenAI Web Search (Rate Limited)"
            # Continue without news
        except Exception as e:
            logger.warning(f"Failed to fetch batch news: {e}")
            # Continue without news
    else:
        logger.info(f"Skipping news fetch - include_news={include_news}, ticker_info_list length={len(ticker_info_list)}")
    
    # Sort by absolute percentage change (biggest movers first)
    results.sort(key=lambda x: abs(x.total_change_pct), reverse=True)
    
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
    )
    
    # Generate holistic summary if news was fetched
    if include_news and news_source == "OpenAI Web Search":
        response.holistic_summary = generate_basket_holistic_summary(response)
    
    return response
