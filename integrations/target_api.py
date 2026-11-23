"""Provide read-only access to the permitted revel8 simulation API.

All operations require explicit network opt-in through the application settings.
The client never sends simulated messages or starts conversations.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

from config.settings import Settings
from integrations.api_errors import SimulationScopeError, TargetAPIError
from integrations.api_models import EventsResponse, Scenario, Session
from integrations.rate_limiter import AsyncRateLimiter
from integrations.retry import RetryPolicy, retry_async

_SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class TargetAPIClient:
    """Fetch simulation data with rate limiting and transient-error retries."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        rate_limiter: AsyncRateLimiter | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        """Create a restricted asynchronous HTTP client.

        Args:
            settings: Validated simulation connection settings.
            transport: Optional HTTP transport for offline testing.
            rate_limiter: Shared per-team limiter, if provided.
            retry_policy: Retry settings for idempotent GET requests.

        """
        self.settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.target_api_base_url.rstrip("/") + "/",
            timeout=httpx.Timeout(settings.http_timeout_seconds),
            follow_redirects=False,
            transport=transport,
        )
        self._rate_limiter = rate_limiter or AsyncRateLimiter(
            max_requests=settings.requests_per_minute,
        )
        self._retry_policy = retry_policy or RetryPolicy()
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_requests)

    async def __aenter__(self) -> TargetAPIClient:
        """Return this client within an asynchronous context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        """Close the HTTP transport when exiting the context."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._client.aclose()

    async def _get(self, path: str) -> Any:
        """Fetch JSON from a validated, read-only API path.

        Args:
            path: Relative API endpoint, without leading slash.

        Returns:
            JSON-decoded response body.

        Raises:
            SimulationScopeError: When live access is not authorized.
            TargetAPIError: When the server fails or returns invalid JSON.

        """
        if self.settings.dry_run:
            raise SimulationScopeError("Network calls are disabled in dry-run mode")
        if not self.settings.team_key or not self.settings.team_key.get_secret_value():
            raise SimulationScopeError("Missing CASPIANX_TEAM_KEY")
        if (
            not path
            or path.startswith("/")
            or ".." in path
            or "://" in path
            or "?" in path
            or "#" in path
        ):
            raise SimulationScopeError("Expected a clean API-relative path")

        headers = {"Authorization": (f"Bearer {self.settings.team_key.get_secret_value()}")}

        async def attempt() -> Any:
            """Perform a single rate-limited GET attempt."""
            await self._rate_limiter.acquire()

            async with self._semaphore:
                response = await self._client.get(path, headers=headers)

            if not response.is_success:
                raise TargetAPIError(
                    response.status_code,
                    "Request rejected by simulation API",
                )

            try:
                return response.json()
            except ValueError as error:
                raise TargetAPIError(
                    response.status_code,
                    "Invalid JSON response",
                ) from error

        return await retry_async(
            attempt,
            idempotent=True,
            policy=self._retry_policy,
        )

    async def list_scenarios(self) -> list[Scenario]:
        """Fetch published practice and evaluation scenario metadata."""
        data = await self._get("scenarios")
        return [Scenario.model_validate(item) for item in data]

    async def get_session(self, session_id: str) -> Session:
        """Retrieve one simulation session by its validated ID."""
        self._validate_id(session_id)
        data = await self._get(f"sessions/{session_id}")
        return Session.model_validate(data)

    async def list_sessions(self) -> list[Session]:
        """List all sessions visible to the authenticated team."""
        data = await self._get("sessions")

        if isinstance(data, dict):
            data = data.get("sessions", [])

        return [Session.model_validate(item) for item in data]

    async def get_events(self, session_id: str) -> EventsResponse:
        """Retrieve recorded simulation events for one session."""
        self._validate_id(session_id)
        data = await self._get(f"sessions/{session_id}/events")
        return EventsResponse.model_validate(data)

    @staticmethod
    def _validate_id(value: str) -> None:
        """Reject unsafe or malformed simulation resource identifiers."""
        if not isinstance(value, str) or not _SESSION_ID_PATTERN.fullmatch(value):
            raise SimulationScopeError("Invalid session ID")
