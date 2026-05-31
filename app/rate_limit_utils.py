"""
Utility functions for handling OpenAI API rate limit errors.
"""

import os
import re
import logging
import random
import time
import threading
from typing import Optional, Dict, Any
from openai import OpenAIError

logger = logging.getLogger(__name__)


# ── Simple rate limiter ────────────────────────────────────────────────────────

class RateLimiter:
    """
    Simple token bucket rate limiter to prevent hitting OpenAI API rate limits.
    
    This limits the number of requests per minute across all API calls.
    """
    
    def __init__(self, max_requests_per_minute: int = 50):
        self.max_requests = max_requests_per_minute
        self.requests = []
        self.lock = threading.Lock()
    
    def acquire(self) -> bool:
        """
        Try to acquire a request token. Returns True if allowed, False if rate limited.
        If rate limited, will log the wait time.
        """
        with self.lock:
            now = time.time()
            # Remove requests older than 1 minute
            self.requests = [t for t in self.requests if now - t < 60]
            
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            else:
                # Calculate wait time until oldest request expires
                oldest = min(self.requests)
                wait_time = 60 - (now - oldest)
                logger.warning(f"Rate limit reached: {len(self.requests)}/{self.max_requests} requests in last minute. Wait {wait_time:.1f}s")
                return False
    
    def wait_if_needed(self) -> None:
        """
        Block until a request token is available.
        """
        while not self.acquire():
            time.sleep(0.5)


# Global rate limiter instance (configurable via environment variable)
try:
    _default_rpm = int(os.getenv("OPENAI_MAX_RPM", "50"))
except ValueError:
    logger.warning(f"Invalid OPENAI_MAX_RPM value, using default of 50")
    _default_rpm = 50
_global_rate_limiter = RateLimiter(max_requests_per_minute=_default_rpm)


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    return _global_rate_limiter


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


def retry_with_exponential_backoff(
    func,
    max_retries: int = 5,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    rate_limiter=None,
) -> Any:
    """
    Execute a function with exponential backoff retry logic for rate limit errors.
    
    This follows OpenAI's recommendation for handling rate limits:
    - Unsuccessful requests still count toward per-minute limits
    - Exponential backoff prevents tight retry loops
    - Respects suggested wait times from error messages when available
    
    Args:
        func: The function to execute (should return the result)
        max_retries: Maximum number of retry attempts (default: 5)
        initial_delay: Initial delay in seconds before first retry (default: 1.0)
        max_delay: Maximum delay between retries (default: 60.0)
        backoff_factor: Multiplier for exponential backoff (default: 2.0)
        rate_limiter: Optional RateLimiter instance to apply before each attempt
    
    Returns:
        The result of the function call
    
    Raises:
        The original exception if max retries are exceeded
    """
    import random
    
    last_exception = None
    delay = initial_delay
    
    for attempt in range(max_retries + 1):
        try:
            # Apply rate limiter if provided
            if rate_limiter:
                rate_limiter.wait_if_needed()
            
            # Execute the function
            logger.debug(f"retry_with_exponential_backoff: Attempt {attempt + 1}/{max_retries + 1}")
            result = func()
            logger.debug(f"retry_with_exponential_backoff: Function returned, type: {type(result)}")
            return result
            
        except Exception as e:
            last_exception = e
            
            # Log all exceptions for debugging
            logger.error(f"Exception in retry_with_exponential_backoff on attempt {attempt + 1}/{max_retries + 1}: {e}", exc_info=True)
            
            # Only retry on rate limit errors
            if not isinstance(e, OpenAIError) or not is_rate_limit_error(e):
                logger.error(f"Non-rate-limit error, raising immediately")
                raise
            
            # If this was the last attempt, raise the rate limit error
            if attempt == max_retries:
                logger.error(f"Max retries ({max_retries}) exceeded for rate limit error: {e}")
                raise create_rate_limit_error(e) from e
            
            # Extract suggested wait time from error if available
            suggested_wait = extract_wait_time(e)
            if suggested_wait:
                # Use the suggested wait time, capped at max_delay
                actual_wait = min(suggested_wait, max_delay)
                logger.info(f"Rate limit hit on attempt {attempt + 1}/{max_retries + 1}. Using suggested wait time: {actual_wait:.1f}s")
            else:
                # Use exponential backoff with jitter
                jitter = random.uniform(0.8, 1.2)  # Add 20% jitter to avoid thundering herd
                actual_wait = min(delay * jitter, max_delay)
                logger.info(f"Rate limit hit on attempt {attempt + 1}/{max_retries + 1}. Waiting {actual_wait:.1f}s (exponential backoff)")
            
            # Wait before retry
            time.sleep(actual_wait)
            
            # Increase delay for next attempt (exponential backoff)
            delay = min(delay * backoff_factor, max_delay)
    
    # This should never be reached, but just in case
    if last_exception:
        raise last_exception
