# Web Search Migration Guide

## Overview

The stock analyzer has been redesigned to use **OpenAI's Responses API with web_search tool** instead of NewsAPI. This provides several key advantages:

### Benefits

1. **Direct Source Citations**: Every news summary includes clickable source URLs from the web search results
2. **AI-Generated Summaries**: Quick-glance insights powered by AI that synthesize multiple sources
3. **Real-Time Data**: Access to up-to-date information from the internet, not limited to a specific news API's coverage
4. **Better Context**: The AI can analyze and summarize news in the context of stock movements
5. **Simplified Dependencies**: No need for separate NewsAPI key
6. **Rate Limit Resilience**: Exponential backoff retry logic prevents tight retry loops
7. **Optimized Batching**: One API call per basket (not per stock) reduces rate limit pressure

## Architecture Changes

### Before (NewsAPI)
```
User Request → NewsAPI Search → Raw Articles → Manual Filtering → Response
```

### After (OpenAI Responses API with web_search)
```
User Request → Responses API → web_search tool → AI Summary + Citations → Response
                      ↓
              Exponential Backoff Retry
                      ↓
              Rate Limiter (token bucket)
```

**Key Configuration:**
- `model="gpt-5.5"` - Recommended model for new integrations
- `tools=[{"type": "web_search", "search_context_size": "medium"}]` - Enables web search
- `tool_choice="required"` - Ensures web search is always performed for news fetching

## Key Components

### 1. Models (`app/models.py`)

**New Models Added:**

```python
class URLCitation(BaseModel):
    url: str
    title: str
    start_index: int
    end_index: int

class NewsSearchSummary(BaseModel):
    category: NewsCategory
    ai_summary: str
    sources: List[str] = []
    search_queries: List[str] = []
```

**Updated Models:**

```python
class NewsArticle(BaseModel):
    # ... existing fields ...
    citations: List[URLCitation] = []  # NEW

class StockMovement(BaseModel):
    # ... existing fields ...
    news_summaries: List[NewsSearchSummary] = []  # NEW
```

### 2. News Fetcher (`app/news_fetcher.py`)

**Core Function:**

```python
def _search_with_openai(search_prompt: str, category: str) -> Tuple[str, List[str], List[str]]:
    """
    Use OpenAI Responses API with web_search tool to find news.
    
    Returns:
        Tuple of (ai_summary, sources, search_queries)
    """
```

**Search Configuration:**

- **Model**: `gpt-5.5` (configurable via `OPENAI_SEARCH_MODEL`)
- **API**: Responses API with `web_search` tool
- **Tool Configuration**: `{"type": "web_search", "search_context_size": "medium"}`
- **Tool Choice**: `auto` (model decides when to search)
- **Temperature**: 0.3 for consistent, factual responses
- **Source Extraction**: Parses URLs from AI response using regex

**Search Prompts:**

The system builds targeted search prompts for each category:

- **Company**: Focuses on earnings, product launches, executive changes, lawsuits
- **Competitor**: Targets industry trends, competitor earnings, sector developments
- **Macro**: Searches for Fed decisions, interest rates, inflation, geopolitical events

### 3. Analyzer (`app/analyzer.py`)

The analyzer now:

1. Checks if OpenAI key is configured
2. Uses web search if available, falls back to mock data if not
3. Attaches `news_summaries` to each `StockMovement`
4. Maintains backward compatibility with `news` field for mock data

### 4. Chat (`app/chat.py`)

Updated to handle both formats:

- **Web Search Results**: Displays AI summaries with source URLs
- **Mock Data**: Displays individual articles (backward compatible)

### 5. Rate Limit Utils (`app/rate_limit_utils.py`)

**New Function:**

```python
def retry_with_exponential_backoff(
    func,
    max_retries: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    rate_limiter=None,
):
    """
    Execute a function with exponential backoff retry logic for rate limit errors.
    
    Follows OpenAI's recommendation:
    - Respects suggested wait times from error messages
    - Uses exponential backoff with jitter to avoid thundering herd
    - Non-rate-limit errors are raised immediately
    """
```

**Features:**
- Extracts suggested wait times from OpenAI error messages
- Falls back to exponential backoff with jitter if no suggestion
- Integrates with token bucket rate limiter
- Configurable retry limits and delays

## Configuration

### Environment Variables

```bash
# Required - used for both web search and chat
OPENAI_API_KEY=your_openai_key_here

# Optional - model for web search (default: gpt-5.5)
# Recommended: gpt-5.5 for new integrations with Responses API + web_search tool
OPENAI_SEARCH_MODEL=gpt-5.5

# Optional - search context size (default: medium)
# Options: low, medium, high
OPENAI_SEARCH_CONTEXT_SIZE=medium

# Optional - model for chat (default: gpt-5.4-nano)
OPENAI_MODEL=gpt-5.4-nano

# Optional - max requests per minute (default: 50)
OPENAI_MAX_RPM=50
```

### Removed Variables

- `NEWSAPI_KEY` - No longer needed

## API Response Format

### Stock Movement with Web Search

```json
{
  "date": "2024-01-15",
  "change_pct": 5.2,
  "direction": "up",
  "news_summaries": [
    {
      "category": "company",
      "ai_summary": "Apple announced record-breaking Q4 earnings...",
      "sources": [
        "https://www.bloomberg.com/...",
        "https://www.reuters.com/...",
        "https://www.cnbc.com/..."
      ],
      "search_queries": [
        "Apple earnings Q4 2024"
      ]
    }
  ]
}
```

## Migration Checklist

- [x] Remove `newsapi-python` dependency
- [x] Update models to support web search results
- [x] Rewrite news fetcher to use OpenAI Responses API
- [x] Update analyzer to use new web search
- [x] Update chat to handle both formats
- [x] Update .env.example with new configuration
- [x] Update API documentation

## Usage Examples

### Basic Analysis (Company News Only)

```bash
curl "http://localhost:8000/api/v1/analysis/AAPL?start_date=2024-01-01&end_date=2024-12-31"
```

### With Competitor News

```bash
curl "http://localhost:8000/api/v1/analysis/AAPL?include_competitors=true"
```

### With Macro News

```bash
curl "http://localhost:8000/api/v1/analysis/AAPL?include_macro=true"
```

## OpenAI Web Search Features Used

### From the Documentation

1. **Responses API with web_search tool**: Modern endpoint for web search integrations
2. **gpt-5.5 model**: Recommended model for new web search integrations
3. **Tool choice: auto**: Model decides when to use web search based on the query
4. **Search context size**: Configurable (low/medium/high) for controlling search depth
5. **Exponential backoff retry**: Follows OpenAI's recommendation for rate limit handling
6. **Batch requests**: One API call per basket (not per stock) to reduce rate limit pressure

### Not Currently Used (Future Enhancements)

- Domain filtering (`filters.allowed_domains` / `filters.blocked_domains`)
- User location for geo-specific results
- Deep research mode with higher reasoning levels
- Return token budget control for extended research
- Live internet access control (`external_web_access`)
- Tool choice: "required" (if search must always be used)

## Cost Considerations

### Web Search Pricing

- Each web search incurs a tool call cost (see [OpenAI pricing](https://developers.openai.com/api/docs/pricing#built-in-tools))
- Using `gpt-5.5` for search provides best results but costs more than smaller models
- Consider caching results (already implemented with 30-minute TTL)

### Optimization Tips

1. **Cache aggressively**: The default 30-minute cache helps reduce redundant searches
2. **Limit categories**: Only enable `include_competitors` and `include_macro` when needed
3. **Batch requests**: Analyze multiple movements in a single API call when possible
4. **Adjust search context size**: Use "low" for quick lookups, "medium" for balanced results, "high" for comprehensive research
5. **Rate limiting**: Configure `OPENAI_MAX_RPM` to prevent hitting API limits
6. **Exponential backoff**: Automatic retry with backoff handles transient rate limit errors

## Backward Compatibility

The system maintains backward compatibility:

- **Mock data mode**: Still available when OpenAI key is not configured
- **News field**: Still populated for mock data
- **Existing API contracts**: All endpoints work the same way

## Testing

### With OpenAI Key

```bash
export OPENAI_API_KEY=your_key_here
python -m uvicorn app.main:app --reload
```

### Without OpenAI Key (Mock Mode)

```bash
unset OPENAI_API_KEY
python -m uvicorn app.main:app --reload
```

## Troubleshooting

### "OpenAI API key not configured"

- Set `OPENAI_API_KEY` in your `.env` file or environment
- The system will fall back to mock data if the key is missing

### "Web search failed"

- Check your OpenAI API key is valid
- Verify you have sufficient API credits
- Check the logs for specific error messages

### Empty news summaries

- The AI may not find relevant news for all movements
- Try adjusting the date range or movement threshold
- Check if the ticker symbol is correct

## Future Enhancements

1. **Domain filtering**: Limit sources to trusted financial news sites
2. **Deep research mode**: For complex multi-source investigations
3. **Citation extraction**: Parse inline citations from AI responses
4. **Source quality scoring**: Rank sources by reliability
5. **Custom search prompts**: Allow users to customize search queries
