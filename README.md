# Stock Analyzer

A full-stack application that analyzes major stock price movements and correlates them with relevant news articles using Yahoo Finance and NewsAPI.

## Features

- **Real-time Stock Data**: Fetches historical price data using Yahoo Finance (yfinance)
- **News Correlation**: Matches significant price movements with relevant news articles
- **AI-Powered Chat**: Ask questions about stock movements using OpenAI GPT
- **Beautiful UI**: Modern React frontend with TailwindCSS
- **Three News Categories**:
  - Company-specific news (earnings, product launches, etc.)
  - Competitor/industry news
  - Macro/geopolitical news

## Architecture

### Backend (FastAPI)
- **Yahoo Finance Integration**: Uses `yfinance` with `curl_cffi` to bypass rate limits
- **News Aggregation**: Optional NewsAPI integration for comprehensive news coverage
- **Smart Caching**: 30-minute TTL cache for API responses
- **AI Chat**: OpenAI-powered conversational analysis

### Frontend (React + TypeScript)
- Modern UI with Lucide icons and TailwindCSS
- Real-time stock analysis visualization
- Interactive chat interface
- Responsive design

## Setup

### Prerequisites
- Python 3.9+
- Node.js 16+
- npm or yarn

### Backend Setup

1. **Install Python dependencies**:
```bash
pip install -r requirements.txt
```

2. **Configure environment variables**:
```bash
cp .env.example .env
```

Edit `.env` and add your API keys:
- `NEWSAPI_KEY` (optional): Get from https://newsapi.org
- `OPENAI_API_KEY` (optional): Get from https://platform.openai.com/api-keys

**Note**: The app works without these keys:
- Without NewsAPI: Falls back to Yahoo Finance news (limited to recent articles)
- Without OpenAI: Chat returns structured text summaries instead of AI responses

3. **Run the backend server**:
```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/api/v1/health`

### Frontend Setup

1. **Navigate to frontend directory**:
```bash
cd frontend
```

2. **Install dependencies**:
```bash
npm install
```

3. **Start the development server**:
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Usage

1. **Start both servers** (backend on port 8000, frontend on port 5173)

2. **Enter a stock ticker** (e.g., AAPL, TSLA, MSFT) in the search bar

3. **View analysis**:
   - Major price movements (default: ±2% intraday change)
   - Related news articles for each movement
   - Summary statistics (up/down days, period, etc.)

4. **Chat with AI** (if OpenAI key is configured):
   - Ask questions like "Why did the stock drop in January?"
   - Get AI-powered explanations based on the data

## API Endpoints

### `GET /api/v1/health`
Check API status and configuration

### `GET /api/v1/analysis/{ticker}`
Get stock analysis with movements and news

**Query Parameters**:
- `start_date`: Start date (YYYY-MM-DD), default: 90 days ago
- `end_date`: End date (YYYY-MM-DD), default: today
- `min_movement_pct`: Minimum % change threshold, default: 2.0
- `include_competitors`: Include competitor news, default: false
- `include_macro`: Include macro news, default: false
- `max_articles`: Max articles per category, default: 5
- `use_mock`: Use mock data for testing, default: false

### `POST /api/v1/chat/{ticker}`
Chat about a ticker's movements

**Request Body**:
```json
{
  "message": "Why did the stock move?",
  "history": [],
  "context_days": 60,
  "min_movement_pct": 2.0,
  "include_competitors": false,
  "include_macro": false
}
```

## How It Works

1. **Data Fetching**: 
   - Fetches historical OHLCV data from Yahoo Finance
   - Uses `curl_cffi` to bypass rate limiting

2. **Movement Detection**:
   - Calculates intraday % change: `(Close - Open) / Open * 100`
   - Flags movements exceeding the threshold (default ±2%)

3. **News Correlation**:
   - Searches for news in a window around each movement date
   - Default: 2 days before, 1 day after
   - Categories: company-specific, competitor, macro

4. **AI Analysis** (optional):
   - Builds structured context from stock + news data
   - Uses OpenAI GPT to explain movements
   - Supports multi-turn conversations

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEWSAPI_KEY` | No | - | NewsAPI key for comprehensive news |
| `OPENAI_API_KEY` | No | - | OpenAI key for AI chat |
| `OPENAI_MODEL` | No | gpt-4o-mini | OpenAI model to use |
| `MIN_MOVEMENT_PCT` | No | 2.0 | Default movement threshold |
| `CACHE_TTL_SECONDS` | No | 1800 | Cache duration (30 min) |

## Troubleshooting

### Yahoo Finance Rate Limiting
- The app uses `curl_cffi` to bypass rate limits
- If you still encounter issues, try reducing the date range

### No News Articles
- Without NewsAPI key: Only recent news from Yahoo Finance
- Yahoo Finance news is limited to ~10 most recent articles
- For historical analysis, configure NewsAPI key

### OpenAI Errors
- Check your API key is valid
- Verify you have sufficient credits
- The app falls back to text summaries if OpenAI fails

## Development

### Project Structure
```
stock-analyzer/
├── app/                    # Backend (FastAPI)
│   ├── main.py            # API routes
│   ├── analyzer.py        # Analysis orchestration
│   ├── stock_data.py      # Yahoo Finance integration
│   ├── news_fetcher.py    # NewsAPI integration
│   ├── chat.py            # OpenAI chat
│   └── models.py          # Pydantic models
├── frontend/              # Frontend (React)
│   ├── src/
│   │   ├── App.tsx        # Main component
│   │   └── api.ts         # API client
│   └── package.json
├── requirements.txt       # Python dependencies
└── .env.example          # Environment template
```

## License

MIT
