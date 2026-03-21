"""Query builders for the three news categories (company, competitor, macro)."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def company_query(company_name: str, ticker: str) -> str:
    """Narrow query targeting the specific company."""
    if not company_name or not ticker:
        logger.warning("Empty company_name or ticker provided for company query")
        return ""

    safe_name = company_name.replace('"', "").strip()
    if not safe_name:
        logger.warning("Company name becomes empty after sanitization")
        return f'"{ticker.upper()}" stock'

    return f'"{safe_name}" OR "{ticker.upper()}" stock'


def competitor_query(sector: Optional[str], industry: Optional[str]) -> str:
    """Broad query for sector/industry news."""
    parts = []

    if industry:
        industry_clean = industry.strip().replace('"', "")
        if industry_clean:
            parts.append(f'"{industry_clean}"')
        else:
            logger.warning("Industry becomes empty after sanitization")

    if sector:
        sector_clean = sector.strip().replace('"', "")
        if sector_clean:
            parts.append(f'"{sector_clean}"')
        else:
            logger.warning("Sector becomes empty after sanitization")

    base = " OR ".join(parts) if parts else "stock market"
    return f"({base}) AND (earnings OR merger OR acquisition OR results OR outlook)"


def macro_query() -> str:
    """Query for macro / political events that move markets."""
    return (
        "Federal Reserve OR interest rate OR inflation OR GDP OR recession "
        "OR trade war OR tariff OR geopolitical OR central bank OR rate hike "
        "OR rate cut OR jobs report OR unemployment"
    )
