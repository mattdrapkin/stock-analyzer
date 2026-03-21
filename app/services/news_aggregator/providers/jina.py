"""Jina AI (jina.ai) web search provider.

Jina's search endpoint does not support native date-range filtering, so the
date window is injected into the query string as context.  This makes it a
reasonable last-resort fallback when other providers have been exhausted.
"""

import os
import logging
from datetime import date
from typing import List, Dict
from urllib.parse import urlparse

import httpx

from ..base import NewsProvider, parse_datetime

logger = logging.getLogger(__name__)

_SEARCH_URL: str = "https://s.jina.ai/"


class JinaProvider(NewsProvider):
    """Provider backed by Jina AI's web search endpoint.

    Requires env var: JINA_API_KEY
    Note: no native date filtering — date range is appended to the query.
    """

    def __init__(self) -> None:
        self._api_key: str = os.getenv("JINA_API_KEY", "")

    @property
    def name(self) -> str:
        return "Jina AI"

    def is_available(self) -> bool:
        return bool(self._api_key)

    def fetch(
        self,
        query: str,
        from_date: date,
        to_date: date,
        max_results: int = 10,
    ) -> List[Dict]:
        if not self.is_available():
            logger.debug("Jina AI API key not configured")
            return []

        if not query.strip():
            logger.warning("Empty query provided to Jina AI")
            return []

        # Inject date range as context since Jina has no native date filter
        date_context = (
            f"news between {from_date.strftime('%B %d %Y')} "
            f"and {to_date.strftime('%B %d %Y')}"
        )
        full_query = f"{query} {date_context}"

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
            "X-Retain-Images": "none",
        }

        params = {"q": full_query}

        try:
            with httpx.Client(timeout=15) as client:
                resp = client.get(_SEARCH_URL, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()

            if not isinstance(data, dict):
                logger.error("Jina AI returned non-dict response")
                return []

            results = data.get("data", [])
            if not isinstance(results, list):
                logger.error("Jina AI 'data' field is not a list")
                return []

            logger.debug(f"Jina AI returned {len(results)} raw results")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("Jina AI rate limit exceeded")
            elif e.response.status_code == 401:
                logger.error("Jina AI invalid API key — check JINA_API_KEY")
            else:
                logger.warning(f"Jina AI HTTP {e.response.status_code}: {e.response.text[:200]}")
            return []
        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.error(f"Jina AI request error: {e}")
            return []
        except Exception as e:
            logger.exception(f"Jina AI unexpected error: {e}")
            return []

        articles = []
        for i, result in enumerate(results[:max_results]):
            try:
                title = result.get("title", "") or ""
                if not title:
                    continue

                url = result.get("url", "") or None

                source = "Unknown"
                if url:
                    try:
                        source = urlparse(url).netloc.lstrip("www.") or "Unknown"
                    except Exception:
                        pass

                published_at = parse_datetime(result.get("publishedTime"))

                summary = result.get("description", "") or result.get("content", "") or ""
                if isinstance(summary, str):
                    summary = summary[:600].strip()
                else:
                    summary = ""

                articles.append(
                    {
                        "title": title.strip(),
                        "source": source,
                        "url": url,
                        "published_at": published_at,
                        "summary": summary,
                    }
                )
            except Exception as e:
                logger.warning(f"Error processing Jina AI result {i}: {e}")
                continue

        return articles
