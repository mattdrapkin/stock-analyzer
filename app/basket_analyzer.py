"""
Basket Analysis: Compare multiple securities to find the biggest movers over a period.
"""

import logging
from datetime import date
from typing import List, Dict, Optional

from .models import BasketAnalysisResponse, BasketTickerResult, NewsCard
from .stock_data import fetch_price_history, get_ticker_info
from .news_fetcher import fetch_batch_news_for_period, has_openai_key, RateLimitError

logger = logging.getLogger(__name__)


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
    
    If include_news is True, also fetches news articles for each ticker.
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
            
            # Fetch news if enabled
            news_cards: List[NewsCard] = []
            if include_news:
                try:
                    raw_cards = fetch_batch_news_for_period(
                        company_name=company_name,
                        ticker=ticker,
                        from_date=start_date,
                        to_date=end_date,
                        include_competitors=include_competitors,
                        include_macro=include_macro,
                    )
                    # Convert raw dicts to NewsCard models
                    for card in raw_cards:
                        cat_str = card.get("category", "company")
                        try:
                            from .models import NewsCategory
                            cat = NewsCategory(cat_str)
                        except ValueError:
                            from .models import NewsCategory
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
                    logger.debug(f"Fetched {len(news_cards)} news cards for {ticker}")
                except RateLimitError as e:
                    logger.warning(f"Rate limit hit fetching news for {ticker}: {e}")
                    # Continue without news for this ticker
                except Exception as e:
                    logger.warning(f"Failed to fetch news for {ticker}: {e}")
                    # Continue without news for this ticker
            
            results.append(
                BasketTickerResult(
                    ticker=ticker,
                    company_name=company_name,
                    start_price=round(start_price, 2),
                    end_price=round(end_price, 2),
                    total_change_pct=round(total_change_pct, 2),
                    direction=direction,
                    news_cards=news_cards,
                )
            )
        except Exception as e:
            logger.warning(f"Failed to analyze {ticker}: {e}")
            failed_tickers.append(ticker)
            continue
    
    # Sort by absolute percentage change (biggest movers first)
    results.sort(key=lambda x: abs(x.total_change_pct), reverse=True)
    
    # Log failed tickers
    if failed_tickers:
        logger.info(f"Failed to analyze tickers: {', '.join(failed_tickers)}")
    
    return BasketAnalysisResponse(
        tickers=[t.upper().strip() for t in tickers if t.strip()],
        period_start=start_date,
        period_end=end_date,
        results=results,
        total_analyzed=len(results),
        news_source=news_source,
    )
