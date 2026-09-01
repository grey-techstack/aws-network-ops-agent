"""Retry decorator with exponential backoff for tool execution."""

import time
import logging
from functools import wraps
from typing import Callable, Type, Tuple, Any
from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)


# Transient error types that should trigger retries
TRANSIENT_ERROR_CODES = {
    "Throttling",
    "ThrottlingException",
    "TooManyRequestsException",
    "RequestLimitExceeded",
    "ServiceUnavailable",
    "InternalError",
    "RequestTimeout",
    "NetworkingError",
}


def is_transient_error(exception: Exception) -> bool:
    """
    Determine if an exception represents a transient error that should be retried.
    
    Args:
        exception: The exception to check
        
    Returns:
        True if the error is transient and should be retried
    """
    # Check for boto3 ClientError with transient error codes
    if isinstance(exception, ClientError):
        error_code = exception.response.get("Error", {}).get("Code", "")
        return error_code in TRANSIENT_ERROR_CODES
    
    # Check for network-related exceptions
    if isinstance(exception, (ConnectionError, TimeoutError)):
        return True
    
    return False


def retry_with_exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
):
    """
    Decorator that retries a function with exponential backoff on transient errors.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay in seconds (default: 60.0)
        exponential_base: Base for exponential calculation (default: 2.0)
        jitter: Whether to add random jitter to delays (default: True)
        
    Returns:
        Decorated function that implements retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    
                    # Check if this is the last attempt
                    if attempt == max_retries:
                        func_name = getattr(func, '__name__', 'unknown')
                        logger.error(
                            f"Function {func_name} failed after {max_retries} retries. "
                            f"Last error: {str(e)}"
                        )
                        raise
                    
                    # Check if error is transient
                    if not is_transient_error(e):
                        func_name = getattr(func, '__name__', 'unknown')
                        logger.warning(
                            f"Function {func_name} failed with non-transient error: {str(e)}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter if enabled
                    if jitter:
                        import random
                        delay = delay * (0.5 + random.random() * 0.5)
                    
                    func_name = getattr(func, '__name__', 'unknown')
                    logger.info(
                        f"Function {func_name} failed with transient error: {str(e)}. "
                        f"Retrying in {delay:.2f} seconds (attempt {attempt + 1}/{max_retries})"
                    )
                    
                    time.sleep(delay)
            
            # This should never be reached, but just in case
            raise last_exception
        
        return wrapper
    return decorator
