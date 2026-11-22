"""Module for tests test target api.py."""

import asyncio

import httpx
import pytest
from pydantic import SecretStr

from config.settings import Settings
from integrations.target_api import TargetAPIClient
from integrations.api_errors import SimulationScopeError


def test_dry_run_blocks_every_network_call():
    """Verify dry run blocks every network call."""
    settings = Settings(_env_file=None, dry_run=True, team_key=SecretStr("dummy"))

    async def run():
        """Execute the asynchronous test scenario."""
        async with TargetAPIClient(settings) as api:
            with pytest.raises(SimulationScopeError):
                await api.list_scenarios()

    asyncio.run(run())


def test_read_only_scenarios_with_mock_transport():
    """Verify read only scenarios with mock transport."""

    async def handler(request):
        """Return a synthetic HTTP response and verify the request."""
        assert request.url.host == "target-api.apps.01.cf.eu01.stackit.cloud"
        assert request.headers["authorization"] == "Bearer dummy"
        return httpx.Response(200, json=[{"id": "practice", "kind": "practice", "open": True}])

    settings = Settings(_env_file=None, dry_run=False, team_key=SecretStr("dummy"))

    async def run():
        """Execute the asynchronous test scenario."""
        async with TargetAPIClient(settings, transport=httpx.MockTransport(handler)) as api:
            scenarios = await api.list_scenarios()
            assert scenarios[0].id == "practice"

    asyncio.run(run())


def test_url_injection_in_session_id_is_blocked():
    """Verify url injection in session id is blocked."""
    settings = Settings(_env_file=None, dry_run=False, team_key=SecretStr("dummy"))

    async def run():
        """Execute the asynchronous test scenario."""
        async with TargetAPIClient(settings) as api:
            with pytest.raises(SimulationScopeError):
                await api.get_session("../../example")

    asyncio.run(run())
