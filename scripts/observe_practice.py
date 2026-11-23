"""Inspect an existing practice session without consuming contacts."""

from __future__ import annotations

import asyncio
import sys

from config.settings import Settings
from core.session_manager import SessionManager
from integrations.target_api import TargetAPIClient
from storage.event_store import EventStore


SESSION_ID = "s_678d0c7e74"


async def main() -> int:
    """Read practice session metadata and synchronize local storage.

    Returns:
        Zero after successful inspection, otherwise one.

    """
    settings = Settings()

    if settings.dry_run:
        print("Live API access is disabled.")
        return 1

    try:
        async with TargetAPIClient(settings) as client:
            session = await client.get_session(SESSION_ID)

            if session.scenario_id != "practice":
                raise ValueError("Only practice sessions are permitted.")

            events_response = await client.get_events(SESSION_ID)

        with EventStore(settings.sqlite_path) as store:
            manager = SessionManager(store)
            machine = manager.synchronize(session)

            restored = manager.restore(SESSION_ID)

            if restored is None:
                raise RuntimeError("SQLite session recovery failed.")

            if restored.to_snapshot() != machine.to_snapshot():
                raise RuntimeError("Restored session does not match the saved state.")

        print("CaspianX Live Practice Observation")
        print(f"Session: {session.session_id}")
        print(f"Scenario: {session.scenario_id}")
        print(f"Status: {session.status}")
        print(f"Contacts used: {session.touches_used}")
        print(f"Contacts remaining: {machine.remaining_contacts}")
        print(f"Events observed: {len(events_response.events)}")
        print(f"Lifecycle state: {machine.state.value}")
        print("SQLite recovery: OK")
        print("Read-only observation: OK")

        return 0

    except Exception as error:
        print(
            f"Observation failed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
