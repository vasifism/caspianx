"""Test the read-only target client against deterministic offline transports."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from pydantic import SecretStr

from config.settings import Settings
from integrations.api_errors import SimulationScopeError, TargetAPIError
from integrations.retry import RetryPolicy
from integrations.target_api import TargetAPIClient


def _settings(*, dry_run: bool = False) -> Settings:
    """Create isolated test settings with placeholder credentials."""
    return Settings(
        _env_file=None,
        dry_run=dry_run,
        team_key=SecretStr("test-only"),
    )


def test_read_only_client_retries_transient_errors() -> None:
    """Ensure a transient response can be recovered without real network use."""

    async def run() -> None:
        """Simulate a temporary failure followed by success."""
        requests = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            """Record GET requests and return scripted responses."""
            nonlocal requests
            requests += 1

            assert request.method == "GET"

            if requests == 1:
                return httpx.Response(
                    503,
                    json={"detail": "Unavailable"},
                )

            return httpx.Response(
                200,
                json=[
                    {
                        "id": "practice",
                        "kind": "practice",
                        "open": True,
                    }
                ],
            )

        async with TargetAPIClient(
            _settings(),
            transport=httpx.MockTransport(handler),
            retry_policy=RetryPolicy(base_delay_seconds=0),
        ) as client:
            scenarios = await client.list_scenarios()

        assert scenarios[0].id == "practice"
        assert requests == 2

    asyncio.run(run())


def test_read_only_client_does_not_retry_permanent_errors() -> None:
    """Ensure HTTP 422 is not retried."""

    async def run() -> None:
        """Count requests that produce a permanent failure."""
        requests = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            """Respond to every request with a validation error."""
            nonlocal requests
            requests += 1
            return httpx.Response(422)

        async with TargetAPIClient(
            _settings(),
            transport=httpx.MockTransport(handler),
            retry_policy=RetryPolicy(base_delay_seconds=0),
        ) as client:
            with pytest.raises(TargetAPIError) as error:
                await client.list_scenarios()

        assert error.value.status_code == 422
        assert requests == 1

    asyncio.run(run())


def test_read_only_client_dry_run_prevents_network() -> None:
    """Ensure dry-run mode blocks outgoing requests before transport access."""

    async def run() -> None:
        """Verify that a dry-run call cannot reach its mock transport."""
        requests = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            """Record a request that should never happen."""
            nonlocal requests
            requests += 1
            return httpx.Response(200, json=[])

        async with TargetAPIClient(
            _settings(dry_run=True),
            transport=httpx.MockTransport(handler),
        ) as client:
            with pytest.raises(SimulationScopeError):
                await client.list_scenarios()

        assert requests == 0

    asyncio.run(run())


def test_read_only_client_rejects_bad_session_identifiers() -> None:
    """Reject path traversal and URL-like identifiers before sending requests."""

    async def run() -> None:
        """Exercise invalid resource IDs."""
        async with TargetAPIClient(_settings()) as client:
            for bad_id in (
                "../sessions",
                "https://elsewhere.test",
                "",
                "a/b",
            ):
                with pytest.raises(SimulationScopeError):
                    await client.get_session(bad_id)

    asyncio.run(run())
