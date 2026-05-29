"""
Fun Facts module: generates interesting facts about stocks or baskets using OpenAI.
"""

import os
import logging
from typing import List, Optional

from openai import OpenAI, OpenAIError

from .models import FunFactsRequest, FunFactsResponse
from .news_fetcher import has_openai_key
from .rate_limit_utils import is_rate_limit_error, format_rate_limit_error

logger = logging.getLogger(__name__)

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


FUN_FACTS_SYSTEM_PROMPT = """You are an expert financial analyst and engaging storyteller.
Your job is to generate 5-8 interesting, fun facts about the provided stock ticker(s) or basket of stocks.

Guidelines:
1. Facts should be relevant to the company/companies, their industry, or their stock performance
2. Mix of historical facts, business trivia, market performance insights, and company culture
3. Keep each fact concise (1-2 sentences max)
4. Make facts engaging and surprising when possible
5. Avoid overly technical jargon - keep it accessible
6. Do not include financial advice or investment recommendations
7. Return the facts as a numbered list, one per line

Example format:
1. Apple was founded in 1976 in a garage by Steve Jobs and Steve Wozniak
2. The company's market cap exceeded $3 trillion in 2022, making it the most valuable company in history
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
        # Fallback to generic facts if no API key
        return FunFactsResponse(
            facts=[
                "Stock market analysis can reveal fascinating patterns in company performance",
                "Many of today's tech giants started in small garages or dorm rooms",
                "Market capitalization reflects investor confidence in a company's future",
                "Historical stock data can tell stories about innovation and economic shifts",
                "The NYSE can process billions of shares in a single trading day",
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

    user_prompt = f"Generate 5-8 fun, interesting facts about {subject}. Focus on company history, market performance, industry trivia, and surprising business insights."
    logger.info(f"User prompt: {user_prompt}")

    try:
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
            return FunFactsResponse(
                facts=[
                    "Stock market analysis can reveal fascinating patterns in company performance",
                    "Many of today's tech giants started in small garages or dorm rooms",
                ]
            )
        else:
            logger.error(f"OpenAI API error in fun facts: {e}")
            return FunFactsResponse(
                facts=[
                    "Stock market analysis can reveal fascinating patterns in company performance",
                    "Many of today's tech giants started in small garages or dorm rooms",
                ]
            )
