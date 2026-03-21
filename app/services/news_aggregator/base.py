"""Abstract base class and shared utilities for news provider implementations."""

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import List, Dict, Optional

import logging

logger = logging.getLogger(__name__)


def parse_datetime(s: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 datetime string, returning None on failure."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


class NewsProvider(ABC):
    """Abstract base class for all news provider implementations.

    Each provider must implement:
        name          — human-readable provider name
        is_available  — returns True when the required credentials are present
        fetch         — fetches and returns normalised article dicts
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g. 'NewsAPI', 'GNews')."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider has the required credentials configured."""
        ...

    @abstractmethod
    def fetch(
        self,
        query: str,
        from_date: date,
        to_date: date,
        max_results: int = 10,
    ) -> List[Dict]:
        """Fetch news articles matching *query* within [from_date, to_date].

        Returns a list of normalised article dicts, each with keys:
            title        : str
            source       : str
            url          : str | None
            published_at : datetime | None
            summary      : str
        """
        ...
