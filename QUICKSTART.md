# Quick Start Guide

Get the Stock Analyzer running in under 2 minutes!

## One-Command Start

```bash
./start.sh
```

This script will:
1. Create a virtual environment (if needed)
2. Install all dependencies
3. Start both backend and frontend servers
4. Open the app at `http://localhost:5173`

## Manual Start

### Backend
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start server
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## First Steps

1. **Open the app**: Navigate to `http://localhost:5173`

2. **Try a stock**: Enter a ticker like `AAPL`, `TSLA`, or `MSFT`

3. **View the analysis**: See major price movements and related news

## Optional: Add API Keys

For enhanced features, edit `.env` and add:

```bash
# For comprehensive news coverage
NEWSAPI_KEY=your_key_here

# For AI-powered chat
OPENAI_API_KEY=your_key_here
```

**The app works without these keys!**
- Without NewsAPI: Uses Yahoo Finance news (limited to recent articles)
- Without OpenAI: Chat returns structured summaries instead of AI responses

## Test the API

Visit `http://localhost:8000/docs` for interactive API documentation.

Try these endpoints:
- `GET /api/v1/health` - Check system status
- `GET /api/v1/analysis/AAPL` - Get Apple stock analysis

## Troubleshooting

**Port already in use?**
```bash
# Kill processes on ports 8000 and 5173
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9
```

**Dependencies not installing?**
```bash
# Update pip
pip install --upgrade pip

# Try again
pip install -r requirements.txt
```

**Frontend not starting?**
```bash
# Clear npm cache
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## What's Next?

- Read the full [README.md](README.md) for detailed documentation
- Explore the API at `http://localhost:8000/docs`
- Try different tickers and date ranges
- Enable AI chat with OpenAI API key

Enjoy analyzing stocks! 📈
