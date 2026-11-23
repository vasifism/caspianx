"""Demonstrate durable event replay without live API requests."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from evaluation.event_replay import EventReplayService
from storage.event_store import EventStore


SESSION_ID = "demo_practice_session"

DEMO_EVENTS = [
    {
        "id": "demo_event_001",
        "type": "message.sent",
        "body": "PRIVATE_DEMO_MESSAGE",
    },
    {
        "id": "demo_event_002",
        "type": "message.opened",
    },
    {
        "id": "demo_event_003",
        "type": "message.reply",
        "body": "PRIVATE_DEMO_REPLY",
    },
]


def run_demo(database_path: Path) -> None:
    """Demonstrate insertion, deduplication, and recovery.

    Args:
        database_path: Temporary SQLite database location.

    Raises:
        AssertionError: If a replay invariant is violated.

    """
    print("CaspianX Offline Replay Demonstration")
    print("Mode: synthetic events only")
    print("Live API calls: 0")
    print("OpenAI calls: 0")

    with EventStore(database_path) as store:
        service = EventReplayService(store)

        first_insert = service.record(
            SESSION_ID,
            DEMO_EVENTS,
        )

        second_insert = service.record(
            SESSION_ID,
            DEMO_EVENTS,
        )

        assert first_insert == 3
        assert second_insert == 0

        print(f"First insertion: {first_insert}")
        print(f"Duplicate insertion: {second_insert}")

    with EventStore(database_path) as store:
        service = EventReplayService(store)
        replay = service.replay(SESSION_ID)

        assert replay.total_events == 3
        assert [event.event_id for event in replay.events] == [
            "demo_event_001",
            "demo_event_002",
            "demo_event_003",
        ]

        stored_events = store.list_events(SESSION_ID)

        for event in stored_events:
            assert "body" not in event.payload
            assert "values" not in event.payload

        print(f"Recovered events: {replay.total_events}")

        for event in replay.events:
            print(f"[{event.position}] {event.event_id}: {event.event_type}")

    print("Deduplication: OK")
    print("Event ordering: OK")
    print("Sensitive content filtering: OK")
    print("SQLite recovery: OK")
    print("Offline Replay Demonstration: PASSED")


def main() -> None:
    """Run the replay demonstration in an isolated temporary database."""
    with TemporaryDirectory(prefix="caspianx_replay_") as directory:
        run_demo(Path(directory) / "demo.sqlite3")


if __name__ == "__main__":
    main()
