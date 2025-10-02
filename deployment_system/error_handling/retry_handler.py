"""
Retry Handler

Provides retry logic for transient failures with exponential backoff
and configurable retry policies.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Optional, Type, Union, List
from dataclasses import dataclass
from enum import Enum
import random

from .error_types import (
    DeploymentSystemError,
    ErrorCategory,
    PrefectAPIError,
    DockerError,
)

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy types."""

    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    RANDOM_JITTER = "random_jitter"


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    backoff_multiplier: float = 2.0
    jitter: bool = True
    retryable_exceptions: Optional[List[Type[Exception]]] = None
    retryable_error_codes: Optional[List[str]] = None


class RetryHandler:
    """Handles retry logic for operations that may fail transiently."""

    # Default retryable exceptions
    DEFAULT_RETRYABLE_EXCEPTIONS = [
        ConnectionError,
        TimeoutError,
        PrefectAPIError,
        DockerError,
    ]

    # Default retryable error codes
    DEFAULT_RETRYABLE_ERROR_CODES = [
        "PREFECT_API_UNAVAILABLE",
        "DOCKER_DAEMON_UNAVAILABLE",
        "NETWORK_TIMEOUT",
        "CONNECTION_REFUSED",
        "TEMPORARY_FAILURE",
    ]

    def __init__(self, policy: Optional[RetryPolicy] = None):
        self.policy = policy or RetryPolicy()

        # Set default retryable exceptions if not provided
        if self.policy.retryable_exceptions is None:
            self.policy.retryable_exceptions = self.DEFAULT_RETRYABLE_EXCEPTIONS

        # Set default retryable error codes if not provided
        if self.policy.retryable_error_codes is None:
            self.policy.retryable_error_codes = self.DEFAULT_RETRYABLE_ERROR_CODES

    def is_retryable(self, exception: Exception) -> bool:
        """Check if an exception is retryable."""
        # Check exception type
        if any(
            isinstance(exception, exc_type)
            for exc_type in self.policy.retryable_exceptions
        ):
            return True

        # Check error code for deployment system errors
        if isinstance(exception, DeploymentSystemError):
            return exception.error_code in self.policy.retryable_error_codes

        return False

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt number."""
        if self.policy.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.policy.base_delay

        elif self.policy.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.policy.base_delay * (
                self.policy.backoff_multiplier ** (attempt - 1)
            )

        elif self.policy.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.policy.base_delay * attempt

        elif self.policy.strategy == RetryStrategy.RANDOM_JITTER:
            delay = self.policy.base_delay + random.uniform(0, self.policy.base_delay)

        else:
            delay = self.policy.base_delay

        # Apply jitter if enabled
        if self.policy.jitter and self.policy.strategy != RetryStrategy.RANDOM_JITTER:
            jitter = random.uniform(0.1, 0.3) * delay
            delay += jitter

        # Cap at max delay
        return min(delay, self.policy.max_delay)

    def retry(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute function with retry logic."""
        last_exception = None

        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                logger.debug(
                    f"Attempting operation (attempt {attempt}/{self.policy.max_attempts})"
                )
                return func(*args, **kwargs)

            except Exception as e:
                last_exception = e

                if not self.is_retryable(e):
                    logger.debug(
                        f"Exception {type(e).__name__} is not retryable, failing immediately"
                    )
                    raise e

                if attempt == self.policy.max_attempts:
                    logger.error(
                        f"Operation failed after {self.policy.max_attempts} attempts"
                    )
                    break

                delay = self.calculate_delay(attempt)
                logger.warning(
                    f"Operation failed (attempt {attempt}/{self.policy.max_attempts}): {e}. "
                    f"Retrying in {delay:.2f} seconds..."
                )
                time.sleep(delay)

        # If we get here, all attempts failed
        raise last_exception

    async def async_retry(self, func: Callable[..., Any], *args, **kwargs) -> Any:
        """Execute async function with retry logic."""
        last_exception = None

        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                logger.debug(
                    f"Attempting async operation (attempt {attempt}/{self.policy.max_attempts})"
                )
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except Exception as e:
                last_exception = e

                if not self.is_retryable(e):
                    logger.debug(
                        f"Exception {type(e).__name__} is not retryable, failing immediately"
                    )
                    raise e

                if attempt == self.policy.max_attempts:
                    logger.error(
                        f"Async operation failed after {self.policy.max_attempts} attempts"
                    )
                    break

                delay = self.calculate_delay(attempt)
                logger.warning(
                    f"Async operation failed (attempt {attempt}/{self.policy.max_attempts}): {e}. "
                    f"Retrying in {delay:.2f} seconds..."
                )
                await asyncio.sleep(delay)

        # If we get here, all attempts failed
        raise last_exception


class RetryContext:
    """Context manager for retry operations."""

    def __init__(self, policy: Optional[RetryPolicy] = None):
        self.handler = RetryHandler(policy)
        self.attempt = 0
        self.last_exception = None

    def __enter__(self):
        self.attempt += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val is not None:
            self.last_exception = exc_val

            if (
                self.handler.is_retryable(exc_val)
                and self.attempt < self.handler.policy.max_attempts
            ):
                delay = self.handler.calculate_delay(self.attempt)
                logger.warning(
                    f"Operation failed (attempt {self.attempt}/{self.handler.policy.max_attempts}): {exc_val}. "
                    f"Retrying in {delay:.2f} seconds..."
                )
                time.sleep(delay)
                return True  # Suppress the exception to retry

        return False  # Let the exception propagate


# Predefined retry policies for common scenarios
class RetryPolicies:
    """Predefined retry policies for common use cases."""

    # Quick retry for fast operations
    QUICK_RETRY = RetryPolicy(
        max_attempts=3,
        base_delay=0.5,
        max_delay=5.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    )

    # Standard retry for most operations
    STANDARD_RETRY = RetryPolicy(
        max_attempts=5,
        base_delay=1.0,
        max_delay=30.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    )

    # Patient retry for slow operations
    PATIENT_RETRY = RetryPolicy(
        max_attempts=10,
        base_delay=2.0,
        max_delay=120.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
    )

    # Network operations retry
    NETWORK_RETRY = RetryPolicy(
        max_attempts=5,
        base_delay=1.0,
        max_delay=60.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        jitter=True,
        retryable_exceptions=[
            ConnectionError,
            TimeoutError,
            PrefectAPIError,
        ],
        retryable_error_codes=[
            "PREFECT_API_UNAVAILABLE",
            "NETWORK_TIMEOUT",
            "CONNECTION_REFUSED",
        ],
    )

    # Docker operations retry
    DOCKER_RETRY = RetryPolicy(
        max_attempts=3,
        base_delay=2.0,
        max_delay=30.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        retryable_exceptions=[
            DockerError,
            ConnectionError,
        ],
        retryable_error_codes=[
            "DOCKER_DAEMON_UNAVAILABLE",
            "DOCKER_BUILD_FAILED",
        ],
    )


def with_retry(policy: Optional[RetryPolicy] = None):
    """Decorator to add retry logic to functions."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            handler = RetryHandler(policy or RetryPolicies.STANDARD_RETRY)
            return handler.retry(func, *args, **kwargs)

        return wrapper

    return decorator


def with_async_retry(policy: Optional[RetryPolicy] = None):
    """Decorator to add retry logic to async functions."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            handler = RetryHandler(policy or RetryPolicies.STANDARD_RETRY)
            return await handler.async_retry(func, *args, **kwargs)

        return wrapper

    return decorator
