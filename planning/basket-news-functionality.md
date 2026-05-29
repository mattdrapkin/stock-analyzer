# Basket News Functionality Implementation Plan

## Overview
Add comprehensive news functionality to the basket analysis feature, similar to the single ticker analysis. This includes:
- Holistic summary explaining why the basket moved the way it did
- Individual news articles for each stock in the basket
- AI-generated insights using OpenAI web search

## Current State
- **Basket analyzer** (`basket_analyzer.py`): Only calculates price changes, no news
- **Single ticker analyzer** (`analyzer.py`): Full news functionality with OpenAI web search
- **Frontend**: Shows basket performance but no news display
- **Models**: Has NewsCard, NewsArticle, NewsCategory for single ticker analysis

## Implementation Steps

### Step 1: Update Backend Models
**File**: `app/models.py`

**Changes**:
- Add `news_cards: List[NewsCard]` field to `BasketTickerResult`
- Add `holistic_summary: Optional[str]` field to `BasketAnalysisResponse`
- Add `news_source: str` field to track news source (OpenAI vs Mock)

**Rationale**: Extend existing models to include news data without breaking changes.

### Step 2: Implement News Fetching for Individual Stocks
**File**: `app/basket_analyzer.py`

**Changes**:
- Import `fetch_batch_news_for_period` from `news_fetcher.py`
- Import `get_ticker_info` from `stock_data.py`
- For each ticker in the basket:
  - Fetch company name, sector, industry
  - Call `fetch_batch_news_for_period` with the date range
  - Attach news cards to the `BasketTickerResult`
- Handle rate limiting gracefully (fall back to no news or mock data)
- Add optional parameters for `include_competitors` and `include_macro`

**Rationale**: Reuse existing news fetching infrastructure from single ticker analysis.

### Step 3: Implement Basket-Level Holistic Summary
**File**: `app/basket_analyzer.py` (new function)

**Changes**:
- Create `generate_basket_holistic_summary()` function
- Aggregate news from all stocks in the basket
- Identify common themes (sector-wide movements, macro events)
- Use OpenAI Chat API to generate a 2-3 sentence summary
- Summary should explain:
  - Overall basket movement direction
  - Key drivers (sector trends, macro events, company-specific news)
  - Why big movers moved significantly

**Rationale**: Provide high-level context for basket performance, similar to single ticker holistic summary.

### Step 4: Update Basket API Endpoint
**File**: `app/main.py`

**Changes**:
- Add optional query parameters to basket endpoint:
  - `include_news: bool = False`
  - `include_competitors: bool = False`
  - `include_macro: bool = False`
- Pass these parameters to `analyze_basket()`
- Update docstring to document new parameters

**Rationale**: Make news fetching optional to maintain performance and control costs.

### Step 5: Update Frontend API Client
**File**: `frontend/src/api.ts`

**Changes**:
- Update `BasketAnalysisResponse` interface to include new fields
- Update `analyzeBasket()` function to accept optional news parameters
- Add TypeScript types for news cards

**Rationale**: Ensure frontend can handle new response structure.

### Step 6: Add Holistic Summary Display to Basket UI
**File**: `frontend/src/App.tsx`

**Changes**:
- Add state for `basketHolisticSummary` and `basketSummaryLoading`
- Add checkbox/toggle for "Include News" in basket form
- After basket analysis, if news enabled:
  - Call new API endpoint to fetch holistic summary
  - Display summary in collapsible section at top of basket results
- Use similar styling as single ticker holistic summary

**Rationale**: Provide users with high-level insights about basket performance.

### Step 7: Add News Articles Display to Individual Stock Cards
**File**: `frontend/src/App.tsx`

**Changes**:
- Update `BasketResultCard` component to be expandable
- When expanded, show news cards for that specific stock
- Reuse `NewsCardItem` component from single ticker view
- Add news count badge to stock cards
- Handle case where no news is available

**Rationale**: Allow users to drill down into news for individual stocks.

### Step 8: Add Navigation Section for Basket News
**File**: `frontend/src/App.tsx`

**Changes**:
- Add "Basket News Highlights" section to navigation
- Only visible when basket has news data
- Scroll to section when clicked

**Rationale**: Improve UX with consistent navigation pattern.

### Step 9: Testing
**Files**: Multiple

**Testing checklist**:
- Test basket analysis without news (baseline)
- Test basket analysis with news enabled
- Test with small basket (2-3 tickers)
- Test with large basket (10+ tickers)
- Test rate limiting behavior
- Test with sectors that have clear themes (e.g., metals/mining)
- Test frontend display of holistic summary
- Test expansion of individual stock news cards
- Test navigation to news sections
- Verify performance with news fetching

## Technical Considerations

### Performance
- News fetching is done in parallel for all tickers to minimize latency
- Consider caching news data per ticker to avoid redundant API calls
- Add timeout handling for news fetching

### Rate Limiting
- Implement graceful fallback when OpenAI rate limits are hit
- Consider adding a delay between ticker news fetches if needed
- Log rate limit events for monitoring

### Cost Control
- Make news fetching opt-in to control OpenAI API costs
- Consider adding a limit on number of news cards per ticker
- Add configuration for max articles per category

### Error Handling
- Handle cases where individual ticker news fetch fails
- Continue basket analysis even if some news fetches fail
- Provide clear error messages to users

## Commit Strategy

Use atomic commits for each step:
1. "Update basket models to include news fields"
2. "Implement news fetching for individual stocks in basket"
3. "Add basket-level holistic summary generation"
4. "Update basket API endpoint with news parameters"
5. "Update frontend API client for basket news"
6. "Add holistic summary display to basket UI"
7. "Add news display to individual stock cards"
8. "Add navigation section for basket news"
9. "Add tests for basket news functionality"

## Success Criteria

- [ ] Basket analysis returns news cards for each stock when enabled
- [ ] Holistic summary explains basket movement drivers
- [ ] Frontend displays summary at top of basket results
- [ ] Individual stock cards show news when expanded
- [ ] Navigation works for news sections
- [ ] Performance is acceptable with news enabled
- [ ] Rate limiting is handled gracefully
- [ ] Tests pass for new functionality
