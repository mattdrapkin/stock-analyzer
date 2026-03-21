"""NewsAPI (newsapi.org) provider."""

import os
import logging
from datetime import date
from typing import List, Dict

import httpx

from ..base import NewsProvider, parse_datetime

logger = logging.getLogger(__name__)

_BASE_URL: str = "https://newsapi.org/v2/everything"


class NewsAPIProvider(NewsProvider):
    """Provider backed by NewsAPI /everything endpoint.

    Requires env var: NEWS_API_KEY
    Free tier: 100 req/day, current month only.
    """

    def __init__(self) -> None:
        self._api_key: str = os.getenv("NEWS_API_KEY", "")

    @property
    def name(self) -> str:
        return "NewsAPI"

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
            logger.debug("NewsAPI key not configured")
            return []

        if not query.strip():
            logger.warning("Empty query provided to NewsAPI")
            return []

        if from_date > to_date:
            logger.error(f"Invalid date range: {from_date} > {to_date}")
            return []

        max_results = max(1, min(max_results, 100))

        params = {
            "q": query,
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "language": "en",
            "sortBy": "relevancy",
            "pageSize": max_results,
            "apiKey": self._api_key,
        }

        try:
            with httpx.Client(timeout=12) as client:
                resp = client.get(_BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            if not isinstance(data, dict) or "articles" not in data:
                logger.error("NewsAPI returned unexpected response structure")
                return []

            articles_data = data.get("articles", [])
            if not isinstance(articles_data, list):
                logger.error("NewsAPI 'articles' field is not a list")
                return []

            logger.debug(f"NewsAPI returned {len(articles_data)} raw articles")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("NewsAPI rate limit exceeded")
            elif e.response.status_code == 401:
                logger.error("NewsAPI invalid API key — check NEWS_API_KEY")
            elif e.response.status_code == 400:
                logger.warning(f"NewsAPI bad request: {e.response.text[:200]}")
            else:
                logger.warning(f"NewsAPI HTTP {e.response.status_code}: {e.response.text[:200]}")
            return []
        except (httpx.TimeoutException, httpx.RequestError) as e:
            logger.error(f"NewsAPI request error: {e}")
            return []
        except Exception as e:
            logger.exception(f"NewsAPI unexpected error: {e}")
            return []

        articles = []
        for i, a in enumerate(articles_data):
            try:
                title = a.get("title", "") or ""
                if title in ("[Removed]", ""):
                    continue

                source_obj = a.get("source", {})
                source_name = (
                    source_obj.get("name", "Unknown")
                    if isinstance(source_obj, dict)
                    else "Unknown"
                ) or "Unknown"

                url = a.get("url", "")
                if url and not isinstance(url, str):
                    url = ""

                summary = a.get("description", "") or a.get("content", "") or ""
                if isinstance(summary, str):
                    summary = summary[:600].strip()
                else:
                    summary = ""

                articles.append(
                    {
                        "title": title.strip(),
                        "source": source_name.strip(),
                        "url": url or None,
                        "published_at": parse_datetime(a.get("publishedAt")),
                        "summary": summary,
                    }
                )
            except Exception as e:
                logger.warning(f"Error processing NewsAPI article {i}: {e}")
                continue

        return articles
