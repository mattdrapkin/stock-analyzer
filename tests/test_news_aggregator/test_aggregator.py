"""Unit tests for the news aggregator module.

Tests cover:
- _fetch_with_fallback: provider priority, fallback on empty results, error handling
- fetch_news_for_movement: category tagging, include_competitors/macro flags, edge cases
- fetch_news_for_period: date range validation, category tagging
- has_any_news_key / get_configured_providers helpers
"""

from datetime import date
from unittest.mock import MagicMock, patch

from app.services.news_aggregator import aggregator

MOVEMENT_DATE = date(2024, 1, 15)
FROM_DATE = date(2024, 1, 13)
TO_DATE = date(2024, 1, 16)

_SAMPLE_ARTICLE = {
    "title": "Apple Earnings Beat",
    "source": "Reuters",
    "url": "https://reuters.com/article",
    "published_at": None,
    "summary": "Apple beat Q1 earnings estimates.",
}


def _make_provider(name="MockProvider", available=True, articles=None):
    source = articles if articles is not None else [_SAMPLE_ARTICLE]
    p = MagicMock()
    p.name = name
    p.is_available.return_value = available
    p.fetch.side_effect = lambda *a, **kw: [dict(art) for art in source]
    return p


# ── _fetch_with_fallback ───────────────────────────────────────────────────────

class TestFetchWithFallback:
    def test_returns_first_provider_results(self):
        p1 = _make_provider("P1", articles=[_SAMPLE_ARTICLE])
        p2 = _make_provider("P2", articles=[_SAMPLE_ARTICLE])
        with patch.object(aggregator, "_PROVIDERS", [p1, p2]):
            result = aggregator._fetch_with_fallback("AAPL stock", FROM_DATE, TO_DATE)
        assert len(result) == 1
        p1.fetch.assert_called_once()
        p2.fetch.assert_not_called()

    def test_falls_back_when_first_returns_empty(self):
        p1 = _make_provider("P1", articles=[])
        p2 = _make_provider("P2", articles=[_SAMPLE_ARTICLE])
        with patch.object(aggregator, "_PROVIDERS", [p1, p2]):
            result = aggregator._fetch_with_fallback("AAPL stock", FROM_DATE, TO_DATE)
        assert len(result) == 1
        p1.fetch.assert_called_once()
        p2.fetch.assert_called_once()

    def test_skips_unavailable_providers(self):
        p1 = _make_provider("P1", available=False)
        p2 = _make_provider("P2", articles=[_SAMPLE_ARTICLE])
        with patch.object(aggregator, "_PROVIDERS", [p1, p2]):
            result = aggregator._fetch_with_fallback("AAPL stock", FROM_DATE, TO_DATE)
        p1.fetch.assert_not_called()
        p2.fetch.assert_called_once()
        assert len(result) == 1

    def test_falls_back_when_provider_raises(self):
        p1 = _make_provider("P1")
        p1.fetch.side_effect = Exception("network error")
        p2 = _make_provider("P2", articles=[_SAMPLE_ARTICLE])
        with patch.object(aggregator, "_PROVIDERS", [p1, p2]):
            result = aggregator._fetch_with_fallback("AAPL stock", FROM_DATE, TO_DATE)
        assert len(result) == 1
        p2.fetch.assert_called_once()

    def test_returns_empty_when_all_providers_fail(self):
        p1 = _make_provider("P1", articles=[])
        p2 = _make_provider("P2", articles=[])
        with patch.object(aggregator, "_PROVIDERS", [p1, p2]):
            result = aggregator._fetch_with_fallback("AAPL stock", FROM_DATE, TO_DATE)
        assert result == []

    def test_returns_empty_on_empty_query(self):
        p1 = _make_provider("P1")
        with patch.object(aggregator, "_PROVIDERS", [p1]):
            result = aggregator._fetch_with_fallback("   ", FROM_DATE, TO_DATE)
        assert result == []
        p1.fetch.assert_not_called()


# ── has_any_news_key / get_configured_providers ────────────────────────────────

class TestHelpers:
    def test_has_any_news_key_true(self):
        p = _make_provider(available=True)
        with patch.object(aggregator, "_PROVIDERS", [p]):
            assert aggregator.has_any_news_key() is True

    def test_has_any_news_key_false(self):
        p = _make_provider(available=False)
        with patch.object(aggregator, "_PROVIDERS", [p]):
            assert aggregator.has_any_news_key() is False

    def test_get_configured_providers_returns_names(self):
        p1 = _make_provider("NewsAPI", available=True)
        p2 = _make_provider("GNews", available=False)
        p3 = _make_provider("Exa AI", available=True)
        with patch.object(aggregator, "_PROVIDERS", [p1, p2, p3]):
            names = aggregator.get_configured_providers()
        assert names == ["NewsAPI", "Exa AI"]


# ── fetch_news_for_movement ────────────────────────────────────────────────────

class TestFetchNewsForMovement:
    def test_company_category_assigned(self):
        p = _make_provider(articles=[dict(_SAMPLE_ARTICLE)])
        with patch.object(aggregator, "_PROVIDERS", [p]):
            articles = aggregator.fetch_news_for_movement(
                movement_date=MOVEMENT_DATE,
                company_name="Apple",
                ticker="AAPL",
            )
        assert all(a["category"] == "company" for a in articles)
        assert len(articles) == 1

    def test_includes_competitor_articles(self):
        p = _make_provider(articles=[dict(_SAMPLE_ARTICLE)])
        with patch.object(aggregator, "_PROVIDERS", [p]):
            articles = aggregator.fetch_news_for_movement(
                movement_date=MOVEMENT_DATE,
                company_name="Apple",
                ticker="AAPL",
                sector="Technology",
                include_competitors=True,
            )
        categories = [a["category"] for a in articles]
        assert "company" in categories
        assert "competitor" in categories

    def test_includes_macro_articles(self):
        p = _make_provider(articles=[dict(_SAMPLE_ARTICLE)])
        with patch.object(aggregator, "_PROVIDERS", [p]):
            articles = aggregator.fetch_news_for_movement(
                movement_date=MOVEMENT_DATE,
                company_name="Apple",
                ticker="AAPL",
                include_macro=True,
            )
        categories = [a["category"] for a in articles]
        assert "company" in categories
        assert "macro" in categories

    def test_returns_empty_when_missing_required_args(self):
        p = _make_provider()
        with patch.object(aggregator, "_PROVIDERS", [p]):
            assert aggregator.fetch_news_for_movement(MOVEMENT_DATE, "", "AAPL") == []
            assert aggregator.fetch_news_for_movement(MOVEMENT_DATE, "Apple", "") == []

    def test_returns_empty_on_negative_days(self):
        p = _make_provider()
        with patch.object(aggregator, "_PROVIDERS", [p]):
            result = aggregator.fetch_news_for_movement(
                MOVEMENT_DATE, "Apple", "AAPL", days_before=-1
            )
        assert result == []


# ── fetch_news_for_period ──────────────────────────────────────────────────────

class TestFetchNewsForPeriod:
    def test_company_category_assigned(self):
        p = _make_provider(articles=[dict(_SAMPLE_ARTICLE)])
        with patch.object(aggregator, "_PROVIDERS", [p]):
            articles = aggregator.fetch_news_for_period(
                from_date=FROM_DATE,
                to_date=TO_DATE,
                company_name="Apple",
                ticker="AAPL",
            )
        assert all(a["category"] == "company" for a in articles)
        assert len(articles) == 1

    def test_returns_empty_on_inverted_date_range(self):
        p = _make_provider()
        with patch.object(aggregator, "_PROVIDERS", [p]):
            result = aggregator.fetch_news_for_period(
                from_date=TO_DATE,
                to_date=FROM_DATE,
                company_name="Apple",
                ticker="AAPL",
            )
        assert result == []
        p.fetch.assert_not_called()

    def test_returns_empty_when_missing_required_args(self):
        p = _make_provider()
        with patch.object(aggregator, "_PROVIDERS", [p]):
            assert aggregator.fetch_news_for_period(FROM_DATE, TO_DATE, "", "AAPL") == []
            assert aggregator.fetch_news_for_period(FROM_DATE, TO_DATE, "Apple", "") == []

    def test_includes_all_categories(self):
        p = _make_provider(articles=[dict(_SAMPLE_ARTICLE)])
        with patch.object(aggregator, "_PROVIDERS", [p]):
            articles = aggregator.fetch_news_for_period(
                from_date=FROM_DATE,
                to_date=TO_DATE,
                company_name="Apple",
                ticker="AAPL",
                sector="Technology",
                include_competitors=True,
                include_macro=True,
            )
        categories = {a["category"] for a in articles}
        assert categories == {"company", "competitor", "macro"}
