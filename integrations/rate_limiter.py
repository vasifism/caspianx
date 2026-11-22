"""Enforce a rolling-window request limit for asynchronous API clients."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Callable


class AsyncRateLimiter:
    """Limit request starts within a rolling time window.

    The limiter is local to one Python process. Share one instance among
    all API clients using the same team credentials.
    """

    def __init__(
        self,
        max_requests: int = 60,
        period_seconds: float = 60.0,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialize request and timing limits.

        Args:
            max_requests: Maximum starts allowed per rolling window.
            period_seconds: Rolling-window duration in seconds.
            clock: Monotonic clock function used to timestamp requests.

        Raises:
            ValueError: If either limit is not positive.

        """
        if max_requests < 1 or period_seconds <= 0:
            raise ValueError("Rate limits must be positive.")

        self.max_requests = max_requests
        self.period_seconds = period_seconds
        self._clock = clock
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until the current rolling window permits a request.

        Each successful acquisition reserves one request slot. The slot is
        consumed even if a later HTTP request fails or is cancelled.
        """
        while True:
            async with self._lock:
                now = self._clock()
                cutoff = now - self.period_seconds

                while self._timestamps and self._timestamps[0] <= cutoff:
                    self._timestamps.popleft()

                if len(self._timestamps) < self.max_requests:
                    self._timestamps.append(now)
                    return

                wait_seconds = self._timestamps[0] + self.period_seconds - now

            await asyncio.sleep(max(wait_seconds, 0.001))
