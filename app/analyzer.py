"""
Orchestration layer: combines stock price data with news articles to produce
the TickerAnalysis response consumed by the REST API.
"""

import time
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .models import NewsArticle, NewsCard, NewsSearchSummary, StockMovement, TickerAnalysis
from .news_fetcher import (
    fetch_batch_news_for_period,
    fetch_mock_news_for_movement,
    fetch_news_summaries_for_movement,
)
from .news_parsing import news_card_from_dict, parse_news_category
from .openai_client import RateLimitError, has_openai_key
from .stock_data import (
    detect_major_movements,
    fetch_price_history,
    get_ticker_info,
    get_yfinance_news,
)

logger = logging.getLogger(__name__)

# ── Simple in-memory TTL cache ────────────────────────────────────────────────

_cache: Dict[str, Tuple[Any, float]] = {}


def _cache_get(key: str, ttl: int) -> Optional[Any]:
    entry = _cache.get(key)
    if entry is None:
        return None
    value, ts = entry
    if time.time() - ts < ttl:
        return value
    del _cache[key]
    return None


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = (value, time.time())


# ── News summary normaliser ───────────────────────────────────────────────────

def _to_news_summary(raw: Dict) -> NewsSearchSummary:
    """Convert raw summary dict to NewsSearchSummary model."""
    return NewsSearchSummary(
        category=parse_news_category(raw.get("category", "company")),
        ai_summary=raw.get("ai_summary", ""),
        sources=raw.get("sources", []),
        search_queries=raw.get("search_queries", []),
    )


def _to_news_card(raw: Dict) -> NewsCard:
    """Convert raw card dict to NewsCard model."""
    return news_card_from_dict(raw)


def _to_news_article(raw: Dict, fallback_category: str = "company") -> NewsArticle:
    """Convert raw article dict to NewsArticle model (for backward compatibility)."""
    return NewsArticle(
        title=raw.get("title", ""),
        source=raw.get("source", ""),
        url=raw.get("url") or None,
        published_at=raw.get("published_at"),
        summary=raw.get("summary") or None,
        category=parse_news_category(raw.get("category", fallback_category)),
    )


# ── Core analysis function ────────────────────────────────────────────────────

def build_analysis(
    ticker: str,
    start_date: date,
    end_date: date,
    min_movement_pct: float = 2.0,
    include_competitors: bool = False,
    include_macro: bool = False,
    max_articles_per_category: int = 5,
    cache_ttl: int = 1800,
    include_news: bool = True,
) -> TickerAnalysis:
    """
    Fetch price history, detect major movements, attach relevant news, and
    return a fully populated TickerAnalysis object.

    Caching: results keyed by (ticker, start, end, min_pct, competitors, macro)
    with a configurable TTL (default 30 min).
    """
    cache_key = (
        f"{ticker.upper()}|{start_date}|{end_date}|{min_movement_pct}"
        f"|{include_competitors}|{include_macro}|{max_articles_per_category}"
        f"|news={include_news}|v2"
    )
    cached = _cache_get(cache_key, cache_ttl)
    if cached is not None:
        logger.info(f"Cache hit for {cache_key}")
        return cached

    ticker = ticker.upper()

    # 1. Company metadata
    info = get_ticker_info(ticker)
    company_name: str = info["company_name"] or ticker
    sector: Optional[str] = info["sector"]
    industry: Optional[str] = info["industry"]

    # 2. Price history + movement detection
    df = fetch_price_history(ticker, start_date, end_date)
    raw_movements = detect_major_movements(df, min_pct=min_movement_pct)

    # 3. News — use OpenAI web search if available and requested, otherwise skip/mock
    if include_news and has_openai_key():
        news_source = "OpenAI Web Search"
        use_web_search = True
    elif include_news:
        news_source = "Mock News Data"
        use_web_search = False
    else:
        news_source = "None"
        use_web_search = False

    # 4. Build StockMovement objects with attached news
    movements = []
    batch_cards: List[NewsCard] = []
    rate_limited = False  # Track if we fell back due to rate limit

    if use_web_search:
        # Use batch web search for entire date range (much more efficient)
        # Extract major movement dates to prioritize in search
        movement_dates = [m["date"] for m in raw_movements]

        try:
            raw_cards = fetch_batch_news_for_period(
                company_name=company_name,
                ticker=ticker,
                from_date=start_date,
                to_date=end_date,
                include_competitors=include_competitors,
                include_macro=include_macro,
                movement_dates=movement_dates,
            )
        except RateLimitError as e:
            logger.warning(f"Rate limit error in build_analysis: {e}")
            # Fall back to mock data when rate limited
            news_source = "Mock News Data (Rate Limited)"
            use_web_search = False
            rate_limited = True
            # Skip to mock data path by not setting raw_cards
        else:
            # Build date -> change_pct lookup from full df (all days, not just major movers)
            df_copy = df.copy()
            df_copy["change_pct"] = ((df_copy["Close"] - df_copy["Open"]) / df_copy["Open"]) * 100
            date_to_change_pct = {
                str(idx.date()): round(float(row["change_pct"]), 2)
                for idx, row in df_copy.iterrows()
            }

            # Attach swing_pct to each card
            batch_cards = []
            for card in raw_cards:
                news_card = _to_news_card(card)
                if news_card.date and news_card.date in date_to_change_pct:
                    news_card = news_card.model_copy(update={"swing_pct": date_to_change_pct[news_card.date]})
                batch_cards.append(news_card)
            
            # Attach batch summary to TickerAnalysis level, not per movement
            for raw in raw_movements:
                movements.append(
                    StockMovement(
                        date=raw["date"],
                        open=raw["open"],
                        close=raw["close"],
                        high=raw["high"],
                        low=raw["low"],
                        volume=raw["volume"],
                        change_pct=raw["change_pct"],
                        direction=raw["direction"],
                        news=[],
                        news_summaries=[],  # Empty per movement, use batch summary at analysis level
                    )
                )
    elif include_news:
        # Use mock news data for testing (no OpenAI key available)
        for raw in raw_movements:
            mv_date: date = raw["date"]
            raw_articles = fetch_mock_news_for_movement(
                movement_date=mv_date,
                company_name=company_name,
                ticker=ticker,
                sector=sector,
                industry=industry,
                include_competitors=include_competitors,
                include_macro=include_macro,
                max_per_category=max_articles_per_category,
            )
            articles = [_to_news_article(a) for a in raw_articles]
            
            movements.append(
                StockMovement(
                    date=raw["date"],
                    open=raw["open"],
                    close=raw["close"],
                    high=raw["high"],
                    low=raw["low"],
                    volume=raw["volume"],
                    change_pct=raw["change_pct"],
                    direction=raw["direction"],
                    news=articles,
                    news_summaries=[],
                )
            )
    else:
        # No news requested — build movements without any news
        for raw in raw_movements:
            movements.append(
                StockMovement(
                    date=raw["date"],
                    open=raw["open"],
                    close=raw["close"],
                    high=raw["high"],
                    low=raw["low"],
                    volume=raw["volume"],
                    change_pct=raw["change_pct"],
                    direction=raw["direction"],
                    news=[],
                    news_summaries=[],
                )
            )

    up = sum(1 for m in movements if m.direction == "up")
    if use_web_search:
        news_note: Optional[str] = None
    elif include_news:
        news_note = "Using mock news data for testing purposes."
    else:
        news_note = None

    result = TickerAnalysis(
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        industry=industry,
        period_start=start_date,
        period_end=end_date,
        min_movement_pct=min_movement_pct,
        total_movements=len(movements),
        up_movements=up,
        down_movements=len(movements) - up,
        movements=movements,
        news_source=news_source,
        news_note=news_note,
        batch_news_summaries=[],
        batch_news_cards=batch_cards,
    )

    # Don't cache results that fell back due to rate limit
    if not rate_limited:
        _cache_set(cache_key, result)
    return result
