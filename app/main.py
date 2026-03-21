"""
FastAPI application — Stock Movement Analyzer API

Endpoints
---------
GET  /api/v1/health                         — liveness + config check
GET  /api/v1/analysis/{ticker}              — stock movements + related news
POST /api/v1/chat/{ticker}                  — multi-turn chat about a ticker
"""

import os
import logging
from datetime import date, timedelta
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .models import ChatRequest, ChatResponse, HealthResponse, TickerAnalysis
from .analyzer import build_analysis
from .chat import chat_with_ticker, has_openai_key
from .news_fetcher import has_newsapi_key

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── App setup ─────────────────────────────────────────────────────────────────

CACHE_TTL: int = int(os.getenv("CACHE_TTL_SECONDS", "1800"))

app = FastAPI(
    title="Stock Movement Analyzer",
    description=(
        "Explains major stock price movements using relevant news articles. "
        "Powered by yfinance, NewsAPI, and OpenAI."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Health check",
)
def health_check() -> HealthResponse:
    """Returns API status and indicates which external keys are configured."""
    return HealthResponse(
        status="ok",
        newsapi_configured=has_newsapi_key(),
        openai_configured=has_openai_key(),
    )


@app.get(
    "/api/v1/analysis/{ticker}",
    response_model=TickerAnalysis,
    tags=["Analysis"],
    summary="Fetch stock movements and related news for a ticker",
)
def get_analysis(
    ticker: str,
    start_date: Optional[date] = Query(
        default=None,
        description="Start date (YYYY-MM-DD). Defaults to 90 days ago.",
    ),
    end_date: Optional[date] = Query(
        default=None,
        description="End date (YYYY-MM-DD). Defaults to today.",
    ),
    min_movement_pct: float = Query(
        default=float(os.getenv("MIN_MOVEMENT_PCT", "2.0")),
        ge=0.1,
        le=50.0,
        description="Minimum absolute intra-day % change to flag as a major movement.",
    ),
    include_competitors: bool = Query(
        default=False,
        description="[Medium] Also fetch competitor / industry news around each movement.",
    ),
    include_macro: bool = Query(
        default=False,
        description="[Hard] Also fetch macro / geopolitical news around each movement.",
    ),
    max_articles: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Maximum news articles per category per movement day.",
    ),
) -> TickerAnalysis:
    """
    Returns all major stock price movements for `ticker` within the requested
    period, each annotated with relevant news articles.

    **Movement definition**: an intra-day close vs. open move of ≥ `min_movement_pct`%.

    **News categories** (controlled via query flags):
    - `include_competitors=false` (default) → company-specific news only
    - `include_competitors=true`             → also includes sector / industry news
    - `include_macro=true`                   → also includes Fed, rates, geopolitics
    
    **News**: Powered by NewsAPI Google News.
    """
    resolved_end = end_date or date.today()
    resolved_start = start_date or (resolved_end - timedelta(days=90))

    # Validate date range
    if resolved_start > resolved_end:
        raise HTTPException(status_code=422, detail="start_date must be before or equal to end_date.")
    if (resolved_end - resolved_start).days > 730:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 2 years.")
    
    try:
        return build_analysis(
            ticker=ticker.upper(),
            start_date=resolved_start,
            end_date=resolved_end,
            min_movement_pct=min_movement_pct,
            include_competitors=include_competitors,
            include_macro=include_macro,
            max_articles_per_category=max_articles,
            cache_ttl=CACHE_TTL,
        )
    except ValueError as e:
        if "rate limit" in str(e).lower():
            raise HTTPException(
                status_code=429, 
                detail={
                    "error": "Rate limit exceeded",
                    "message": "yfinance is rate limiting requests. Please try again in a few minutes.",
                    "retry_after": 300
                }
            )
        elif "newsapi" in str(e).lower():
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "News service unavailable", 
                    "message": "NewsAPI key is required for news analysis. Please set NEWSAPI_KEY environment variable."
                }
            )
        else:
            raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error building analysis for {ticker}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.post(
    "/api/v1/chat/{ticker}",
    response_model=ChatResponse,
    tags=["Chat"],
    summary="Chat about a ticker's price movements and news",
)
def chat(
    ticker: str,
    body: ChatRequest,
) -> ChatResponse:
    """
    Ask free-form questions about a ticker's major price movements.

    The API automatically fetches stock data and news for the configured
    `context_days` window, builds an LLM context, and answers via OpenAI.

    Multi-turn conversations are supported — pass previous turns in `history`.

    **Requires** `OPENAI_API_KEY` to be set for AI-powered responses.
    Without it, a structured text summary is returned instead.

    Example questions:
    - "Why did the stock drop so sharply in January?"
    - "Summarise the biggest movements over the past 2 months."
    - "Were any of the moves driven by macro events?"
    """
    try:
        return chat_with_ticker(
            ticker=ticker.upper(),
            message=body.message,
            history=body.history,
            context_days=body.context_days,
            min_movement_pct=body.min_movement_pct,
            include_competitors=body.include_competitors,
            include_macro=body.include_macro,
        )
    except ValueError as e:
        if "rate limit" in str(e).lower():
            raise HTTPException(
                status_code=429, 
                detail={
                    "error": "Rate limit exceeded",
                    "message": "yfinance is rate limiting requests. Please try again in a few minutes.",
                    "retry_after": 300
                }
            )
        elif "newsapi" in str(e).lower():
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "News service unavailable", 
                    "message": "NewsAPI key is required for news analysis. Please set NEWSAPI_KEY environment variable."
                }
            )
        else:
            raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error in chat for {ticker}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
