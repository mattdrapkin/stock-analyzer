# Stock Movement Analyzer

Explains **major stock price movements** using relevant news articles.  
Built with **FastAPI**, **yfinance**, **NewsAPI**, and **OpenAI**.

---

## How it works

1. Fetches historical OHLCV data for any public ticker via **yfinance**.
2. Flags days where the intra-day move (Close vs. Open) is **≥ 2 %** (configurable).
3. For each flagged day, fetches related news from **NewsAPI** across up to three categories:
   - **Company-specific** (earnings, product launches, lawsuits) — always on
   - **Competitor / industry** (`include_competitors=true`) — optional, uses LLM to identify specific competitors
   - **Macro / geopolitical** (`include_macro=true`) — optional
4. Exposes the data via a REST API with two main endpoints:
   - `GET /api/v1/analysis/{ticker}` — structured data with filters
   - `POST /api/v1/chat/{ticker}` — natural-language Q&A powered by OpenAI
5. Includes comprehensive testing suite and rate limit handling

---

## Quickstart

### 1 — Prerequisites

- Python 3.11+
- A free [NewsAPI key](https://newsapi.org/register) (100 requests/day)
- An [OpenAI API key](https://platform.openai.com/api-keys) (for the `/chat` endpoint)

### 2 — Clone & install

```bash
git clone <repo-url>
cd stock-analyzer

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 3 — Configure environment

```bash
cp .env.example .env
# Edit .env and add your keys:
#   NEWS_API_KEY=...
#   OPENAI_API_KEY=...
```

### 4 — Run the server

```bash
uvicorn app.main:app --reload --port 8000
```

The API is now live at **http://localhost:8000**.  
Interactive docs: **http://localhost:8000/docs**

**Live deployment**: https://stock-analyzer-227z.onrender.com  
Live API docs: https://stock-analyzer-227z.onrender.com/docs

### 5 — Test the installation

```bash
python test_app.py
```

This runs the comprehensive test suite to verify all functionality.

---

## API Reference

### `GET /api/v1/health`

Liveness check. Shows which API keys are configured.

```bash
curl http://localhost:8000/api/v1/health
```

```json
{
  "status": "ok",
  "news_api_configured": true,
  "openai_configured": true
}
```

---

### `GET /api/v1/analysis/{ticker}`

Returns all major price movements for a ticker with related news.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start_date` | date | 90 days ago | Analysis start (YYYY-MM-DD) |
| `end_date` | date | today | Analysis end (YYYY-MM-DD) |
| `min_movement_pct` | float | 2.0 | Min absolute intra-day % change |
| `include_competitors` | bool | false | Add sector/industry news |
| `include_macro` | bool | false | Add macro/geopolitical news |
| `max_articles` | int | 5 | Max articles per category per day |

**Example — basic**

```bash
curl "http://localhost:8000/api/v1/analysis/AAPL"
```

**Example — with all filters**

```bash
curl "http://localhost:8000/api/v1/analysis/NVDA?\
start_date=2024-11-01&\
end_date=2025-01-31&\
min_movement_pct=3.0&\
include_competitors=true&\
include_macro=true&\
max_articles=5"
```

**Response shape**

```json
{
  "ticker": "NVDA",
  "company_name": "NVIDIA Corporation",
  "sector": "Technology",
  "industry": "Semiconductors",
  "period_start": "2024-11-01",
  "period_end": "2025-01-31",
  "min_movement_pct": 3.0,
  "total_movements": 8,
  "up_movements": 5,
  "down_movements": 3,
  "news_source": "NewsAPI",
  "movements": [
    {
      "date": "2024-11-21",
      "open": 141.20,
      "close": 148.88,
      "high": 149.43,
      "low": 140.55,
      "volume": 312000000,
      "change_pct": 5.44,
      "direction": "up",
      "news": [
        {
          "title": "Nvidia earnings smash expectations...",
          "source": "Reuters",
          "url": "https://...",
          "published_at": "2024-11-20T21:00:00",
          "summary": "Nvidia posted Q3 revenue of...",
          "category": "company"
        }
      ]
    }
  ]
}
```

---

### `POST /api/v1/chat/{ticker}`

Ask natural-language questions about a ticker's movements and news.

**Request body**

```json
{
  "message": "Why did the stock drop so sharply in January?",
  "history": [],
  "context_days": 60,
  "min_movement_pct": 2.0,
  "include_competitors": false,
  "include_macro": true
}
```

**Multi-turn example**

```json
{
  "message": "Were any of those moves driven by macro factors?",
  "history": [
    { "role": "user",      "content": "Summarise the biggest movements last month." },
    { "role": "assistant", "content": "The three largest moves were..." }
  ],
  "context_days": 30
}
```

**Response**

```json
{
  "response": "The sharp decline on Jan 27 appears to be linked to...",
  "ticker": "AAPL",
  "movements_analyzed": 4,
  "context_used": true
}
```

**curl example**

```bash
curl -X POST "http://localhost:8000/api/v1/chat/AAPL" \
  -H "Content-Type: application/json" \
  -d '{"message": "What caused the biggest movement this quarter?", "context_days": 90, "include_macro": true}'
```

---

## Running without API keys

| Key missing | Behaviour |
|---|---|
| `NEWS_API_KEY` | Falls back to **yfinance's Yahoo Finance news feed** (free, no date filter, ~10 most recent articles) |
| `OPENAI_API_KEY` | `/chat` returns a structured text summary of movements instead of AI analysis |

---

## Design decisions & trade-offs

### Movement definition
`change_pct = (Close − Open) / Open × 100`  
Intra-day open-to-close rather than close-to-close was chosen to capture news-driven moves *during* the trading session, avoiding overnight gap ambiguity.

### Caching
An in-memory TTL cache (default 30 min) avoids hammering yfinance and NewsAPI on repeated requests. For a production system this would be Redis or a similar shared cache.

### News window
Each movement day searches `[date − 2 days, date + 1 day]` for news. The asymmetric window reflects that catalysts (earnings releases, Fed decisions) are often published the evening *before* or the morning *of* the movement.

### NewsAPI free tier limits
Free tier: 100 requests/day, articles from the past 30 days only.  
For historical analysis beyond 30 days, upgrading to a paid NewsAPI plan (or switching to a paid source like Exa AI) is needed.

### Rate limit handling
The API includes intelligent rate limit detection and will warn when news articles may be missing due to API quota limits. Consider reducing the number of categories (competitor/macro) or checking your NewsAPI quota if you see warnings.

**yfinance rate limits**: Yahoo Finance implements rate limiting on free requests. The system automatically retries with exponential backoff (up to 6 attempts) and provides clear error messages when rate limits are exceeded. If you encounter rate limiting, please wait a few minutes before trying again.

### LLM-enhanced competitor detection
When `include_competitors=true`, the system uses OpenAI to identify specific public competitors for more targeted news queries, falling back to sector/industry keywords if the LLM call fails.

### Chat context
The full movement + news dataset is serialised into a compact structured block and injected as a system message. This gives the LLM a faithful, grounded view of the data rather than relying on its pre-training knowledge of specific events.

---

## Testing

The project includes a comprehensive test suite (`test_app.py`) that verifies:
- Stock price fetching and movement detection
- News fetching across all categories
- LLM-powered competitor identification
- Chat functionality with and without API keys
- Rate limit handling and error scenarios

Run tests with:
```bash
python test_app.py
```

---

## Project structure

```
stock-analyzer/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app — routes & middleware
│   ├── models.py        # Pydantic request/response schemas
│   ├── stock_data.py    # yfinance price history + movement detection
│   ├── news_fetcher.py  # NewsAPI client + query builders + LLM competitor detection
│   ├── analyzer.py      # Orchestration + in-memory cache + rate limit handling
│   └── chat.py          # OpenAI chat + context builder
├── tests/
│   └── test_news_aggregator/
├── .env.example
├── requirements.txt
├── test_app.py         # Comprehensive test suite
└── README.md
```
