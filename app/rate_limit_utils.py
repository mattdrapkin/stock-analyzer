"""
Utility functions for handling OpenAI API rate limit errors.
"""

import re
import logging
from typing import Optional
from openai import OpenAIError

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when OpenAI API rate limit is exceeded."""
    pass


def is_rate_limit_error(error: OpenAIError) -> bool:
    """Check if an OpenAI error is a rate limit error."""
    if hasattr(error, 'code') and error.code == 'rate_limit_exceeded':
        return True
    error_str = str(error).lower()
    return 'rate limit' in error_str or 'rate_limit_exceeded' in error_str


def extract_wait_time(error: OpenAIError) -> Optional[float]:
    """Extract wait time in seconds from rate limit error message."""
    error_str = str(error)
    # Look for patterns like "Please try again in 4.55s" or "Please try again in 5 seconds"
    match = re.search(r'Please try again in (\d+\.?\d*)s', error_str)
    if match:
        return float(match.group(1))
    match = re.search(r'Please try again in (\d+) seconds?', error_str)
    if match:
        return float(match.group(1))
    return None


def format_rate_limit_error(error: OpenAIError) -> str:
    """Format a rate limit error with user-friendly message."""
    wait_time = extract_wait_time(error)
    if wait_time:
        wait_str = f"{wait_time:.1f}" if wait_time < 60 else f"{wait_time/60:.1f} minutes"
        return (
            f"⏱️ **Rate limit reached** - The OpenAI API has hit its usage limit.\n\n"
            f"Please wait {wait_str} before trying again.\n\n"
            f"This is a temporary limit from OpenAI, not an issue with your account."
        )
    else:
        return (
            f"⏱️ **Rate limit reached** - The OpenAI API has hit its usage limit.\n\n"
            f"Please wait a moment before trying again.\n\n"
            f"This is a temporary limit from OpenAI, not an issue with your account."
        )
