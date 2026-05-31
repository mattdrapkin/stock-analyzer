"""
Shared utilities for parsing and normalising news article data from OpenAI responses.

Functions here are used by both news_fetcher and basket_analyzer to avoid
duplicating article validation, date normalisation, and category conversion logic.
"""

import logging
import re
from datetime import datetime
from typing import Dict, Optional

from .models import NewsCard, NewsCategory

logger = logging.getLogger(__name__)


# ── Category helpers ──────────────────────────────────────────────────────────

def parse_news_category(cat_str: str) -> NewsCategory:
    """Convert a category string to a NewsCategory enum, defaulting to COMPANY."""
    try:
        return NewsCategory(cat_str)
    except ValueError:
        return NewsCategory.COMPANY


# ── Date / URL normalisation ──────────────────────────────────────────────────

def normalize_date(date_str: Optional[str]) -> Optional[str]:
    """
    Normalise a date string to YYYY-MM-DD format.

    Tries ISO format first, then a set of common alternatives.
    Returns None if the string cannot be parsed.
    """
    if not date_str:
        return None

    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date().isoformat()
    except ValueError:
        pass

    for fmt in ("%B %d, %Y", "%d %B %Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str, fmt).date().isoformat()
        except ValueError:
            continue

    logger.debug("Could not parse date '%s', returning None", date_str)
    return None


def validate_url(url: Optional[str]) -> Optional[str]:
    """Return *url* unchanged if it starts with 'http', otherwise None."""
    if url and url.startswith("http"):
        return url
    return None


# ── Markdown helpers ──────────────────────────────────────────────────────────

def strip_markdown_fences(text: str) -> str:
    """Remove leading/trailing markdown code fences (```...```) from *text*."""
    if text.startswith("```"):
        text = re.sub(r'^```(?:json)?\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    return text.strip()


def strip_markdown_formatting(text: str) -> str:
    """Remove bold (**text**, __text__) and italic (*text*, _text_) markdown."""
    text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text)
    text = re.sub(r'(\*|_)(?!\1)(.*?)\1', r'\2', text)
    return text


# ── Article dict validation ───────────────────────────────────────────────────

def parse_article_dict(article: object) -> Optional[Dict]:
    """
    Validate and normalise a raw article dict from an OpenAI response.

    Performs:
      - Required field check (title, summary must be non-empty)
      - Category normalisation (must be company / competitor / macro)
      - URL validation (must start with http)
      - Date normalisation to YYYY-MM-DD

    Returns a normalised dict on success, or None if the article is invalid.
    """
    if not isinstance(article, dict):
        return None

    title = (article.get("title") or "").strip()
    summary = (article.get("summary") or "").strip()
    if not title or not summary:
        logger.debug("Skipping article with missing title or summary: %s", article)
        return None

    cat = article.get("category", "company")
    if cat not in ("company", "competitor", "macro"):
        cat = "company"

    return {
        "title": title,
        "summary": summary,
        "date": normalize_date(article.get("date")),
        "source_name": (article.get("source_name") or "").strip() or None,
        "url": validate_url(article.get("url") or None),
        "category": cat,
        "relevance": (article.get("relevance") or "").strip() or None,
    }


# ── Model conversion ──────────────────────────────────────────────────────────

def news_card_from_dict(raw: Dict) -> NewsCard:
    """Convert a raw (already-validated) article dict to a NewsCard model."""
    return NewsCard(
        title=raw.get("title", ""),
        summary=raw.get("summary", ""),
        date=raw.get("date") or None,
        source_name=raw.get("source_name") or None,
        url=raw.get("url") or None,
        category=parse_news_category(raw.get("category", "company")),
        relevance=raw.get("relevance") or None,
    )
