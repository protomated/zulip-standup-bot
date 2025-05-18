import time
import logging
import threading
from typing import Dict, Any, List, Optional, Callable, Tuple
from collections import defaultdict, deque
from datetime import datetime, timedelta

class RateLimiter:
    """
    Rate limiting and throttling for the Standup Bot.
    Provides methods for limiting the rate of operations.
    """

    def __init__(self, logger=None):
        """
        Initialize the rate limiter.

        Args:
            logger: Optional logger instance.
        """
        self.logger = logger or logging.getLogger('standup_bot.rate_limiter')

        # Rate limit buckets (key -> list of timestamps)
        self.buckets: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

        # Default limits
        self.default_limits = {
            'api_calls': (60, 60),  # 60 calls per 60 seconds
            'user_commands': (30, 60),  # 30 commands per 60 seconds
            'scheduled_tasks': (10, 60),  # 10 tasks per 60 seconds
        }

        # Custom limits
        self.custom_limits: Dict[str, Tuple[int, int]] = {}

        # Lock for thread safety
        self.lock = threading.RLock()

    def set_limit(self, key: str, max_calls: int, period_seconds: int) -> None:
        """
        Set a custom rate limit for a specific key.

        Args:
            key: The rate limit key.
            max_calls: Maximum number of calls allowed in the period.
            period_seconds: Period in seconds.
        """
        with self.lock:
            self.custom_limits[key] = (max_calls, period_seconds)
            self.logger.info(f"Set rate limit for {key}: {max_calls} calls per {period_seconds} seconds")

    def check_limit(self, key: str, subkey: Optional[str] = None) -> bool:
        """
        Check if an operation would exceed the rate limit.

        Args:
            key: The rate limit key.
            subkey: Optional subkey for more granular limits (e.g., user_id).

        Returns:
            True if the operation is allowed, False if it would exceed the limit.
        """
        with self.lock:
            # Determine the bucket key
            bucket_key = key if subkey is None else f"{key}:{subkey}"

            # Get the limit for this key
            limit = self.custom_limits.get(key, self.default_limits.get(key, (100, 60)))
            max_calls, period_seconds = limit

            # Get the current time
            now = time.time()

            # Clean up old timestamps
            cutoff = now - period_seconds
            while self.buckets[bucket_key] and self.buckets[bucket_key][0] < cutoff:
                self.buckets[bucket_key].popleft()

            # Check if we're over the limit
            if len(self.buckets[bucket_key]) >= max_calls:
                self.logger.warning(f"Rate limit exceeded for {bucket_key}: {max_calls} calls per {period_seconds} seconds")
                return False

            return True

    def record_call(self, key: str, subkey: Optional[str] = None) -> None:
        """
        Record an operation for rate limiting.

        Args:
            key: The rate limit key.
            subkey: Optional subkey for more granular limits (e.g., user_id).
        """
        with self.lock:
            # Determine the bucket key
            bucket_key = key if subkey is None else f"{key}:{subkey}"

            # Record the timestamp
            self.buckets[bucket_key].append(time.time())

    def is_allowed(self, key: str, subkey: Optional[str] = None) -> bool:
        """
        Check if an operation is allowed and record it if it is.

        Args:
            key: The rate limit key.
            subkey: Optional subkey for more granular limits (e.g., user_id).

        Returns:
            True if the operation is allowed, False if it exceeds the limit.
        """
        with self.lock:
            if self.check_limit(key, subkey):
                self.record_call(key, subkey)
                return True
            return False

    def wait_if_needed(self, key: str, subkey: Optional[str] = None, max_wait: float = 5.0) -> bool:
        """
        Wait if necessary to stay within rate limits.

        Args:
            key: The rate limit key.
            subkey: Optional subkey for more granular limits (e.g., user_id).
            max_wait: Maximum time to wait in seconds.

        Returns:
            True if the operation is allowed (possibly after waiting),
            False if it would still exceed the limit after waiting.
        """
        with self.lock:
            # Check if we're already under the limit
            if self.check_limit(key, subkey):
                self.record_call(key, subkey)
                return True

            # Get the limit for this key
            limit = self.custom_limits.get(key, self.default_limits.get(key, (100, 60)))
            max_calls, period_seconds = limit

            # Determine the bucket key
            bucket_key = key if subkey is None else f"{key}:{subkey}"

            # Get the current time
            now = time.time()

            # If we have timestamps, calculate when the oldest will expire
            if self.buckets[bucket_key]:
                oldest = self.buckets[bucket_key][0]
                wait_time = (oldest + period_seconds) - now

                # If the wait time is reasonable, wait and then allow
                if wait_time <= max_wait:
                    self.logger.info(f"Waiting {wait_time:.2f}s for rate limit on {bucket_key}")
                    time.sleep(wait_time)

                    # After waiting, record the call and allow it
                    self.record_call(key, subkey)
                    return True

            # If we get here, we can't wait long enough
            self.logger.warning(f"Rate limit exceeded for {bucket_key} and max wait time ({max_wait}s) is too short")
            return False

    def get_rate_limit_status(self, key: str, subkey: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the current status of a rate limit.

        Args:
            key: The rate limit key.
            subkey: Optional subkey for more granular limits (e.g., user_id).

        Returns:
            Dictionary with rate limit status information.
        """
        with self.lock:
            # Determine the bucket key
            bucket_key = key if subkey is None else f"{key}:{subkey}"

            # Get the limit for this key
            limit = self.custom_limits.get(key, self.default_limits.get(key, (100, 60)))
            max_calls, period_seconds = limit

            # Get the current time
            now = time.time()

            # Clean up old timestamps
            cutoff = now - period_seconds
            while self.buckets[bucket_key] and self.buckets[bucket_key][0] < cutoff:
                self.buckets[bucket_key].popleft()

            # Calculate remaining calls
            used_calls = len(self.buckets[bucket_key])
            remaining_calls = max_calls - used_calls

            # Calculate reset time
            reset_time = now + period_seconds if used_calls == 0 else (
                self.buckets[bucket_key][0] + period_seconds if self.buckets[bucket_key] else now + period_seconds
            )

            return {
                'limit': max_calls,
                'remaining': remaining_calls,
                'used': used_calls,
                'period_seconds': period_seconds,
                'reset_time': datetime.fromtimestamp(reset_time).isoformat(),
                'reset_seconds': reset_time - now
            }

    def clear_limits(self, key: Optional[str] = None, subkey: Optional[str] = None) -> None:
        """
        Clear rate limit history.

        Args:
            key: Optional key to clear. If None, clears all keys.
            subkey: Optional subkey to clear. If None, clears all subkeys for the key.
        """
        with self.lock:
            if key is None:
                # Clear all buckets
                self.buckets.clear()
                self.logger.info("Cleared all rate limit history")
            elif subkey is None:
                # Clear all subkeys for this key
                prefix = f"{key}:"
                keys_to_clear = [k for k in self.buckets.keys() if k == key or k.startswith(prefix)]
                for k in keys_to_clear:
                    del self.buckets[k]
                self.logger.info(f"Cleared rate limit history for key: {key}")
            else:
                # Clear specific key:subkey
                bucket_key = f"{key}:{subkey}"
                if bucket_key in self.buckets:
                    del self.buckets[bucket_key]
                self.logger.info(f"Cleared rate limit history for {bucket_key}")


class ThrottledDecorator:
    """
    Decorator for rate-limiting function calls.
    """

    def __init__(self, rate_limiter: RateLimiter, key: str, subkey_func: Optional[Callable] = None):
        """
        Initialize the decorator.

        Args:
            rate_limiter: RateLimiter instance.
            key: Rate limit key.
            subkey_func: Optional function to extract subkey from function arguments.
        """
        self.rate_limiter = rate_limiter
        self.key = key
        self.subkey_func = subkey_func

    def __call__(self, func):
        """Apply the decorator to a function."""
        def wrapper(*args, **kwargs):
            # Determine subkey if needed
            subkey = None
            if self.subkey_func:
                subkey = self.subkey_func(*args, **kwargs)

            # Check rate limit
            if not self.rate_limiter.is_allowed(self.key, subkey):
                # Handle rate limit exceeded
                self.rate_limiter.logger.warning(
                    f"Rate limit exceeded for {func.__name__} ({self.key}:{subkey})"
                )
                # You could raise an exception, return None, or handle it in another way
                return None

            # Call the function if allowed
            return func(*args, **kwargs)

        return wrapper


def throttled(rate_limiter: RateLimiter, key: str, subkey_func: Optional[Callable] = None):
    """
    Decorator for rate-limiting function calls.

    Args:
        rate_limiter: RateLimiter instance.
        key: Rate limit key.
        subkey_func: Optional function to extract subkey from function arguments.

    Returns:
        Decorated function.
    """
    return ThrottledDecorator(rate_limiter, key, subkey_func)
