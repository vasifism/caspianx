"""Retry transient asynchronous transport errors with bounded backoff."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar

import httpx

from integrations.api_errors import TargetAPIError


ResultT = TypeVar("ResultT")
RETRYABLE_STATUSES = frozenset({429, 502, 503, 504})


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Specify bounds for retrying temporary failures.

    Attributes:
        max_attempts: Total attempts, including the initial request.
        base_delay_seconds: Delay before the first retry.
        max_delay_seconds: Maximum delay between retries.

    """

    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 8.0

    def __post_init__(self) -> None:
        """Validate retry policy parameters.

        Raises:
            ValueError: If attempts or delay bounds are invalid.

        """
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least one.")
        if self.base_delay_seconds < 0:
            raise ValueError("base_delay_seconds cannot be negative.")
        if self.max_delay_seconds < self.base_delay_seconds:
            raise ValueError("max_delay_seconds cannot be below base delay.")


def is_retryable(error: Exception) -> bool:
    """Determine whether an exception represents a temporary failure.

    Args:
        error: Exception raised by the attempted HTTP request.

    Returns:
        Whether the exception is safe to retry at the transport level.

    """
    if isinstance(error, TargetAPIError):
        return error.status_code in RETRYABLE_STATUSES

    return isinstance(error, httpx.TransportError)


async def retry_async(
    operation: Callable[[], Awaitable[ResultT]],
    *,
    idempotent: bool,
    policy: RetryPolicy | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> ResultT:
    """Execute an asynchronous operation with bounded retry attempts.

    Retry is allowed only when the caller guarantees an idempotent request.
    For a state-changing Target API request, reuse the same request body
    and Idempotency-Key on every attempt. Never generate a new key here.

    Args:
        operation: Zero-argument async callable representing one request.
        idempotent: Whether repeating the operation is safe.
        policy: Optional retry configuration.
        sleep: Async delay callable, replaceable for deterministic tests.

    Returns:
        The operation's successful result.

    Raises:
        Exception: The last request failure when no retry is permitted or
            the configured attempt limit is reached.

    """
    active_policy = policy or RetryPolicy()

    for attempt in range(active_policy.max_attempts):
        try:
            return await operation()

        except (TargetAPIError, httpx.TransportError) as error:
            is_last = attempt + 1 == active_policy.max_attempts

            if not idempotent or is_last or not is_retryable(error):
                raise

            delay = min(
                active_policy.base_delay_seconds * (2**attempt),
                active_policy.max_delay_seconds,
            )
            await sleep(delay)

    raise RuntimeError("Retry loop terminated unexpectedly.")
