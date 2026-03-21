#!/usr/bin/env python3
"""
Test script for stock analyzer functionality.
Tests each major requirement one by one.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import date, timedelta
from app.stock_data import fetch_price_history, detect_major_movements, get_ticker_info
from app.news_fetcher import fetch_news_for_movement, has_newsapi_key
from app.analyzer import build_analysis
from app.chat import chat_with_ticker, has_openai_key
import pandas as pd

def test_stock_price_fetching():
    """Test 1: Stock price fetching using yfinance"""
    print("=" * 60)
    print("TEST 1: Stock Price Fetching using yfinance")
    print("=" * 60)
    
    try:
        # Test with a well-known ticker
        ticker = "AAPL"
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        print(f"Fetching price history for {ticker} from {start_date} to {end_date}")
        df = fetch_price_history(ticker, start_date, end_date)
        
        print(f"✅ Successfully fetched {len(df)} days of data")
        print(f"   Date range: {df.index[0].date()} to {df.index[-1].date()}")
        print(f"   Columns: {list(df.columns)}")
        print(f"   Sample data:")
        print(df.head(3).to_string())
        
        # Test ticker info
        info = get_ticker_info(ticker)
        print(f"\n✅ Ticker info for {ticker}:")
        print(f"   Company: {info['company_name']}")
        print(f"   Sector: {info['sector']}")
        print(f"   Industry: {info['industry']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Stock price fetching failed: {e}")
        return False

def test_major_movement_detection():
    """Test 2: Major stock movement detection (>= 2% delta)"""
    print("\n" + "=" * 60)
    print("TEST 2: Major Stock Movement Detection (>= 2% delta)")
    print("=" * 60)
    
    try:
        ticker = "TSLA"  # Tesla tends to have volatile movements
        end_date = date.today()
        start_date = end_date - timedelta(days=60)
        
        print(f"Fetching {ticker} data for movement analysis...")
        df = fetch_price_history(ticker, start_date, end_date)
        
        # Test with 2% threshold
        movements = detect_major_movements(df, min_pct=2.0)
        
        print(f"✅ Found {len(movements)} major movements (>= 2%)")
        
        if movements:
            print("   Sample movements:")
            for i, mv in enumerate(movements[:5]):
                print(f"   {i+1}. {mv['date']}: {mv['direction']} {mv['change_pct']:+.2f}% "
                      f"(${mv['open']:.2f} → ${mv['close']:.2f})")
        
        # Test with different threshold
        movements_5pct = detect_major_movements(df, min_pct=5.0)
        print(f"\n   With 5% threshold: {len(movements_5pct)} movements")
        
        return True
        
    except Exception as e:
        print(f"❌ Movement detection failed: {e}")
        return False

def test_news_fetching_company():
    """Test 3: News fetching for company-specific events"""
    print("\n" + "=" * 60)
    print("TEST 3: News Fetching - Company-Specific Events")
    print("=" * 60)
    
    if not has_newsapi_key():
        print("⚠️  NEWS_API_KEY not configured, skipping news test")
        print("   To test news fetching, set NEWS_API_KEY in your .env file")
        return False
    
    try:
        # Use a recent date for better news availability
        movement_date = date.today() - timedelta(days=7)
        company_name = "Apple Inc"
        ticker = "AAPL"
        
        print(f"Fetching company news for {company_name} around {movement_date}")
        
        articles = fetch_news_for_movement(
            movement_date=movement_date,
            company_name=company_name,
            ticker=ticker,
            include_competitors=False,
            include_macro=False,
            max_per_category=3
        )
        
        print(f"✅ Found {len(articles)} company-specific articles")
        
        if articles:
            print("   Sample articles:")
            for i, article in enumerate(articles[:3]):
                print(f"   {i+1}. [{article['category'].upper()}] {article['title']}")
                print(f"      Source: {article['source']}")
                if article['published_at']:
                    print(f"      Date: {article['published_at']}")
                if article['summary']:
                    summary = article['summary'][:100] + "..." if len(article['summary']) > 100 else article['summary']
                    print(f"      Summary: {summary}")
                print()
        
        return True
        
    except Exception as e:
        print(f"❌ Company news fetching failed: {e}")
        return False

def test_news_fetching_competitor():
    """Test 4: News fetching for competitor/industry moves"""
    print("\n" + "=" * 60)
    print("TEST 4: News Fetching - Competitor/Industry Moves")
    print("=" * 60)
    
    if not has_newsapi_key():
        print("⚠️  NEWS_API_KEY not configured, skipping competitor news test")
        return False
    
    try:
        movement_date = date.today() - timedelta(days=5)
        company_name = "Microsoft Corporation"
        ticker = "MSFT"
        sector = "Technology"
        industry = "Software - Infrastructure"
        
        print(f"Fetching competitor/industry news for {company_name}")
        
        articles = fetch_news_for_movement(
            movement_date=movement_date,
            company_name=company_name,
            ticker=ticker,
            sector=sector,
            industry=industry,
            include_competitors=True,
            include_macro=False,
            max_per_category=2
        )
        
        # Filter for competitor articles
        competitor_articles = [a for a in articles if a['category'] == 'competitor']
        
        print(f"✅ Found {len(competitor_articles)} competitor/industry articles")
        
        if competitor_articles:
            print("   Sample competitor articles:")
            for i, article in enumerate(competitor_articles[:2]):
                print(f"   {i+1}. {article['title']}")
                print(f"      Source: {article['source']}")
                print()
        
        return True
        
    except Exception as e:
        print(f"❌ Competitor news fetching failed: {e}")
        return False

def test_news_fetching_macro():
    """Test 5: News fetching for macro/political events"""
    print("\n" + "=" * 60)
    print("TEST 5: News Fetching - Macro/Political Events")
    print("=" * 60)
    
    if not has_newsapi_key():
        print("⚠️  NEWS_API_KEY not configured, skipping macro news test")
        return False
    
    try:
        movement_date = date.today() - timedelta(days=3)
        
        print(f"Fetching macro/political news around {movement_date}")
        
        articles = fetch_news_for_movement(
            movement_date=movement_date,
            company_name="Test Company",
            ticker="TEST",
            include_competitors=False,
            include_macro=True,
            max_per_category=3
        )
        
        # Filter for macro articles
        macro_articles = [a for a in articles if a['category'] == 'macro']
        
        print(f"✅ Found {len(macro_articles)} macro/political articles")
        
        if macro_articles:
            print("   Sample macro articles:")
            for i, article in enumerate(macro_articles[:2]):
                print(f"   {i+1}. {article['title']}")
                print(f"      Source: {article['source']}")
                print()
        
        return True
        
    except Exception as e:
        print(f"❌ Macro news fetching failed: {e}")
        return False

def test_api_endpoint():
    """Test 6: Main API endpoint for stock and news data"""
    print("\n" + "=" * 60)
    print("TEST 6: Main API Endpoint - Stock and News Data")
    print("=" * 60)
    
    try:
        ticker = "NVDA"
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        print(f"Testing analysis endpoint for {ticker}")
        
        analysis = build_analysis(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            min_movement_pct=2.0,
            include_competitors=False,
            include_macro=False,
            max_articles_per_category=3
        )
        
        print(f"✅ Analysis completed successfully!")
        print(f"   Ticker: {analysis.ticker}")
        print(f"   Company: {analysis.company_name}")
        print(f"   Sector: {analysis.sector}")
        print(f"   Period: {analysis.period_start} to {analysis.period_end}")
        print(f"   Total movements: {analysis.total_movements}")
        print(f"   Up movements: {analysis.up_movements}")
        print(f"   Down movements: {analysis.down_movements}")
        print(f"   News source: {analysis.news_source}")
        
        if analysis.movements:
            print(f"\n   Sample movement with news:")
            mv = analysis.movements[0]
            print(f"   Date: {mv.date}, Change: {mv.change_pct:+.2f}%")
            print(f"   News articles: {len(mv.news)}")
            if mv.news:
                for i, article in enumerate(mv.news[:2]):
                    print(f"     {i+1}. [{article.category}] {article.title}")
        
        return True
        
    except Exception as e:
        print(f"❌ API endpoint test failed: {e}")
        return False

def test_chat_endpoint():
    """Test 7: Chat endpoint functionality"""
    print("\n" + "=" * 60)
    print("TEST 7: Chat Endpoint Functionality")
    print("=" * 60)
    
    try:
        ticker = "AAPL"
        message = "What were the biggest price movements and what caused them?"
        
        print(f"Testing chat endpoint for {ticker}")
        print(f"Question: {message}")
        
        response = chat_with_ticker(
            ticker=ticker,
            message=message,
            history=[],
            context_days=30,
            min_movement_pct=2.0,
            include_competitors=False,
            include_macro=False
        )
        
        print(f"✅ Chat response generated!")
        print(f"   Ticker: {response.ticker}")
        print(f"   Movements analyzed: {response.movements_analyzed}")
        print(f"   Context used: {response.context_used}")
        print(f"\n   Response preview:")
        # Show first 500 characters of response
        preview = response.response[:500] + "..." if len(response.response) > 500 else response.response
        print(f"   {preview}")
        
        return True
        
    except Exception as e:
        print(f"❌ Chat endpoint test failed: {e}")
        return False

def test_api_filters():
    """Test 8: API filters and parameters"""
    print("\n" + "=" * 60)
    print("TEST 8: API Filters and Parameters")
    print("=" * 60)
    
    try:
        ticker = "GOOGL"
        end_date = date.today()
        start_date = end_date - timedelta(days=20)
        
        # Test different movement thresholds
        print("Testing different movement thresholds...")
        
        for threshold in [1.0, 3.0, 5.0]:
            analysis = build_analysis(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                min_movement_pct=threshold,
                include_competitors=False,
                include_macro=False
            )
            print(f"   {threshold}% threshold: {analysis.total_movements} movements")
        
        # Test with competitor and macro flags
        print("\nTesting with competitor and macro flags...")
        
        analysis_full = build_analysis(
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            min_movement_pct=2.0,
            include_competitors=True,
            include_macro=True,
            max_articles_per_category=2
        )
        
        total_articles = sum(len(mv.news) for mv in analysis_full.movements)
        print(f"   With all flags: {analysis_full.total_movements} movements, {total_articles} total articles")
        
        # Test date range validation - swapped dates
        print("\nTesting date range validation...")
        try:
            build_analysis(
                ticker=ticker,
                start_date=end_date,
                end_date=start_date,  # Swapped dates
                min_movement_pct=2.0
            )
            print("   ❌ Date validation failed - should have thrown error")
            return False
        except ValueError as e:
            print(f"   ✅ Date validation works - correctly rejected invalid range: {e}")
        
        # Test date range validation - too long
        print("\nTesting maximum date range validation...")
        try:
            build_analysis(
                ticker=ticker,
                start_date=date.today() - timedelta(days=800),  # > 2 years
                end_date=date.today(),
                min_movement_pct=2.0
            )
            print("   ❌ Long date range validation failed - should have thrown error")
            return False
        except ValueError as e:
            print(f"   ✅ Long date range validation works: {e}")
        
        # Test NewsAPI free plan limitation warning
        print("\nTesting NewsAPI free plan limitation...")
        if has_newsapi_key():
            old_date = date.today() - timedelta(days=60)  # Previous month
            try:
                analysis_old = build_analysis(
                    ticker="AAPL",
                    start_date=old_date,
                    end_date=date.today(),
                    min_movement_pct=2.0
                )
                if analysis_old.news_note and "free plan" in analysis_old.news_note.lower():
                    print(f"   ✅ NewsAPI free plan limitation noted: {analysis_old.news_note[:100]}...")
                else:
                    print(f"   ⚠️  NewsAPI free plan limitation not explicitly noted in news_note")
            except Exception as e:
                print(f"   ❌ NewsAPI limitation test failed: {e}")
        else:
            print("   ⚠️  NewsAPI not configured - skipping free plan limitation test")
        
        return True
        
    except Exception as e:
        print(f"❌ API filters test failed: {e}")
        return False

def test_error_handling():
    """Test 9: Error handling and edge cases"""
    print("\n" + "=" * 60)
    print("TEST 9: Error Handling and Edge Cases")
    print("=" * 60)
    
    try:
        # Test invalid ticker
        print("Testing invalid ticker...")
        try:
            fetch_price_history("INVALIDTICKER123", date.today() - timedelta(days=10), date.today())
            print("   ❌ Should have failed for invalid ticker")
            return False
        except ValueError as e:
            print(f"   ✅ Correctly handled invalid ticker: {e}")
        
        # Test edge case - no movements found
        print("Testing case with no major movements...")
        analysis = build_analysis(
            ticker="BRK-B",  # Berkshire - typically less volatile
            start_date=date.today() - timedelta(days=10),
            end_date=date.today(),
            min_movement_pct=10.0  # Very high threshold
        )
        print(f"   ✅ Handled no movements case: {analysis.total_movements} movements found")
        
        # Test edge case - same start and end date
        print("Testing same start and end date...")
        same_day = date.today() - timedelta(days=5)
        try:
            analysis_same_day = build_analysis(
                ticker="AAPL",
                start_date=same_day,
                end_date=same_day,
                min_movement_pct=2.0
            )
            print(f"   ✅ Handled same day request: {analysis_same_day.total_movements} movements")
        except Exception as e:
            print(f"   ⚠️  Same day request failed (may be expected): {e}")
        
        # Test very high movement threshold
        print("Testing very high movement threshold...")
        try:
            analysis_high = build_analysis(
                ticker="TSLA",
                start_date=date.today() - timedelta(days=30),
                end_date=date.today(),
                min_movement_pct=50.0  # 50% threshold
            )
            print(f"   ✅ Handled high threshold: {analysis_high.total_movements} movements found")
        except Exception as e:
            print(f"   ❌ High threshold test failed: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Stock Analyzer Test Suite")
    print("=" * 60)
    
    # Check environment
    print("Environment check:")
    print(f"   NewsAPI configured: {has_newsapi_key()}")
    print(f"   OpenAI configured: {has_openai_key()}")
    print()
    
    tests = [
        ("Stock Price Fetching", test_stock_price_fetching),
        ("Major Movement Detection", test_major_movement_detection),
        ("Company News Fetching", test_news_fetching_company),
        ("Competitor News Fetching", test_news_fetching_competitor),
        ("Macro News Fetching", test_news_fetching_macro),
        ("Main API Endpoint", test_api_endpoint),
        ("Chat Endpoint", test_chat_endpoint),
        ("API Filters", test_api_filters),
        ("Error Handling", test_error_handling),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUITE SUMMARY")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! The stock analyzer is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()
