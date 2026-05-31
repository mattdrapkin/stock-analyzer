"""
Centralized OpenAI API configuration and call utilities.

This module owns all OpenAI env-var configuration and provides thin
wrappers around the two API surfaces used by this application:

  - Responses API (web_search tool)  → call_responses_api
  - Chat Completions API             → call_chat_completions

Both wrappers apply the global rate-limiter and exponential-backoff
retry so call sites are free of that boilerplate.
"""

import logging
import os
from typing import List, Optional, Tuple

from openai import OpenAI, OpenAIError

from .rate_limit_utils import (
    RateLimitError,
    create_rate_limit_error,
    get_rate_limiter,
    is_rate_limit_error,
    retry_with_exponential_backoff,
)

logger = logging.getLogger(__name__)

# ── Environment configuration ─────────────────────────────────────────────────

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_SEARCH_MODEL: str = os.getenv("OPENAI_SEARCH_MODEL", "gpt-5.5")
OPENAI_SEARCH_CONTEXT_SIZE: str = os.getenv("OPENAI_SEARCH_CONTEXT_SIZE", "medium")


# ── Client factory ────────────────────────────────────────────────────────────

def has_openai_key() -> bool:
    """Return True if the OpenAI API key is configured."""
    return bool(OPENAI_API_KEY)


def get_openai_client() -> OpenAI:
    """Return a configured OpenAI client instance."""
    return OpenAI(api_key=OPENAI_API_KEY)


# ── Responses API output parsing ──────────────────────────────────────────────

def extract_response_content(response) -> Tuple[str, List[str], List[str]]:
    """
    Parse a Responses API response object.

    The output list contains two item types (per API docs):
      - web_search_call  → exposes the search query via action.query
      - message          → contains assistant text and url_citation annotations

    Returns:
        Tuple of (text, source_urls, search_queries)
    """
    text = ""
    source_urls: List[str] = []
    search_queries: List[str] = []

    if not hasattr(response, "output") or not response.output:
        return text, source_urls, search_queries

    for item in response.output:
        item_type = getattr(item, "type", None)

        if item_type == "web_search_call":
            action = getattr(item, "action", None)
            if action:
                query = getattr(action, "query", None)
                if query:
                    search_queries.append(query)

        elif item_type == "message":
            content_list = getattr(item, "content", None) or []
            for block in content_list:
                if getattr(block, "type", None) == "output_text":
                    text = getattr(block, "text", "") or ""
                    for ann in (getattr(block, "annotations", None) or []):
                        if getattr(ann, "type", None) == "url_citation":
                            url = getattr(ann, "url", None)
                            if url:
                                source_urls.append(url)

    source_urls = list(dict.fromkeys(source_urls))      # deduplicate, preserve order
    search_queries = list(dict.fromkeys(search_queries))
    return text, source_urls, search_queries


# ── High-level API call wrappers ──────────────────────────────────────────────

def call_responses_api(
    instructions: str,
    prompt: str,
    model: Optional[str] = None,
    context_size: Optional[str] = None,
) -> Tuple[str, List[str], List[str]]:
    """
    Call the OpenAI Responses API with the web_search tool.

    Applies the global rate-limiter and exponential-backoff retry automatically.

    Args:
        instructions: System-level instructions for the model.
        prompt: The user-facing input / search request.
        model: Override the default OPENAI_SEARCH_MODEL.
        context_size: Override the default OPENAI_SEARCH_CONTEXT_SIZE.

    Returns:
        Tuple of (text, source_urls, search_queries)

    Raises:
        RateLimitError: if the rate limit is exceeded after all retries.
        OpenAIError: for any other API-level error.
    """
    _model = model or OPENAI_SEARCH_MODEL
    _context_size = context_size or OPENAI_SEARCH_CONTEXT_SIZE
    client = get_openai_client()
    rate_limiter = get_rate_limiter()

    def make_api_call():
        return client.responses.create(
            model=_model,
            instructions=instructions,
            input=prompt,
            tools=[{"type": "web_search", "search_context_size": _context_size}],
            tool_choice="required",
        )

    try:
        response = retry_with_exponential_backoff(
            make_api_call,
            max_retries=5,
            initial_delay=1.0,
            max_delay=60.0,
            rate_limiter=rate_limiter,
        )
        return extract_response_content(response)
    except OpenAIError as e:
        if is_rate_limit_error(e):
            raise create_rate_limit_error(e) from e
        raise


def call_chat_completions(
    messages: list,
    model: Optional[str] = None,
    temperature: float = 0.3,
) -> str:
    """
    Call the OpenAI Chat Completions API.

    Applies the global rate-limiter and exponential-backoff retry automatically.

    Args:
        messages: The messages list in OpenAI chat format.
        model: Override the default OPENAI_MODEL.
        temperature: Sampling temperature (default 0.3).

    Returns:
        The assistant's response text.

    Raises:
        RateLimitError: if the rate limit is exceeded after all retries.
        OpenAIError: for any other API-level error.
    """
    _model = model or OPENAI_MODEL
    client = get_openai_client()
    rate_limiter = get_rate_limiter()

    def make_api_call():
        return client.chat.completions.create(
            model=_model,
            messages=messages,
            temperature=temperature,
        )

    try:
        completion = retry_with_exponential_backoff(
            make_api_call,
            max_retries=5,
            initial_delay=1.0,
            max_delay=60.0,
            rate_limiter=rate_limiter,
        )
        return completion.choices[0].message.content or ""
    except OpenAIError as e:
        if is_rate_limit_error(e):
            raise create_rate_limit_error(e) from e
        raise
