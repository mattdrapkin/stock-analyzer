# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                         │
│                     http://localhost:5173                        │
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ Search Input │───▶│ Analysis View│───▶│  Chat Panel  │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                    │                    │              │
│         └────────────────────┴────────────────────┘              │
│                              │                                   │
│                         api.ts (Axios)                           │
└──────────────────────────────┼──────────────────────────────────┘
                               │ HTTP/JSON
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                           │
│                     http://localhost:8000                        │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                      main.py (Routes)                       │ │
│  │  • GET  /api/v1/health                                      │ │
│  │  • GET  /api/v1/analysis/{ticker}                           │ │
│  │  • POST /api/v1/chat/{ticker}                               │ │
│  └────────────┬───────────────────────────┬────────────────────┘ │
│               │                           │                      │
│               ▼                           ▼                      │
│  ┌────────────────────┐      ┌────────────────────┐            │
│  │   analyzer.py      │      │     chat.py        │            │
│  │  • build_analysis  │      │  • chat_with_ticker│            │
│  │  • cache results   │      │  • format context  │            │
│  └─────┬──────────────┘      └──────┬─────────────┘            │
│        │                             │                          │
│        ▼                             │                          │
│  ┌────────────────────┐              │                          │
│  │  stock_data.py     │              │                          │
│  │  • fetch_price     │              │                          │
│  │  • detect_moves    │              │                          │
│  │  • get_info        │              │                          │
│  └─────┬──────────────┘              │                          │
│        │                             │                          │
│        ▼                             │                          │
│  ┌────────────────────┐              │                          │
│  │  news_fetcher.py   │◀─────────────┘                          │
│  │  • fetch_news      │                                         │
│  │  • categorize      │                                         │
│  └─────┬──────────────┘                                         │
└────────┼────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      External Services                           │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │Yahoo Finance │  │   NewsAPI    │  │    OpenAI    │          │
│  │  (yfinance)  │  │  (optional)  │  │  (optional)  │          │
│  │              │  │              │  │              │          │
│  │ • Price data │  │ • News       │  │ • Chat AI    │          │
│  │ • Company    │  │ • Historical │  │ • Analysis   │          │
│  │ • News feed  │  │ • Filtered   │  │              │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow: Stock Analysis Request

```
1. User enters ticker "AAPL" in frontend
   │
   ▼
2. Frontend calls: GET /api/v1/analysis/AAPL
   │
   ▼
3. Backend main.py receives request
   │
   ▼
4. analyzer.py checks cache
   │
   ├─ Cache hit? → Return cached result
   │
   └─ Cache miss? → Continue
      │
      ▼
5. stock_data.py fetches from Yahoo Finance
   │
   ├─ Price history (OHLCV data)
   ├─ Company info (name, sector, industry)
   └─ Detect major movements (±2% default)
      │
      ▼
6. For each movement, news_fetcher.py queries:
   │
   ├─ NewsAPI (if key configured)
   │  └─ Company news
   │  └─ Competitor news (if enabled)
   │  └─ Macro news (if enabled)
   │
   └─ Yahoo Finance news (fallback)
      │
      ▼
7. analyzer.py combines data into TickerAnalysis
   │
   ├─ Cache result (30 min TTL)
   │
   └─ Return JSON response
      │
      ▼
8. Frontend displays:
   │
   ├─ Company info card
   ├─ Movement timeline
   └─ News articles per movement
```

## Data Flow: Chat Request

```
1. User asks: "Why did AAPL drop in January?"
   │
   ▼
2. Frontend calls: POST /api/v1/chat/AAPL
   │
   ▼
3. chat.py receives request
   │
   ▼
4. Calls analyzer.py to get stock data
   │ (same flow as above)
   ▼
5. Formats data as structured context
   │
   ▼
6. Sends to OpenAI with:
   │
   ├─ System prompt (financial analyst role)
   ├─ Stock + news context
   ├─ Conversation history
   └─ User question
      │
      ▼
7. OpenAI returns analysis
   │
   ▼
8. Frontend displays chat response
```

## Key Components

### Frontend (`frontend/src/`)
- **App.tsx**: Main UI component with search, analysis view, and chat
- **api.ts**: Axios client for backend communication
- **TailwindCSS**: Styling framework
- **Lucide Icons**: Icon library

### Backend (`app/`)
- **main.py**: FastAPI application with CORS, routes, and error handling
- **analyzer.py**: Orchestrates data fetching and caching
- **stock_data.py**: Yahoo Finance integration with rate limit bypass
- **news_fetcher.py**: NewsAPI integration with category support
- **chat.py**: OpenAI integration for conversational analysis
- **models.py**: Pydantic models for type safety

### External Dependencies
- **yfinance**: Yahoo Finance API wrapper
- **curl_cffi**: Bypass Yahoo Finance rate limits
- **newsapi-python**: NewsAPI client (optional)
- **openai**: OpenAI API client (optional)
- **FastAPI**: Modern Python web framework
- **React**: Frontend framework

## Caching Strategy

```
Cache Key Format:
{ticker}|{start_date}|{end_date}|{min_pct}|{competitors}|{macro}|{max_articles}

Example:
AAPL|2024-02-20|2024-05-20|2.0|False|False|5

TTL: 30 minutes (configurable via CACHE_TTL_SECONDS)
```

## Error Handling

### Backend
- Invalid ticker → 404 with error message
- Yahoo Finance rate limit → Exponential backoff retry (4 attempts)
- NewsAPI failure → Falls back to Yahoo Finance news
- OpenAI failure → Returns structured text summary
- All errors logged with context

### Frontend
- Network errors → Display error banner
- Invalid responses → Fallback to error state
- Loading states → Spinner indicators
- Empty results → Helpful empty state messages

## Security Considerations

1. **API Keys**: Stored in `.env` (not committed to git)
2. **CORS**: Configured to allow frontend origin
3. **Rate Limiting**: curl_cffi bypasses Yahoo Finance limits
4. **Input Validation**: Pydantic models validate all inputs
5. **Error Messages**: No sensitive data in error responses

## Performance Optimizations

1. **Caching**: 30-minute TTL reduces API calls
2. **Parallel Requests**: Frontend can make multiple requests
3. **Lazy Loading**: News expanded on demand
4. **Rate Limit Bypass**: curl_cffi for Yahoo Finance
5. **Efficient Queries**: NewsAPI limited to relevant date ranges

## Scalability Considerations

Current implementation is suitable for:
- Personal use
- Small teams
- Development/testing

For production scale, consider:
- Redis for distributed caching
- Database for historical data storage
- Rate limiting middleware
- Load balancing
- Async task queue for slow operations
