"""
Basket Analysis: Compare multiple securities to find the biggest movers over a period.
"""

import logging
from datetime import date
from typing import List, Dict

from .models import BasketAnalysisResponse, BasketTickerResult
from .stock_data import fetch_price_history, get_ticker_info

logger = logging.getLogger(__name__)


def analyze_basket(
    tickers: List[str],
    start_date: date,
    end_date: date,
) -> BasketAnalysisResponse:
    """
    Analyze a basket of tickers over a date range to find the biggest movers.
    
    For each ticker, calculates the total percentage change from the first
    trading day to the last trading day in the period, then sorts by
    absolute percentage change to identify the biggest movers.
    """
    results: List[BasketTickerResult] = []
    failed_tickers: List[str] = []
    
    for ticker in tickers:
        ticker = ticker.upper().strip()
        if not ticker:
            continue
            
        try:
            # Fetch price history
            df = fetch_price_history(ticker, start_date, end_date)
            
            if df.empty:
                logger.warning(f"No price data for {ticker}")
                failed_tickers.append(ticker)
                continue
            
            # Get first and last close prices
            start_price = float(df.iloc[0]['Close'])
            end_price = float(df.iloc[-1]['Close'])
            
            # Calculate total percentage change
            total_change_pct = ((end_price - start_price) / start_price) * 100
            direction = "up" if total_change_pct >= 0 else "down"
            
            # Get company info
            info = get_ticker_info(ticker)
            company_name = info.get("company_name")
            
            results.append(
                BasketTickerResult(
                    ticker=ticker,
                    company_name=company_name,
                    start_price=round(start_price, 2),
                    end_price=round(end_price, 2),
                    total_change_pct=round(total_change_pct, 2),
                    direction=direction,
                )
            )
        except Exception as e:
            logger.warning(f"Failed to analyze {ticker}: {e}")
            failed_tickers.append(ticker)
            continue
    
    # Sort by absolute percentage change (biggest movers first)
    results.sort(key=lambda x: abs(x.total_change_pct), reverse=True)
    
    # Log failed tickers
    if failed_tickers:
        logger.info(f"Failed to analyze tickers: {', '.join(failed_tickers)}")
    
    return BasketAnalysisResponse(
        tickers=[t.upper().strip() for t in tickers if t.strip()],
        period_start=start_date,
        period_end=end_date,
        results=results,
        total_analyzed=len(results),
    )
