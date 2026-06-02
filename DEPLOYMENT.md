# Deployment Guide

This guide will help you deploy the Stock Analyzer application to production.

## Architecture

- **Frontend**: React + Vite app deployed on Vercel
- **Backend**: FastAPI Python app deployed on Render (or Railway/Fly.io)

## Prerequisites

- GitHub account with the code pushed to a repository
- Vercel account (free tier works)
- Render account (free tier works) - or alternative like Railway/Fly.io
- API keys (optional but recommended):
  - `OPENAI_API_KEY` for AI chat features
  - `NEWSAPI_KEY` for comprehensive news coverage

## Step 1: Deploy Backend (Render)

### Option A: Using Render (Recommended)

1. **Push your code to GitHub** if you haven't already

2. **Create a new Render service**:
   - Go to [dashboard.render.com](https://dashboard.render.com)
   - Click "New +"
   - Select "Web Service"
   - Connect your GitHub repository
   - Configure the service:
     - **Name**: `stock-analyzer-api` (or your preferred name)
     - **Region**: Choose the region closest to your users
     - **Branch**: `main`
     - **Runtime**: `Python`
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
     - **Instance Type**: Free (or paid for better performance)

3. **Add Environment Variables** (in the Environment section):
   - `PORT`: `8000`
   - `PYTHON_VERSION`: `3.9.0`
   - `OPENAI_API_KEY`: (optional) Your OpenAI API key
   - `NEWSAPI_KEY`: (optional) Your NewsAPI key
   - `OPENAI_MODEL`: `gpt-4o-mini` (or your preferred model)
   - `MIN_MOVEMENT_PCT`: `2.0`
   - `CACHE_TTL_SECONDS`: `1800`

4. **Click "Create Web Service"** and wait for deployment

5. **Copy your backend URL** (e.g., `https://stock-analyzer-api.onrender.com`)

### Option B: Using Railway

1. Go to [railway.app](https://railway.app)
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Connect your repository
5. Railway will auto-detect Python. Configure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables (same as above)
7. Deploy and copy the backend URL

### Option C: Using Fly.io

1. Install Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Run: `fly launch`
3. Follow the prompts to configure
4. Set environment variables: `fly secrets set OPENAI_API_KEY=your_key`
5. Deploy: `fly deploy`

## Step 2: Deploy Frontend (Vercel)

1. **Install Vercel CLI** (optional, or use the web dashboard):
   ```bash
   npm i -g vercel
   ```

2. **Deploy using Vercel CLI**:
   ```bash
   cd frontend
   vercel
   ```
   Follow the prompts:
   - Link to your existing project or create new
   - Set the project name
   - When asked about environment variables, add:
     - `VITE_API_BASE_URL`: Your backend URL from Step 1 (e.g., `https://stock-analyzer-api.onrender.com/api/v1`)

3. **Or deploy using Vercel Dashboard**:
   - Go to [vercel.com](https://vercel.com)
   - Click "Add New Project"
   - Import your GitHub repository
   - Configure:
     - **Framework Preset**: Vite
     - **Root Directory**: `frontend`
     - **Build Command**: `npm run build`
     - **Output Directory**: `dist`
   - Add environment variable:
     - `VITE_API_BASE_URL`: Your backend URL
   - Click "Deploy"

4. **Copy your frontend URL** (e.g., `https://stock-analyzer.vercel.app`)

## Step 3: Configure CORS (if needed)

If you encounter CORS errors, update the backend CORS settings in `app/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-url.vercel.app"],  # Replace with your Vercel URL
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Then redeploy the backend.

## Step 4: Test the Deployment

1. Visit your frontend URL
2. Try searching for a stock ticker (e.g., AAPL)
3. Verify that:
   - The UI loads correctly
   - API calls work
   - Stock data displays
   - News articles appear (if API keys are configured)

## Environment Variables Reference

### Backend (Render/Railway/Fly.io)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PORT` | Yes | 8000 | Port for the server |
| `PYTHON_VERSION` | No | 3.9.0 | Python version |
| `OPENAI_API_KEY` | No | - | OpenAI API key for AI chat |
| `NEWSAPI_KEY` | No | - | NewsAPI key for news |
| `OPENAI_MODEL` | No | gpt-4o-mini | OpenAI model |
| `MIN_MOVEMENT_PCT` | No | 2.0 | Movement threshold |
| `CACHE_TTL_SECONDS` | No | 1800 | Cache duration |

### Frontend (Vercel)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_BASE_URL` | Yes | http://localhost:8000/api/v1 | Backend API URL |

## Troubleshooting

### Backend Issues

- **Build fails**: Check that all dependencies in `requirements.txt` are compatible
- **Runtime errors**: Check Render logs for detailed error messages
- **API timeouts**: The free tier has spin-up time (cold starts). Consider upgrading for production

### Frontend Issues

- **Build fails**: Ensure `package.json` is not gitignored (fixed in this setup)
- **API errors**: Verify `VITE_API_BASE_URL` is set correctly in Vercel
- **CORS errors**: Update backend CORS settings to allow your frontend domain

### Common Issues

- **Missing API keys**: The app works without them, but features will be limited
- **Rate limiting**: Yahoo Finance has rate limits; consider adding caching or using a proxy
- **Free tier limitations**: Both Vercel and Render have limits on free tiers

## Cost Estimates

- **Vercel (Frontend)**: Free tier includes:
  - 100GB bandwidth per month
  - Unlimited deployments
  - SSL certificates
  - Automatic HTTPS

- **Render (Backend)**: Free tier includes:
  - 750 hours per month
  - 512MB RAM
  - Spins down after 15 minutes of inactivity
  - Cold starts (~30 seconds)

- **Paid tiers**: Recommended for production:
  - Render: ~$7/month for basic web service
  - Vercel: $20/month for Pro plan (no cold starts)

## Alternative: Single-Repository Deployment

If you prefer to deploy both frontend and backend from the same repository:

1. Keep the monorepo structure as-is
2. Deploy backend to Render using the root directory
3. Deploy frontend to Vercel using the `frontend/` subdirectory
4. Configure Vercel to build from the `frontend/` directory

## Monitoring

- **Render**: View logs in the Render dashboard
- **Vercel**: View logs and analytics in the Vercel dashboard
- **Health check**: Access `/api/v1/health` endpoint to verify backend status

## Next Steps

1. Set up a custom domain (optional)
2. Configure analytics (Vercel Analytics, Google Analytics)
3. Set up error tracking (Sentry, etc.)
4. Add monitoring/alerts for production issues
5. Consider a database for persistent caching (Redis, etc.)
