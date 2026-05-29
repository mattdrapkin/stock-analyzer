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
from .news_fetcher import has_openai_key
from .rate_limit_utils import RateLimitError, is_rate_limit_error, create_rate_limit_error

logger = logging.getLogger(__name__)

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5.4-nano")


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

    # Display batch news cards if available (from web search)
    if analysis.batch_news_cards:
        lines.append("\n" + "─" * 60)
        lines.append("NEWS HIGHLIGHTS (Entire Period)")
        lines.append("─" * 60)
        for card in analysis.batch_news_cards:
            category_label = {
                "company": "COMPANY-SPECIFIC NEWS",
                "competitor": "COMPETITOR / INDUSTRY NEWS",
                "macro": "MACRO / GEOPOLITICAL NEWS",
            }.get(card.category.value, "NEWS")

            lines.append(f"\n>> {category_label}:")
            lines.append(f"   Title: {card.title}")
            lines.append(f"   Summary: {card.summary}")
            if card.date:
                lines.append(f"   Date: {card.date}")
            if card.source_name:
                lines.append(f"   Source: {card.source_name}")
            if card.relevance:
                lines.append(f"   Relevance: {card.relevance}")

    if not analysis.movements:
        lines.append("(No major movements found in this period.)")
    else:
        lines.append("\n" + "─" * 60)
        lines.append("MOVEMENT DETAILS")
        lines.append("─" * 60)

        for mv in analysis.movements:
            lines.append(
                f"\nDATE: {mv.date}  |  {mv.direction.upper()} {mv.change_pct:+.2f}%"
                f"  |  Open: ${mv.open:.2f}  →  Close: ${mv.close:.2f}"
                f"  |  Volume: {mv.volume:,}"
            )

            # Handle individual articles (from mock data)
            if mv.news:
                company_news = [a for a in mv.news if a.category.value == "company"]
                competitor_news = [a for a in mv.news if a.category.value == "competitor"]
                macro_news = [a for a in mv.news if a.category.value == "macro"]

                def _render_articles(articles, label):
                    if not articles:
                        return
                    lines.append(f"  >> {label} ({len(articles)} articles):")
                    for i, art in enumerate(articles, 1):
                        pub = art.published_at.strftime("%Y-%m-%d") if art.published_at else "?"
                        lines.append(
                            f"    {i}. ({pub}) {art.title} — {art.source}"
                        )
                        if art.summary:
                            lines.append(f"       Summary: {art.summary[:300]}")

                _render_articles(company_news, "COMPANY-SPECIFIC NEWS")
                _render_articles(competitor_news, "COMPETITOR / INDUSTRY NEWS")
                _render_articles(macro_news, "MACRO / GEOPOLITICAL NEWS")

    return "\n".join(lines)


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert financial analyst AI assistant.
You have been given structured data about major stock price movements and related news for a specific company.

News is provided either as AI-generated summaries with source citations, or as individual articles.
News is grouped into three distinct categories — COMPANY-SPECIFIC, COMPETITOR / INDUSTRY, and MACRO / GEOPOLITICAL.

Your job is to:
1. Start with a HOLISTIC SUMMARY at the top of your response — a short paragraph explaining what drove the stock's overall swings over the entire time period. Synthesize across all news categories to identify the primary themes and drivers.
2. Then explain WHY the stock moved significantly on specific dates, drawing on the provided news.
3. ALWAYS structure your detailed analysis by news category, in this order:
   - **Company-Specific**: earnings, product launches, lawsuits, management changes — this is the primary driver to examine first.
   - **Competitor / Industry**: peer earnings, sector-wide moves, industry trends — discuss separately only if relevant.
   - **Macro / Geopolitical**: Fed decisions, rates, inflation, trade policy — discuss separately only if relevant.
4. If a category has no relevant news for a given move, omit it rather than speculating.
5. Be intellectually honest — if available news does not clearly explain a move, state this fact without offering follow-up actions or suggesting what the user can do next.
6. Keep responses concise and well-structured. Use clear section headers to separate the three news categories when multiple are present.
7. When citing news, reference sources naturally in your answer. For AI summaries, you can reference the source URLs provided.
8. Never fabricate news events or financial data.
9. IMPORTANT: This is a web application interface, not a conversational chat. Never offer follow-up actions, suggest what the user can do next, or ask if they want additional information. Provide a complete, self-contained response.

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
    logger.debug("=== CONTEXT PROVIDED TO LLM ===\n%s\n=== END CONTEXT ===", context_block)

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
        logger.debug("COMPLETION: %s", completion.choices)
        response_text = completion.choices[0].message.content or ""
        logger.debug("RESPONSE: %s", response_text)
    except OpenAIError as e:
        if is_rate_limit_error(e):
            logger.warning(f"Rate limit hit in chat: {e}")
            rate_limit_err = create_rate_limit_error(e)
            response_text = str(rate_limit_err) + "\n\n" + context_block
        else:
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
