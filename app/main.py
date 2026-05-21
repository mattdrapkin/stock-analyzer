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

from .models import (
    BasketAnalysisRequest,
    BasketAnalysisResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    TickerAnalysis,
)
from .analyzer import build_analysis
from .basket_analyzer import analyze_basket
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


# ── Mock Data for Demonstration ────────────────────────────────────────────────

def _get_mock_analysis(ticker: str, start_date: date, end_date: date, min_movement_pct: float) -> TickerAnalysis:
    """Generate mock analysis data for demonstration purposes."""
    from .models import StockMovement, NewsArticle, NewsCategory
    
    # Mock company info
    company_names = {
        'AAPL': 'Apple Inc.',
        'MSFT': 'Microsoft Corporation',
        'GOOGL': 'Alphabet Inc.',
        'TSLA': 'Tesla, Inc.',
        'AMZN': 'Amazon.com, Inc.',
    }
    
    company_name = company_names.get(ticker, f'{ticker} Corporation')
    sector = 'Technology'
    industry = 'Consumer Electronics'
    
    # Generate mock movements
    import random
    from datetime import timedelta
    
    movements = []
    current_date = start_date
    
    # Generate 3-6 random movements
    num_movements = random.randint(3, 6)
    for i in range(num_movements):
        days_offset = random.randint(0, (end_date - start_date).days)
        move_date = start_date + timedelta(days=days_offset)
        
        is_up = random.choice([True, False])
        change_pct = round(random.uniform(min_movement_pct, min_movement_pct * 3), 2)
        if not is_up:
            change_pct = -change_pct
        
        base_price = round(random.uniform(150, 200), 2)
        open_price = base_price
        close_price = round(base_price * (1 + change_pct / 100), 2)
        high_price = round(max(open_price, close_price) * random.uniform(1.001, 1.01), 2)
        low_price = round(min(open_price, close_price) * random.uniform(0.99, 0.999), 2)
        volume = random.randint(50000000, 150000000)
        
        # Mock news articles
        news_articles = []
        num_articles = random.randint(1, 3)
        for j in range(num_articles):
            headlines = [
                f"{company_name} reports strong quarterly earnings",
                f"{ticker} stock surges on positive analyst rating",
                f"{company_name} announces new product line",
                f"Market rally boosts {ticker} shares",
                f"{company_name} faces regulatory scrutiny",
                f"Investors optimistic about {ticker} growth prospects",
            ]
            headlines = headlines[:num_articles]
            
            article = NewsArticle(
                title=headlines[j],
                source="Financial News",
                url=f"https://example.com/news/{ticker.lower()}-{j}",
                published_at=move_date,
                summary=f"Breaking news about {ticker} with market implications.",
                category=NewsCategory.COMPANY,
            )
            news_articles.append(article)
        
        movement = StockMovement(
            date=move_date,
            open=open_price,
            close=close_price,
            high=high_price,
            low=low_price,
            volume=volume,
            change_pct=change_pct,
            direction="up" if change_pct > 0 else "down",
            news=news_articles,
        )
        movements.append(movement)
    
    movements.sort(key=lambda x: x.date)
    
    up_count = sum(1 for m in movements if m.direction == "up")
    
    return TickerAnalysis(
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        industry=industry,
        period_start=start_date,
        period_end=end_date,
        min_movement_pct=min_movement_pct,
        total_movements=len(movements),
        up_movements=up_count,
        down_movements=len(movements) - up_count,
        movements=movements,
        news_source="Mock Data (Demonstration Mode)",
        news_note="This is mock data for demonstration purposes. Set use_mock=false to use real data.",
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
        news_api_configured=has_newsapi_key(),
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
    use_mock: bool = Query(
        default=False,
        description="Use mock data for demonstration (bypasses yfinance).",
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
    """
    resolved_end = end_date or date.today()
    resolved_start = start_date or (resolved_end - timedelta(days=90))

    if resolved_start > resolved_end:
        raise HTTPException(status_code=422, detail="start_date must be before end_date.")
    if (resolved_end - resolved_start).days > 730:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 2 years.")

    # Use mock data for demonstration if requested or if real data fails
    if use_mock:
        return _get_mock_analysis(ticker.upper(), resolved_start, resolved_end, min_movement_pct)

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
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error in chat for {ticker}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.post(
    "/api/v1/basket",
    response_model=BasketAnalysisResponse,
    tags=["Basket"],
    summary="Analyze a basket of securities to find the biggest movers",
)
def analyze_basket_endpoint(
    body: BasketAnalysisRequest,
) -> BasketAnalysisResponse:
    """
    Analyze multiple securities over a date range to identify the biggest movers.

    Takes a comma-separated list of ticker symbols and a date range, then
    calculates the total percentage change for each ticker from the first
    to the last trading day in the period. Results are sorted by absolute
    percentage change to show the biggest movers first.

    **Example request body:**
    ```json
    {
      "tickers": ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"],
      "start_date": "2024-01-01",
      "end_date": "2024-12-31"
    }
    ```
    """
    # Normalize tickers
    normalized_tickers = [t.upper().strip() for t in body.tickers if t.strip()]
    
    if not normalized_tickers:
        raise HTTPException(status_code=422, detail="At least one valid ticker is required.")
    
    if len(normalized_tickers) > 50:
        raise HTTPException(status_code=422, detail="Maximum 50 tickers allowed per request.")
    
    if body.start_date > body.end_date:
        raise HTTPException(status_code=422, detail="start_date must be before end_date.")
    
    if (body.end_date - body.start_date).days > 730:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 2 years.")
    
    try:
        return analyze_basket(
            tickers=normalized_tickers,
            start_date=body.start_date,
            end_date=body.end_date,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in basket analysis")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
