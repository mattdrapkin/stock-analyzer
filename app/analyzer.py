"""
Orchestration layer: combines stock price data with news articles to produce
the TickerAnalysis response consumed by the REST API.
"""

import time
import logging
from datetime import date, timedelta
from typing import Any, Dict, Optional, Tuple

from .models import NewsArticle, NewsCategory, StockMovement, TickerAnalysis
from .stock_data import (
    detect_major_movements,
    fetch_price_history,
    get_ticker_info,
)
from .news_fetcher import (
    fetch_news_for_movement,
    has_newsapi_key,
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


# ── News article normaliser ───────────────────────────────────────────────────

def _to_news_article(raw: Dict, fallback_category: str = "company") -> NewsArticle:
    cat_str = raw.get("category", fallback_category)
    try:
        cat = NewsCategory(cat_str)
    except ValueError:
        cat = NewsCategory.COMPANY
    return NewsArticle(
        title=raw.get("title", ""),
        source=raw.get("source", ""),
        url=raw.get("url") or None,
        published_at=raw.get("published_at"),
        summary=raw.get("summary") or None,
        category=cat,
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
) -> TickerAnalysis:
    """
    Fetch price history, detect major movements, attach relevant news, and
    return a fully populated TickerAnalysis object.

    Caching: results keyed by (ticker, start, end, min_pct, competitors, macro)
    with a configurable TTL (default 30 min).
    
    Raises:
        ValueError: For invalid parameters (date range, ticker, etc.)
    """
    # Validate date range
    if start_date > end_date:
        raise ValueError("start_date must be before or equal to end_date")
    
    # Validate date range limits
    max_range_days = 730  # 2 years
    if (end_date - start_date).days > max_range_days:
        raise ValueError(f"Date range cannot exceed {max_range_days} days")
    
    current_month_start = date.today().replace(day=1)
    cache_key = (
        f"{ticker.upper()}|{start_date}|{end_date}|{min_movement_pct}"
        f"|{include_competitors}|{include_macro}|{max_articles_per_category}"
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

    # 3. News key
    if not has_newsapi_key():
        raise ValueError(
            "NEWSAPI_KEY is required for news analysis. Please set the NEWSAPI_KEY environment variable."
        )

    # Track rate limit issues
    rate_limit_hit = False

    # 4. Build StockMovement objects with attached news
    movements = []
    for raw in raw_movements:
        mv_date: date = raw["date"]

        # Fetch news for this movement date
        raw_articles = fetch_news_for_movement(
            movement_date=mv_date,
            company_name=company_name,
            ticker=ticker,
            sector=sector,
            industry=industry,
            include_competitors=include_competitors,
            include_macro=include_macro,
            max_per_category=max_articles_per_category,
        )
        
        # Check if we might have hit rate limits (no articles when expected)
        if not raw_articles:
            rate_limit_hit = True
        
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
            )
        )

    up = sum(1 for m in movements if m.direction == "up")

    news_note: Optional[str] = None
    if rate_limit_hit:
        news_note = (
            "Warning: Some news articles may be missing. "
            "Consider reducing the number of categories (competitor/macro) or checking your NewsAPI quota."
        )

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
        news_source="NewsAPI",
        news_note=news_note,
    )

    _cache_set(cache_key, result)
    return result
