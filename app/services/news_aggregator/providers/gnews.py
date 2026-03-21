"""GNews (gnews.io) provider."""

import os
import logging
from datetime import date, datetime
from typing import List, Dict

import httpx

from ..base import NewsProvider, parse_datetime

logger = logging.getLogger(__name__)

_BASE_URL: str = "https://gnews.io/api/v4/search"


class GNewsProvider(NewsProvider):
    """Provider backed by the GNews /search endpoint.

    Requires env var: GNEWS_API_KEY
    Free tier: 100 req/day, max 10 articles/request.
    """

    def __init__(self) -> None:
        self._api_key: str = os.getenv("GNEWS_API_KEY", "")

    @property
    def name(self) -> str:
        return "GNews"

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
            logger.debug("GNews API key not configured")
            return []

        if not query.strip():
            logger.warning("Empty query provided to GNews")
            return []

        # GNews free tier caps at 10 results per request
        max_results = max(1, min(max_results, 10))

        # GNews expects ISO 8601 datetime with timezone offset
        from_str = datetime.combine(from_date, datetime.min.time()).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        to_str = datetime.combine(to_date, datetime.max.time().replace(microsecond=0)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        params = {
            "q": query,
            "lang": "en",
            "from": from_str,
            "to": to_str,
            "max": max_results,
            "sortby": "relevance",
            "token": self._api_key,
        }

        try:
            with httpx.Client(timeout=12) as client:
                resp = client.get(_BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            if not isinstance(data, dict) or "articles" not in data:
                logger.error(f"GNews returned unexpected response: {str(data)[:200]}")
                return []

            articles_data = data.get("articles", [])
            logger.debug(f"GNews returned {len(articles_data)} raw articles")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("GNews rate limit exceeded")
            elif e.response.status_code == 403:
                logger.error("GNews invalid API key or plan limit — check GNEWS_API_KEY")
            else:
                logger.warning(f"GNews HTTP {e.response.status_code}: {e.response.text[:200]}")
            return []
        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.error(f"GNews request error: {e}")
            return []
        except Exception as e:
            logger.exception(f"GNews unexpected error: {e}")
            return []

        articles = []
        for i, a in enumerate(articles_data):
            try:
                title = a.get("title", "") or ""
                if not title:
                    continue

                source_obj = a.get("source", {})
                source_name = (
                    source_obj.get("name", "Unknown")
                    if isinstance(source_obj, dict)
                    else "Unknown"
                ) or "Unknown"

                url = a.get("url", "") or None

                summary = a.get("description", "") or a.get("content", "") or ""
                if isinstance(summary, str):
                    summary = summary[:600].strip()
                else:
                    summary = ""

                articles.append(
                    {
                        "title": title.strip(),
                        "source": source_name.strip(),
                        "url": url,
                        "published_at": parse_datetime(a.get("publishedAt")),
                        "summary": summary,
                    }
                )
            except Exception as e:
                logger.warning(f"Error processing GNews article {i}: {e}")
                continue

        return articles
