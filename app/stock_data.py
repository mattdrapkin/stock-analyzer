import time
import yfinance as yf
import pandas as pd
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Use curl_cffi session if available to bypass Yahoo Finance per-IP rate limiting
try:
    from curl_cffi import requests as _curl_requests
    _SESSION = _curl_requests.Session(impersonate="chrome110")
    logger.info("curl_cffi session active — Yahoo Finance rate limit bypass enabled")
except ImportError:
    _SESSION = None
    logger.warning("curl_cffi not installed — Yahoo Finance rate limiting may apply")


def _ticker(symbol: str) -> yf.Ticker:
    """Return a yf.Ticker optionally backed by a curl_cffi session."""
    if _SESSION is not None:
        return yf.Ticker(symbol, session=_SESSION)
    return yf.Ticker(symbol)


def _retry(fn, retries: int = 4, base_delay: float = 5.0):
    """Call fn() with exponential backoff on rate-limit responses."""
    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            msg = str(e).lower()
            is_rate = "rate" in msg or "429" in msg or "too many" in msg
            if is_rate and attempt < retries - 1:
                wait = base_delay * (2 ** attempt)
                logger.warning(
                    f"Rate limited — retrying in {wait:.0f}s (attempt {attempt + 1}/{retries})"
                )
                time.sleep(wait)
            else:
                raise
    raise last_exc


def fetch_price_history(
    ticker: str,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """
    Fetch historical OHLCV data for a ticker via yfinance.
    curl_cffi (listed in requirements.txt) must be installed so that yfinance
    can bypass Yahoo Finance's per-IP rate limiting.
    """
    t = _ticker(ticker)
    end_inclusive = end_date + timedelta(days=1)

    def _fetch():
        return t.history(
            start=start_date.isoformat(),
            end=end_inclusive.isoformat(),
        )

    df = _retry(_fetch)
    if df.empty:
        raise ValueError(f"No price data found for ticker '{ticker}'. Check the symbol.")

    # Remove timezone info for consistent datetime handling
    df.index = df.index.tz_localize(None)
    return df


def detect_major_movements(
    df: pd.DataFrame,
    min_pct: float = 2.0,
) -> List[Dict]:
    """
    Identify trading days where abs(daily % change) >= min_pct.

    Change is computed as (Close - Open) / Open * 100 to capture intra-day
    moves rather than overnight gaps, making it a cleaner signal of news-driven
    activity during the trading session.
    """
    df = df.copy()
    df["change_pct"] = ((df["Close"] - df["Open"]) / df["Open"]) * 100

    movements = []
    for idx, row in df.iterrows():
        if abs(row["change_pct"]) >= min_pct:
            movements.append(
                {
                    "date": idx.date(),
                    "open": round(float(row["Open"]), 4),
                    "close": round(float(row["Close"]), 4),
                    "high": round(float(row["High"]), 4),
                    "low": round(float(row["Low"]), 4),
                    "volume": int(row["Volume"]),
                    "change_pct": round(float(row["change_pct"]), 2),
                    "direction": "up" if row["change_pct"] > 0 else "down",
                }
            )

    return sorted(movements, key=lambda x: x["date"])


def get_ticker_info(ticker: str) -> Dict:
    """Return basic company metadata from yfinance."""
    try:
        t = _ticker(ticker)
        info = _retry(lambda: t.info)
        return {
            "company_name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }
    except Exception as e:
        logger.warning(f"Could not fetch info for {ticker}: {e}")
        return {"company_name": ticker, "sector": None, "industry": None}


def get_yfinance_news(ticker: str) -> List[Dict]:
    """
    Fetch the most recent news from yfinance's Yahoo Finance feed.
    Used as a free fallback when NewsAPI key is not configured.
    Note: no date-range filtering is available; returns the ~10 most recent items.
    """
    try:
        t = _ticker(ticker)
        raw_news = t.news or []
        articles = []
        for item in raw_news:
            # yfinance ≥ 0.2.50 wraps everything inside a "content" sub-dict
            c = item.get("content") or item
            title = c.get("title", "")
            if not title:
                continue
            # pubDate is ISO string in newer schema; providerPublishTime is epoch in older
            pub_dt: Optional[datetime] = None
            pub_date_str = c.get("pubDate") or c.get("displayTime", "")
            if pub_date_str:
                try:
                    pub_dt = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00")).replace(tzinfo=None)
                except Exception:
                    pass
            if pub_dt is None:
                pub_ts = c.get("providerPublishTime", 0)
                pub_dt = datetime.fromtimestamp(pub_ts) if pub_ts else None

            provider = c.get("provider") or {}
            source = (
                provider.get("displayName")
                or c.get("publisher", "Yahoo Finance")
            )
            url_obj = c.get("canonicalUrl") or c.get("clickThroughUrl") or {}
            url = url_obj.get("url") or c.get("link", "") or None

            articles.append(
                {
                    "title": title,
                    "source": source,
                    "url": url,
                    "published_at": pub_dt,
                    "summary": c.get("summary", "") or c.get("description", ""),
                    "category": "company",
                }
            )
        return articles
    except Exception as e:
        logger.warning(f"yfinance news fetch failed for {ticker}: {e}")
        return []
