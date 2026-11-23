"""Test request pacing and bounded retries without external network access."""

from __future__ import annotations

import asyncio

import pytest

from integrations.api_errors import TargetAPIError
from integrations.rate_limiter import AsyncRateLimiter
from integrations.retry import RetryPolicy, retry_async


def test_rate_limiter_rejects_invalid_limits() -> None:
    """Reject nonpositive rate-limit settings."""
    with pytest.raises(ValueError):
        AsyncRateLimiter(max_requests=0)

    with pytest.raises(ValueError):
        AsyncRateLimiter(period_seconds=0)


def test_rate_limiter_accepts_available_slots() -> None:
    """Accept requests without delay while capacity remains."""

    async def run() -> None:
        """Acquire all permitted slots in a mock time window."""
        limiter = AsyncRateLimiter(
            max_requests=2,
            period_seconds=60,
        )
        await asyncio.wait_for(limiter.acquire(), timeout=0.5)
        await asyncio.wait_for(limiter.acquire(), timeout=0.5)

    asyncio.run(run())


def test_rate_limiter_waits_for_window() -> None:
    """Hold requests exceeding the rolling-window capacity."""

    async def run() -> None:
        """Verify an extra request waits until the window expires."""
        limiter = AsyncRateLimiter(
            max_requests=1,
            period_seconds=0.05,
        )
        await limiter.acquire()
        await asyncio.wait_for(limiter.acquire(), timeout=0.5)

    asyncio.run(run())


def test_retry_policy_validates_bounds() -> None:
    """Reject negative delays and empty retry budgets."""
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)

    with pytest.raises(ValueError):
        RetryPolicy(base_delay_seconds=-1)

    with pytest.raises(ValueError):
        RetryPolicy(
            base_delay_seconds=3,
            max_delay_seconds=2,
        )


def test_retry_transient_error() -> None:
    """Retry a transient failure and return the successful result."""

    async def run() -> None:
        """Simulate one HTTP 503 response followed by success."""
        attempts = 0
        delays: list[float] = []

        async def operation() -> str:
            """Fail once with HTTP 503, then succeed."""
            nonlocal attempts
            attempts += 1

            if attempts == 1:
                raise TargetAPIError(status_code=503)

            return "ok"

        async def fake_sleep(delay: float) -> None:
            """Capture requested backoff without waiting."""
            delays.append(delay)

        result = await retry_async(
            operation,
            idempotent=True,
            policy=RetryPolicy(base_delay_seconds=0.5),
            sleep=fake_sleep,
        )

        assert result == "ok"
        assert attempts == 2
        assert delays == [0.5]

    asyncio.run(run())


def test_nonretryable_error_stops() -> None:
    """Never retry a request rejected with HTTP 422."""

    async def run() -> None:
        """Check that validation failures return immediately."""
        attempts = 0

        async def operation() -> None:
            """Raise a permanent request error."""
            nonlocal attempts
            attempts += 1
            raise TargetAPIError(status_code=422)

        with pytest.raises(TargetAPIError):
            await retry_async(
                operation,
                idempotent=True,
            )

        assert attempts == 1

    asyncio.run(run())


def test_nonidempotent_request_stops() -> None:
    """Never retry state-changing requests without retry guarantees."""

    async def run() -> None:
        """Check that an unprotected operation runs only once."""
        attempts = 0

        async def operation() -> None:
            """Raise an otherwise retryable server error."""
            nonlocal attempts
            attempts += 1
            raise TargetAPIError(status_code=503)

        with pytest.raises(TargetAPIError):
            await retry_async(
                operation,
                idempotent=False,
            )

        assert attempts == 1

    asyncio.run(run())


def test_retry_budget_is_bounded() -> None:
    """Raise the final error after all retry attempts are exhausted."""

    async def run() -> None:
        """Check the attempt budget and exponential delays."""
        attempts = 0
        delays: list[float] = []

        async def operation() -> None:
            """Raise a temporary server error on every attempt."""
            nonlocal attempts
            attempts += 1
            raise TargetAPIError(status_code=503)

        async def fake_sleep(delay: float) -> None:
            """Capture backoff delays without sleeping."""
            delays.append(delay)

        with pytest.raises(TargetAPIError):
            await retry_async(
                operation,
                idempotent=True,
                policy=RetryPolicy(
                    max_attempts=3,
                    base_delay_seconds=1,
                    max_delay_seconds=2,
                ),
                sleep=fake_sleep,
            )

        assert attempts == 3
        assert delays == [1, 2]

    asyncio.run(run())
