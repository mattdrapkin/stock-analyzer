"""
Fun Facts module: generates interesting facts about stocks or baskets using OpenAI.
"""

import os
import logging
from typing import List, Optional

from openai import OpenAI, OpenAIError

from .models import FunFactsRequest, FunFactsResponse
from .news_fetcher import has_openai_key
from .rate_limit_utils import is_rate_limit_error, create_rate_limit_error, RateLimitError, get_rate_limiter

logger = logging.getLogger(__name__)

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


FUN_FACTS_SYSTEM_PROMPT = """You are a sophisticated institutional investor with deep knowledge of public and private markets, having worked at top-tier endowments, hedge funds, and venture capital firms.
Your job is to generate 5-8 genuinely interesting, non-obvious insights about the provided stock ticker(s) or basket of stocks.

Guidelines:
1. Focus on sophisticated market insights: capital structure anomalies, ownership patterns, competitive moats, regulatory arbitrage, or unique business model economics
2. Include insights about private market parallels, venture ecosystem connections, or institutional ownership patterns
3. Reference historical market anomalies, sector rotation patterns, or macroeconomic linkages that sophisticated investors would find compelling
4. Highlight non-obvious competitive dynamics, supply chain vulnerabilities, or optionality in the business model
5. Touch on governance structures, founder ownership, or capital allocation strategies that drive long-term value
6. Include insights about the company's role in broader market structure, index inclusion effects, or ETF flow impacts
7. Reference interesting comparisons across public/private market valuations or similar companies in different geographies
8. Keep each fact concise (1-2 sentences max) but dense with insight
9. Avoid generic trivia, basic company history, or surface-level facts
10. Do not include financial advice or investment recommendations
11. Return the facts as a numbered list, one per line

Example format:
1. NVIDIA's GPU dominance creates a structural moat in AI training that's difficult to displace due to CUDA ecosystem lock-in
2. The company's high float percentage makes it a favorite for passive index funds, creating persistent buying pressure
3. etc.
"""


def generate_fun_facts(request: FunFactsRequest) -> FunFactsResponse:
    """
    Generate fun facts about a ticker or basket using OpenAI.
    """
    logger.info(f"Generating fun facts for request: {request}")
    logger.info(f"OpenAI API key configured: {bool(OPENAI_API_KEY)}")
    logger.info(f"Using model: {OPENAI_MODEL}")

    if not has_openai_key():
        logger.warning("No OpenAI API key configured, using fallback facts")
        # Fallback to sophisticated facts if no API key
        return FunFactsResponse(
            facts=[
                "Index fund flows can create persistent price pressure on high-float stocks, independent of fundamentals",
                "Private market valuations often lead public market comps by 6-18 months due to information asymmetry",
                "Companies with dual-class share structures often trade at governance discounts despite founder alignment benefits",
                "ETF inclusion effects can add 5-15bps of permanent beta to large-cap stocks through passive rebalancing",
                "Supply chain concentration in single geographies creates hidden tail risks not captured in financial statements",
                "Revenue quality metrics like cash conversion often signal future earnings revisions before they hit consensus estimates",
            ]
        )

    # Build the prompt based on input type
    if request.ticker:
        subject = f"the stock ticker {request.ticker.upper()} and its company"
    elif request.basket:
        basket_str = ", ".join([t.upper() for t in request.basket])
        subject = f"the basket of stocks: {basket_str}"
    else:
        # Default fallback
        subject = "the stock market and investing"

    user_prompt = f"Generate 5-8 sophisticated, non-obvious insights about {subject} that would interest a top-tier institutional investor. Focus on structural advantages, market dynamics, ownership patterns, competitive moats, or unique aspects of the business model that aren't widely appreciated."
    logger.info(f"User prompt: {user_prompt}")

    try:
        # Apply rate limiting before making the API call
        rate_limiter = get_rate_limiter()
        rate_limiter.wait_if_needed()
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": FUN_FACTS_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,  # Slightly higher temperature for more variety
        )
        
        response_text = completion.choices[0].message.content or ""
        logger.info(f"Fun facts generated successfully: {response_text[:200]}...")

        # Parse the numbered list into individual facts
        facts = []
        for line in response_text.strip().split('\n'):
            line = line.strip()
            if line:
                # Remove numbering (e.g., "1. " or "1) ")
                if line[0].isdigit():
                    parts = line.split('.', 1) if '.' in line else line.split(')', 1)
                    if len(parts) > 1:
                        line = parts[1].strip()
                facts.append(line)

        # Ensure we have at least some facts
        if not facts:
            facts = [response_text]

        logger.info(f"Parsed {len(facts)} facts")
        return FunFactsResponse(facts=facts[:8])  # Limit to 8 facts max

    except OpenAIError as e:
        if is_rate_limit_error(e):
            logger.warning(f"Rate limit hit in fun facts: {e}")
            raise create_rate_limit_error(e) from e
        else:
            logger.error(f"OpenAI API error in fun facts: {e}")
            raise
