"""Create one authorized practice session and persist its metadata."""

from __future__ import annotations

import asyncio
import sys

import httpx

from config.settings import Settings
from core.session_manager import SessionManager
from integrations.api_models import Session
from storage.event_store import EventStore


async def main() -> int:
    """Create and persist a single practice session.

    Returns:
        Zero when the session is created and stored successfully,
        otherwise a nonzero process exit code.

    """
    settings = Settings()

    if settings.dry_run:
        print("Live API access is disabled.")
        return 1

    if not settings.team_key:
        print("CASPIANX_TEAM_KEY is missing.")
        return 1

    key = settings.team_key.get_secret_value()

    if not key:
        print("CASPIANX_TEAM_KEY is empty.")
        return 1

    print("Creating one revel8 PRACTICE session...")

    try:
        async with httpx.AsyncClient(
            base_url=settings.target_api_base_url.rstrip("/") + "/",
            timeout=settings.http_timeout_seconds,
            follow_redirects=False,
        ) as client:
            response = await client.post(
                "sessions",
                headers={"Authorization": f"Bearer {key}"},
                json={"scenario_id": "practice"},
            )
            response.raise_for_status()

            session = Session.model_validate(response.json())

        if session.scenario_id != "practice":
            raise ValueError("Unexpected scenario returned by API.")

        with EventStore(settings.sqlite_path) as store:
            manager = SessionManager(store)
            machine = manager.synchronize(session)

        print("Practice session created successfully.")
        print(f"Session ID: {session.session_id}")
        print(f"Scenario: {session.scenario_id}")
        print(f"Status: {session.status}")
        print(f"Contact budget: {session.touch_budget}")
        print(f"Contacts used: {machine.touches_used}")
        print(f"State: {machine.state.value}")
        print("SQLite persistence: OK")

        return 0

    except (httpx.HTTPError, ValueError, OSError) as error:
        print(
            f"Practice creation failed: {type(error).__name__}",
            file=sys.stderr,
        )
        print(
            "Do not automatically retry: the session may have been created before the failure.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
11
