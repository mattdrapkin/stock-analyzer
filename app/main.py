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
import json
from datetime import date, timedelta
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .models import (
    BasketAnalysisRequest,
    BasketAnalysisResponse,
    ChatRequest,
    ChatResponse,
    FunFactsRequest,
    FunFactsResponse,
    HealthResponse,
    TickerAnalysis,
    PriceHistoryResponse,
)
from .analyzer import build_analysis
from .basket_analyzer import analyze_basket
from .chat import chat_with_ticker, has_openai_key
from .fun_facts import generate_fun_facts
from .news_fetcher import has_openai_key as news_has_openai_key
from .rate_limit_utils import RateLimitError
from .pdf_generator import generate_analysis_pdf, generate_basket_pdf
from .stock_data import fetch_price_history

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── App setup ─────────────────────────────────────────────────────────────────

CACHE_TTL: int = int(os.getenv("CACHE_TTL_SECONDS", "1800"))


class CustomJSONResponse(JSONResponse):
    """Custom JSONResponse that converts NaN values to None for JSON compliance."""
    def _replace_nan(self, obj):
        """Recursively replace NaN values with None."""
        import math
        if isinstance(obj, float) and math.isnan(obj):
            return None
        elif isinstance(obj, dict):
            return {k: self._replace_nan(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_nan(item) for item in obj]
        return obj

    def render(self, content) -> bytes:
        cleaned_content = self._replace_nan(content)
        return json.dumps(
            cleaned_content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")


app = FastAPI(
    title="Stock Movement Analyzer",
    description=(
        "Explains major stock price movements using AI-powered web search and news analysis. "
        "Powered by yfinance and OpenAI Responses API with web_search."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    default_response_class=CustomJSONResponse,
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
        news_api_configured=news_has_openai_key(),
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
    except RateLimitError as e:
        logger.warning(f"Rate limit error in analysis endpoint: {e}")
        raise HTTPException(status_code=429, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error building analysis for {ticker}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get(
    "/api/v1/analysis/{ticker}/price-history",
    response_model=PriceHistoryResponse,
    tags=["Analysis"],
    summary="Fetch full price history for a ticker",
)
def get_price_history(
    ticker: str,
    start_date: Optional[date] = Query(
        default=None,
        description="Start date (YYYY-MM-DD). Defaults to 90 days ago.",
    ),
    end_date: Optional[date] = Query(
        default=None,
        description="End date (YYYY-MM-DD). Defaults to today.",
    ),
) -> PriceHistoryResponse:
    """
    Returns full OHLCV price history for a ticker over the requested period.
    Used for charting and analytics visualizations.
    """
    resolved_end = end_date or date.today()
    resolved_start = start_date or (resolved_end - timedelta(days=90))

    if resolved_start > resolved_end:
        raise HTTPException(status_code=422, detail="start_date must be before end_date.")
    if (resolved_end - resolved_start).days > 730:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 2 years.")

    try:
        from .models import PriceDataPoint
        
        df = fetch_price_history(ticker.upper(), resolved_start, resolved_end)
        
        # Convert DataFrame to list of PriceDataPoint
        data_points = []
        for idx, row in df.iterrows():
            data_points.append(PriceDataPoint(
                date=idx.date().isoformat(),
                open=round(float(row["Open"]), 4),
                high=round(float(row["High"]), 4),
                low=round(float(row["Low"]), 4),
                close=round(float(row["Close"]), 4),
                volume=int(row["Volume"]),
            ))
        
        return PriceHistoryResponse(
            ticker=ticker.upper(),
            period_start=resolved_start,
            period_end=resolved_end,
            data=data_points,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error fetching price history for {ticker}")
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
    except RateLimitError as e:
        logger.warning(f"Rate limit error in chat endpoint: {e}")
        raise HTTPException(status_code=429, detail=str(e))
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
    include_news: bool = Query(
        default=False,
        description="Include news articles for each stock in the basket.",
    ),
    include_competitors: bool = Query(
        default=False,
        description="Also fetch competitor / industry news for each stock.",
    ),
    include_macro: bool = Query(
        default=False,
        description="Also fetch macro / geopolitical news for each stock.",
    ),
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

    **News features** (controlled via query parameters):
    - `include_news=false` (default) → price analysis only
    - `include_news=true` → also fetches news articles for each stock
    - `include_competitors=true` → includes sector / industry news
    - `include_macro=true` → includes Fed, rates, geopolitics news
    """
    # Normalize tickers
    normalized_tickers = [t.upper().strip() for t in body.tickers if t and t.strip()]
    
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
            include_news=include_news,
            include_competitors=include_competitors,
            include_macro=include_macro,
            basket_id=body.basket_id,
            basket_name=body.basket_name,
        )
    except RateLimitError as e:
        logger.warning(f"Rate limit error in basket analysis: {e}")
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error in basket analysis")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.post(
    "/api/v1/fun-facts",
    response_model=FunFactsResponse,
    tags=["Fun Facts"],
    summary="Generate fun facts about a ticker or basket",
)
def get_fun_facts(
    body: FunFactsRequest,
) -> FunFactsResponse:
    """
    Generate interesting, fun facts about a stock ticker or basket of stocks using OpenAI.

    **Example request body for single ticker:**
    ```json
    {
      "ticker": "AAPL"
    }
    ```

    **Example request body for basket:**
    ```json
    {
      "basket": ["AAPL", "MSFT", "GOOGL"]
    }
    ```

    Returns 5-8 fun facts relevant to the provided ticker(s).
    """
    try:
        return generate_fun_facts(body)
    except RateLimitError as e:
        logger.warning(f"Rate limit error in fun facts: {e}")
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error generating fun facts")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.get(
    "/api/v1/analysis/{ticker}/pdf",
    tags=["Analysis"],
    summary="Download stock analysis as PDF",
)
def download_analysis_pdf(
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
        description="Also fetch competitor / industry news around each movement.",
    ),
    include_macro: bool = Query(
        default=False,
        description="Also fetch macro / geopolitical news around each movement.",
    ),
    max_articles: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Maximum news articles per category per movement day.",
    ),
) -> Response:
    """
    Generate and download a PDF report for the stock analysis.
    
    The PDF includes:
    - Report generation timestamp
    - Company information
    - Analysis parameters (date range, threshold, etc.)
    - Summary statistics
    - Significant price movements table
    - News highlights
    
    Returns a PDF file with the analysis results.
    """
    resolved_end = end_date or date.today()
    resolved_start = start_date or (resolved_end - timedelta(days=90))

    if resolved_start > resolved_end:
        raise HTTPException(status_code=422, detail="start_date must be before end_date.")
    if (resolved_end - resolved_start).days > 730:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 2 years.")

    try:
        analysis = build_analysis(
            ticker=ticker.upper(),
            start_date=resolved_start,
            end_date=resolved_end,
            min_movement_pct=min_movement_pct,
            include_competitors=include_competitors,
            include_macro=include_macro,
            max_articles_per_category=max_articles,
            cache_ttl=CACHE_TTL,
        )
        
        params = {
            'include_competitors': include_competitors,
            'include_macro': include_macro,
        }
        
        pdf_content = generate_analysis_pdf(analysis, params)
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={ticker}_analysis_{resolved_start}_to_{resolved_end}.pdf"
            }
        )
    except RateLimitError as e:
        logger.warning(f"Rate limit error in PDF generation: {e}")
        raise HTTPException(status_code=429, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error generating PDF for {ticker}")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")


@app.post(
    "/api/v1/basket/pdf",
    tags=["Basket"],
    summary="Download basket analysis as PDF",
)
def download_basket_pdf(
    body: BasketAnalysisRequest,
    include_news: bool = Query(
        default=False,
        description="Include news articles for each stock in the basket.",
    ),
    include_competitors: bool = Query(
        default=False,
        description="Also fetch competitor / industry news for each stock.",
    ),
    include_macro: bool = Query(
        default=False,
        description="Also fetch macro / geopolitical news for each stock.",
    ),
) -> Response:
    """
    Generate and download a PDF report for the basket analysis.
    
    The PDF includes:
    - Report generation timestamp
    - Analysis parameters (date range, tickers, etc.)
    - Summary statistics
    - Basket performance table with all tickers
    - Holistic summary (if available)
    - News highlights by ticker (if news was fetched)
    
    Returns a PDF file with the basket analysis results.
    """
    # Normalize tickers
    normalized_tickers = [t.upper().strip() for t in body.tickers if t and t.strip()]
    
    if not normalized_tickers:
        raise HTTPException(status_code=422, detail="At least one valid ticker is required.")
    
    if len(normalized_tickers) > 50:
        raise HTTPException(status_code=422, detail="Maximum 50 tickers allowed per request.")
    
    if body.start_date > body.end_date:
        raise HTTPException(status_code=422, detail="start_date must be before end_date.")
    
    if (body.end_date - body.start_date).days > 730:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 2 years.")

    try:
        basket_response = analyze_basket(
            tickers=normalized_tickers,
            start_date=body.start_date,
            end_date=body.end_date,
            include_news=include_news,
            include_competitors=include_competitors,
            include_macro=include_macro,
            basket_id=body.basket_id,
            basket_name=body.basket_name,
        )
        
        params = {
            'include_competitors': include_competitors,
            'include_macro': include_macro,
        }
        
        pdf_content = generate_basket_pdf(basket_response, params)
        
        # Create filename from tickers
        ticker_str = "_".join(normalized_tickers[:5])
        if len(normalized_tickers) > 5:
            ticker_str += f"_and_{len(normalized_tickers) - 5}_more"
        
        return Response(
            content=pdf_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=basket_{ticker_str}_{body.start_date}_to_{body.end_date}.pdf"
            }
        )
    except RateLimitError as e:
        logger.warning(f"Rate limit error in basket PDF generation: {e}")
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        logger.exception(f"Unexpected error generating basket PDF")
        raise HTTPException(status_code=500, detail=f"Internal error: {e}")
