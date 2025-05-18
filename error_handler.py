import logging
import traceback
import sys
import time
from typing import Callable, Any, Dict, Optional, Type, List, Tuple
from functools import wraps

class ErrorHandler:
    """
    Centralized error handling for the Standup Bot.
    Provides decorators and utilities for robust error handling.
    """

    def __init__(self, logger=None):
        """
        Initialize the error handler.

        Args:
            logger: Optional logger instance. If not provided, a new one will be created.
        """
        self.logger = logger or logging.getLogger('standup_bot.error_handler')
        self.error_counts: Dict[str, Dict[str, Any]] = {}
        self.max_retries = 3
        self.retry_delay = 2  # seconds

    def with_error_handling(self,
                           error_types: Optional[List[Type[Exception]]] = None,
                           default_return: Any = None,
                           retry: bool = False,
                           max_retries: int = None,
                           retry_delay: int = None,
                           retry_backoff: bool = True,
                           critical: bool = False):
        """
        Decorator for functions that need error handling.

        Args:
            error_types: List of exception types to catch. If None, catches all exceptions.
            default_return: Value to return if an exception occurs.
            retry: Whether to retry the function on failure.
            max_retries: Maximum number of retries. Defaults to self.max_retries.
            retry_delay: Delay between retries in seconds. Defaults to self.retry_delay.
            retry_backoff: Whether to use exponential backoff for retries.
            critical: Whether this is a critical function. If True, logs at ERROR level.

        Returns:
            Decorated function.
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                func_name = func.__name__
                error_key = f"{func.__module__}.{func_name}"

                # Initialize error count for this function if not exists
                if error_key not in self.error_counts:
                    self.error_counts[error_key] = {
                        'count': 0,
                        'last_error': None,
                        'last_error_time': None
                    }

                # Set retry parameters
                _max_retries = max_retries if max_retries is not None else self.max_retries
                _retry_delay = retry_delay if retry_delay is not None else self.retry_delay

                # Try to execute the function with retries if enabled
                retries = 0
                while True:
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        # Check if we should catch this exception
                        if error_types and not any(isinstance(e, t) for t in error_types):
                            raise

                        # Update error count
                        self.error_counts[error_key]['count'] += 1
                        self.error_counts[error_key]['last_error'] = str(e)
                        self.error_counts[error_key]['last_error_time'] = time.time()

                        # Log the error
                        log_level = logging.ERROR if critical else logging.WARNING
                        self.logger.log(log_level,
                                       f"Error in {func_name}: {str(e)}",
                                       exc_info=True)

                        # Check if we should retry
                        if retry and retries < _max_retries:
                            retries += 1
                            delay = _retry_delay * (2 ** (retries - 1)) if retry_backoff else _retry_delay
                            self.logger.info(f"Retrying {func_name} in {delay} seconds (attempt {retries}/{_max_retries})")
                            time.sleep(delay)
                            continue

                        # Return default value if no more retries
                        return default_return

            return wrapper

        return decorator

    def retry_with_backoff(self,
                          max_retries: int = 3,
                          initial_delay: float = 1.0,
                          backoff_factor: float = 2.0,
                          error_types: Optional[List[Type[Exception]]] = None):
        """
        Decorator for retrying a function with exponential backoff.

        Args:
            max_retries: Maximum number of retries.
            initial_delay: Initial delay between retries in seconds.
            backoff_factor: Factor to multiply delay by after each retry.
            error_types: List of exception types to catch. If None, catches all exceptions.

        Returns:
            Decorated function.
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                retries = 0
                delay = initial_delay

                while True:
                    try:
                        return func(*args, **kwargs)
                    except Exception as e:
                        # Check if we should catch this exception
                        if error_types and not any(isinstance(e, t) for t in error_types):
                            raise

                        retries += 1
                        if retries > max_retries:
                            self.logger.error(
                                f"Failed after {max_retries} retries: {func.__name__} - {str(e)}",
                                exc_info=True
                            )
                            raise

                        self.logger.warning(
                            f"Retry {retries}/{max_retries} for {func.__name__} after error: {str(e)}"
                        )

                        time.sleep(delay)
                        delay *= backoff_factor

            return wrapper

        return decorator

    def get_error_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics about errors that have occurred.

        Returns:
            Dictionary with error statistics.
        """
        return self.error_counts

    def reset_error_stats(self) -> None:
        """Reset error statistics."""
        self.error_counts = {}

    def log_exception(self, e: Exception, context: str = None, critical: bool = False) -> None:
        """
        Log an exception with context.

        Args:
            e: The exception to log.
            context: Additional context for the error.
            critical: Whether this is a critical error. If True, logs at ERROR level.
        """
        log_level = logging.ERROR if critical else logging.WARNING
        message = f"Exception: {str(e)}"
        if context:
            message = f"{context}: {message}"

        self.logger.log(log_level, message, exc_info=True)
