from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from datetime import date, datetime
from enum import Enum


class NewsCategory(str, Enum):
    COMPANY = "company"
    COMPETITOR = "competitor"
    MACRO = "macro"


class URLCitation(BaseModel):
    url: str
    title: str
    start_index: int
    end_index: int


class NewsArticle(BaseModel):
    title: str
    source: str
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    summary: Optional[str] = None
    category: NewsCategory = NewsCategory.COMPANY
    citations: List[URLCitation] = []


class NewsSearchSummary(BaseModel):
    category: NewsCategory
    ai_summary: str
    sources: List[str] = []
    search_queries: List[str] = []


class NewsCard(BaseModel):
    title: str
    summary: str
    date: Optional[str] = None  # YYYY-MM-DD string
    source_name: Optional[str] = None
    url: Optional[str] = None
    category: NewsCategory = NewsCategory.COMPANY
    relevance: Optional[str] = None  # one sentence on why it affected the stock
    swing_pct: Optional[float] = None  # stock's daily % change on this date


class StockMovement(BaseModel):
    date: date
    open: float
    close: float
    high: float
    low: float
    volume: int
    change_pct: float
    direction: str  # "up" or "down"
    news: List[NewsArticle] = []
    news_summaries: List[NewsSearchSummary] = []


class TickerAnalysis(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    period_start: date
    period_end: date
    min_movement_pct: float
    total_movements: int
    up_movements: int
    down_movements: int
    movements: List[StockMovement]
    news_source: str  # which news source was used
    news_note: Optional[str] = None  # any caveats about news availability/coverage
    batch_news_summaries: List[NewsSearchSummary] = []  # News summaries for entire period (legacy)
    batch_news_cards: List[NewsCard] = []  # Structured news cards for entire period


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    context_days: int = Field(default=60, ge=1, le=365)
    min_movement_pct: float = Field(default=2.0, ge=0.1)
    include_competitors: bool = False
    include_macro: bool = False


class ChatResponse(BaseModel):
    response: str
    ticker: str
    movements_analyzed: int
    context_used: bool


class HealthResponse(BaseModel):
    status: str
    news_api_configured: bool
    openai_configured: bool


class BasketTickerResult(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    start_price: float
    end_price: float
    total_change_pct: float
    direction: str  # "up" or "down"
    news_cards: List[NewsCard] = []  # News articles for this specific stock


class BasketAnalysisRequest(BaseModel):
    tickers: List[str] = Field(..., min_items=1, max_items=50, description="List of ticker symbols")
    start_date: date
    end_date: date


class BasketAnalysisResponse(BaseModel):
    tickers: List[str]
    period_start: date
    period_end: date
    results: List[BasketTickerResult]
    total_analyzed: int
    holistic_summary: Optional[str] = None  # AI-generated summary of basket movement drivers
    news_source: str = "None"  # Which news source was used (OpenAI, Mock, None)


class FunFactsRequest(BaseModel):
    ticker: Optional[str] = None
    basket: Optional[List[str]] = None

    @model_validator(mode='after')
    def validate_request(self):
        if not self.ticker and not self.basket:
            raise ValueError("Either ticker or basket must be provided")
        return self


class FunFactsResponse(BaseModel):
    facts: List[str]
