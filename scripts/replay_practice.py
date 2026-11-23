"""Synchronize and replay sanitized events from a live practice session."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Mapping
from typing import Any

from config.settings import Settings
from evaluation.event_replay import EventReplayService
from integrations.target_api import TargetAPIClient
from storage.event_store import EventStore


SESSION_ID = "s_678d0c7e74"


def extract_events(response: Any) -> list[dict[str, Any]]:
    """Normalize supported API responses into event dictionaries.

    Args:
        response: Event collection returned by the Target API client.

    Returns:
        List of event dictionaries suitable for metadata validation.

    Raises:
        TypeError: If the API response has an unsupported structure.

    """
    if isinstance(response, Mapping):
        events = response.get("events")
    elif isinstance(response, (list, tuple)):
        events = response
    else:
        events = getattr(response, "events", None)

    if not isinstance(events, (list, tuple)):
        raise TypeError("Unsupported event collection response.")

    normalized = []

    for event in events:
        if isinstance(event, Mapping):
            normalized.append(dict(event))
        elif callable(getattr(event, "model_dump", None)):
            normalized.append(event.model_dump())
        else:
            raise TypeError("Unsupported event representation.")

    return normalized


async def main() -> int:
    """Synchronize practice events and verify persisted replay.

    Returns:
        Zero on successful synchronization, otherwise one.

    """
    settings = Settings()

    if settings.dry_run:
        print("Live API access is disabled in dry-run mode.")
        return 1

    print("CaspianX Live Event Replay")
    print(f"Session: {SESSION_ID}")
    print("Mode: read-only")
    print("Contacts sent: 0")

    try:
        async with TargetAPIClient(settings) as target:
            session = await target.get_session(SESSION_ID)

            if session.scenario_id != "practice":
                raise ValueError("Only practice sessions may be replayed.")

            response = await target.get_events(SESSION_ID)

        events = extract_events(response)

        with EventStore(settings.sqlite_path) as store:
            service = EventReplayService(store)

            newly_inserted = service.record(
                SESSION_ID,
                events,
            )

            replay = service.replay(SESSION_ID)

            print(f"API contacts used: {session.touches_used}")
            print(f"API events received: {len(events)}")
            print(f"New events persisted: {newly_inserted}")
            print(f"Replayed events: {replay.total_events}")

            for event in replay.events:
                print(f"[{event.position}] {event.event_id}: {event.event_type}")

        # Reopen SQLite to test persistence across store instances.
        with EventStore(settings.sqlite_path) as store:
            restored = EventReplayService(store).replay(SESSION_ID)

            if restored != replay:
                raise RuntimeError("Replayed history changed after reopening SQLite.")

        print("SQLite replay recovery: OK")
        print("Live event replay: OK")
        return 0

    except Exception as error:
        print(
            f"Live replay failed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
