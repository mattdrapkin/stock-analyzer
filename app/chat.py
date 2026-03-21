"""
Chat module: builds LLM context from stock + news data and handles
multi-turn conversations via the OpenAI Chat Completions API.

If OPENAI_API_KEY is not set the module returns a structured text summary
instead of an LLM response so the endpoint remains usable without a key.
"""

import os
import logging
from datetime import date, timedelta
from typing import List, Optional

from openai import OpenAI, OpenAIError

from .models import ChatMessage, ChatResponse, TickerAnalysis
from .analyzer import build_analysis
from .news_fetcher import fetch_news_for_period, has_serpapi_key

logger = logging.getLogger(__name__)

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5.4-nano")


def has_openai_key() -> bool:
    return bool(OPENAI_API_KEY)


# ── Context builder ───────────────────────────────────────────────────────────

def _format_analysis_as_context(analysis: TickerAnalysis) -> str:
    """Serialise a TickerAnalysis into a compact, LLM-readable string."""
    lines = [
        f"TICKER: {analysis.ticker}",
        f"COMPANY: {analysis.company_name}",
        f"SECTOR / INDUSTRY: {analysis.sector} / {analysis.industry}",
        f"ANALYSIS PERIOD: {analysis.period_start} → {analysis.period_end}",
        f"MOVEMENT THRESHOLD: ≥ {analysis.min_movement_pct}% intra-day",
        f"MAJOR MOVEMENTS FOUND: {analysis.total_movements} "
        f"({analysis.up_movements} up, {analysis.down_movements} down)",
        "",
        "─" * 60,
        "MAJOR PRICE MOVEMENTS WITH RELATED NEWS",
        "─" * 60,
    ]

    if not analysis.movements:
        lines.append("(No major movements found in this period.)")
    else:
        for mv in analysis.movements:
            lines.append(
                f"\nDATE: {mv.date}  |  {mv.direction.upper()} {mv.change_pct:+.2f}%"
                f"  |  Open: ${mv.open:.2f}  →  Close: ${mv.close:.2f}"
                f"  |  Volume: {mv.volume:,}"
            )
            if mv.news:
                lines.append(f"  Related news ({len(mv.news)} articles):")
                for i, art in enumerate(mv.news, 1):
                    pub = art.published_at.strftime("%Y-%m-%d") if art.published_at else "?"
                    lines.append(
                        f"    {i}. [{art.category.upper()}] ({pub}) {art.title}"
                        f" — {art.source}"
                    )
                    if art.summary:
                        lines.append(f"       Summary: {art.summary[:300]}")
            else:
                lines.append("  (No news articles found for this movement.)")

    return "\n".join(lines)


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert financial analyst AI assistant.
You have been given structured data about major stock price movements and related news articles for a specific company.

Your job is to:
1. Explain WHY the stock moved significantly on specific dates, drawing on the provided news.
2. Distinguish between company-specific drivers (earnings, product launches, lawsuits), industry/competitor moves, and macro factors (Fed decisions, geopolitics, inflation).
3. Be intellectually honest — if the available news does not clearly explain a move, say so and suggest what *type* of event could be responsible.
4. Keep responses concise and well-structured. Use bullet points when listing multiple factors.
5. When citing news, reference the article title and date naturally in your answer.
6. Never fabricate news events or financial data.

The structured data provided below is your sole source of truth. Do not use outside knowledge about specific events unless asked explicitly.
"""


def _no_llm_summary(analysis: TickerAnalysis, message: str) -> str:
    """Fallback response when OpenAI key is not configured."""
    ctx = _format_analysis_as_context(analysis)
    return (
        "⚠️  OpenAI API key not configured — returning structured summary instead of AI analysis.\n\n"
        f"Your question: {message}\n\n"
        f"{ctx}\n\n"
        "To enable AI-powered chat analysis, set OPENAI_API_KEY in your .env file."
    )


# ── Public interface ──────────────────────────────────────────────────────────

def chat_with_ticker(
    ticker: str,
    message: str,
    history: List[ChatMessage],
    context_days: int = 60,
    min_movement_pct: float = 2.0,
    include_competitors: bool = False,
    include_macro: bool = False,
) -> ChatResponse:
    """
    Build context from stock + news data then call the OpenAI Chat API.

    History is forwarded verbatim so multi-turn conversations are supported.
    """
    ticker = ticker.upper()
    end_date = date.today()
    start_date = end_date - timedelta(days=context_days)

    # Build analysis (may be served from cache)
    analysis = build_analysis(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        min_movement_pct=min_movement_pct,
        include_competitors=include_competitors,
        include_macro=include_macro,
        max_articles_per_category=5,
    )

    if not has_openai_key():
        return ChatResponse(
            response=_no_llm_summary(analysis, message),
            ticker=ticker,
            movements_analyzed=analysis.total_movements,
            context_used=False,
        )

    context_block = _format_analysis_as_context(analysis)

    # Build messages list for the API call
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "system",
            "content": f"Here is the stock and news data you have access to:\n\n{context_block}",
        },
    ]
    # Append conversation history
    for turn in history:
        messages.append({"role": turn.role, "content": turn.content})
    # Append the new user message
    messages.append({"role": "user", "content": message})
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.3,
        )
        print("COMPLETION:", completion.choices)
        response_text = completion.choices[0].message.content or ""
        print("RESPONSE:", response_text)
    except OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        response_text = (
            f"OpenAI API error: {e}\n\n"
            "Falling back to raw data:\n\n"
            + context_block
        )

    return ChatResponse(
        response=response_text,
        ticker=ticker,
        movements_analyzed=analysis.total_movements,
        context_used=True,
    )
