"""
Utility functions for handling OpenAI API rate limit errors.
"""

import re
import logging
from typing import Optional, Dict, Any
from openai import OpenAIError

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when OpenAI API rate limit is exceeded."""
    
    def __init__(self, message: str, limit_type: Optional[str] = None, wait_time: Optional[float] = None):
        super().__init__(message)
        self.limit_type = limit_type
        self.wait_time = wait_time


# All OpenAI rate limit error codes
RATE_LIMIT_ERROR_CODES = {
    'rate_limit_exceeded',
    'quota_exceeded',
    'insufficient_quota',
}


def is_rate_limit_error(error: OpenAIError) -> bool:
    """
    Check if an OpenAI error is a rate limit error.
    
    Detects rate limits via:
    1. Error code (rate_limit_exceeded, quota_exceeded, insufficient_quota)
    2. HTTP status code 429
    3. Error message content
    """
    # Check error code
    if hasattr(error, 'code') and error.code in RATE_LIMIT_ERROR_CODES:
        return True
    
    # Check HTTP status code
    if hasattr(error, 'status_code') and error.status_code == 429:
        return True
    
    # Check error message content
    error_str = str(error).lower()
    rate_limit_indicators = [
        'rate limit',
        'rate_limit_exceeded',
        'quota exceeded',
        'insufficient quota',
        'too many requests',
        'rate_limited',
    ]
    return any(indicator in error_str for indicator in rate_limit_indicators)


def extract_wait_time(error: OpenAIError) -> Optional[float]:
    """
    Extract wait time in seconds from rate limit error message.
    
    Looks for patterns like:
    - "Please try again in 4.55s"
    - "Please try again in 5 seconds"
    - "try again in 2m"
    """
    error_str = str(error)
    
    # Pattern: "Please try again in 4.55s"
    match = re.search(r'Please try again in (\d+\.?\d*)s', error_str)
    if match:
        return float(match.group(1))
    
    # Pattern: "Please try again in 5 seconds"
    match = re.search(r'Please try again in (\d+) seconds?', error_str)
    if match:
        return float(match.group(1))
    
    # Pattern: "try again in 2m" (minutes)
    match = re.search(r'try again in (\d+\.?\d*)m', error_str)
    if match:
        return float(match.group(1)) * 60
    
    # Pattern: "try again in 2 minutes"
    match = re.search(r'try again in (\d+) minutes?', error_str)
    if match:
        return float(match.group(1)) * 60
    
    return None


def extract_limit_type(error: OpenAIError) -> Optional[str]:
    """
    Extract the type of rate limit that was hit.
    
    Returns one of: 'rpm', 'rpd', 'tpm', 'token', 'quota', or None
    """
    error_str = str(error).lower()
    
    if 'rpm' in error_str or 'requests per minute' in error_str:
        return 'rpm'
    elif 'rpd' in error_str or 'requests per day' in error_str:
        return 'rpd'
    elif 'tpm' in error_str or 'tokens per minute' in error_str:
        return 'tpm'
    elif 'token' in error_str and 'limit' in error_str:
        return 'token'
    elif 'quota' in error_str:
        return 'quota'
    
    return None


def get_rate_limit_error_details(error: OpenAIError) -> Dict[str, Any]:
    """
    Extract structured information from a rate limit error.
    
    Returns dict with keys:
    - limit_type: Type of limit hit (rpm, rpd, tpm, token, quota)
    - wait_time: Suggested wait time in seconds (if available)
    - error_code: OpenAI error code (if available)
    - status_code: HTTP status code (if available)
    """
    return {
        'limit_type': extract_limit_type(error),
        'wait_time': extract_wait_time(error),
        'error_code': getattr(error, 'code', None),
        'status_code': getattr(error, 'status_code', None),
    }


def format_rate_limit_error(error: OpenAIError) -> str:
    """Format a rate limit error with user-friendly message."""
    details = get_rate_limit_error_details(error)
    wait_time = details['wait_time']
    limit_type = details['limit_type']
    
    # Build base message
    message = "⏱️ **Rate limit reached** - The OpenAI API has hit its usage limit.\n\n"
    
    # Add specific limit type information
    if limit_type:
        limit_descriptions = {
            'rpm': 'requests per minute',
            'rpd': 'requests per day',
            'tpm': 'tokens per minute',
            'token': 'token limit',
            'quota': 'account quota',
        }
        message += f"Limit type: {limit_descriptions.get(limit_type, limit_type)}\n\n"
    
    # Add wait time if available
    if wait_time:
        if wait_time < 60:
            wait_str = f"{wait_time:.1f} seconds"
        elif wait_time < 3600:
            wait_str = f"{wait_time/60:.1f} minutes"
        else:
            wait_str = f"{wait_time/3600:.1f} hours"
        message += f"Please wait {wait_str} before trying again.\n\n"
    else:
        message += "Please wait a moment before trying again.\n\n"
    
    message += "This is a temporary limit from OpenAI, not an issue with your account."
    
    return message


def create_rate_limit_error(error: OpenAIError) -> RateLimitError:
    """
    Create a RateLimitError with structured information from an OpenAIError.
    
    This is the preferred way to create RateLimitError instances to ensure
    consistent error information across the application.
    """
    details = get_rate_limit_error_details(error)
    message = format_rate_limit_error(error)
    
    return RateLimitError(
        message=message,
        limit_type=details['limit_type'],
        wait_time=details['wait_time']
    )
