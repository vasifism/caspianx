"""Verify read-only connectivity to the revel8 practice simulation API."""

from __future__ import annotations

import asyncio
import sys

from config.settings import Settings
from integrations.target_api import TargetAPIClient


async def main() -> int:
    """Check authorization and retrieve available simulation scenarios.

    Returns:
        Process exit code indicating whether verification succeeded.

    """
    settings = Settings()

    if settings.dry_run:
        print("Live connectivity is disabled. Set CASPIANX_DRY_RUN=false to run the smoke test.")
        return 1

    if not settings.team_key or not settings.team_key.get_secret_value():
        print("CASPIANX_TEAM_KEY is missing.")
        return 1

    print("CaspianX Practice API smoke test")
    print("Mode: read-only")
    print("Creating sessions: no")
    print("Sending contacts: no")

    try:
        async with TargetAPIClient(settings) as client:
            scenarios = await client.list_scenarios()

        print(f"Available scenarios: {len(scenarios)}")

        for scenario in scenarios:
            print(f"  - {scenario.id} (kind: {scenario.kind})")

    except Exception as error:
        print(
            f"Smoke test failed: {type(error).__name__}",
            file=sys.stderr,
        )
        return 1

    print("Practice API connectivity: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
