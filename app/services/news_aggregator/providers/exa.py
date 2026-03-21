"""Exa AI (exa.ai) news search provider."""

import os
import logging
from datetime import date, datetime
from typing import List, Dict
from urllib.parse import urlparse

import httpx

from ..base import NewsProvider, parse_datetime

logger = logging.getLogger(__name__)

_SEARCH_URL: str = "https://api.exa.ai/search"


class ExaProvider(NewsProvider):
    """Provider backed by the Exa AI search API with the 'news' category filter.

    Requires env var: EXA_API_KEY
    Supports native date-range filtering and returns article highlights.
    """

    def __init__(self) -> None:
        self._api_key: str = os.getenv("EXA_API_KEY", "")

    @property
    def name(self) -> str:
        return "Exa AI"

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
            logger.debug("Exa AI API key not configured")
            return []

        if not query.strip():
            logger.warning("Empty query provided to Exa AI")
            return []

        max_results = max(1, min(max_results, 100))

        # Exa expects ISO 8601 with milliseconds and Z suffix
        from_str = datetime.combine(from_date, datetime.min.time()).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        to_str = datetime.combine(
            to_date, datetime.max.time().replace(microsecond=0)
        ).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        payload = {
            "query": query,
            "type": "keyword",
            "category": "news",
            "numResults": max_results,
            "startPublishedDate": from_str,
            "endPublishedDate": to_str,
            "contents": {
                "highlights": {
                    "numSentences": 3,
                    "highlightsPerUrl": 1,
                },
            },
        }

        headers = {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(_SEARCH_URL, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

            if not isinstance(data, dict) or "results" not in data:
                logger.error(f"Exa AI returned unexpected response: {str(data)[:200]}")
                return []

            results = data.get("results", [])
            logger.debug(f"Exa AI returned {len(results)} raw results")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("Exa AI rate limit exceeded")
            elif e.response.status_code == 401:
                logger.error("Exa AI invalid API key — check EXA_API_KEY")
            else:
                logger.warning(f"Exa AI HTTP {e.response.status_code}: {e.response.text[:200]}")
            return []
        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.error(f"Exa AI request error: {e}")
            return []
        except Exception as e:
            logger.exception(f"Exa AI unexpected error: {e}")
            return []

        articles = []
        for i, result in enumerate(results):
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

                published_at = parse_datetime(result.get("publishedDate"))

                highlights = result.get("highlights", [])
                summary = " ".join(highlights[:3]) if isinstance(highlights, list) else ""
                summary = summary[:600].strip()

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
                logger.warning(f"Error processing Exa AI result {i}: {e}")
                continue

        return articles
