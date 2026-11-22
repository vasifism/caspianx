"""Verify event deduplication and durable replay using temporary databases."""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.event_replay import EventReplayService
from storage.event_store import EventStore


def test_new_events_are_recorded(tmp_path: Path) -> None:
    """Persist unique event metadata in the event store."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        service = EventReplayService(store)

        inserted = service.record(
            "practice_001",
            [
                {"id": "e1", "type": "message.opened"},
                {"id": "e2", "type": "message.reply"},
            ],
        )

        assert inserted == 2
        assert service.replay("practice_001").total_events == 2


def test_duplicate_events_are_ignored(tmp_path: Path) -> None:
    """Avoid inserting the same event twice within one session."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        service = EventReplayService(store)
        events = [{"id": "e1", "type": "message.opened"}]

        assert service.record("practice_001", events) == 1
        assert service.record("practice_001", events) == 0
        assert service.replay("practice_001").total_events == 1


def test_replay_preserves_event_order(tmp_path: Path) -> None:
    """Preserve insertion order during event-history reconstruction."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        service = EventReplayService(store)

        service.record(
            "practice_001",
            [
                {"id": "e3", "type": "message.sent"},
                {"id": "e1", "type": "message.opened"},
                {"id": "e2", "type": "message.reply"},
            ],
        )

        replay = service.replay("practice_001")

        assert [event.event_id for event in replay.events] == [
            "e3",
            "e1",
            "e2",
        ]

        assert [event.position for event in replay.events] == [
            0,
            1,
            2,
        ]


def test_replay_survives_restart(tmp_path: Path) -> None:
    """Recover event history after reopening the SQLite database."""
    path = tmp_path / "durable.sqlite3"

    with EventStore(path) as store:
        service = EventReplayService(store)
        service.record(
            "practice_001",
            [{"id": "e1", "type": "message.opened"}],
        )

    with EventStore(path) as store:
        service = EventReplayService(store)
        replay = service.replay("practice_001")

        assert replay.total_events == 1
        assert replay.events[0].event_id == "e1"


def test_sessions_have_independent_histories(tmp_path: Path) -> None:
    """Permit identical event IDs in separate simulation sessions."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        service = EventReplayService(store)

        event = [{"id": "e1", "type": "message.opened"}]

        service.record("practice_001", event)
        service.record("practice_002", event)

        assert service.replay("practice_001").total_events == 1
        assert service.replay("practice_002").total_events == 1


def test_sensitive_content_is_not_stored(tmp_path: Path) -> None:
    """Exclude message bodies and submitted values from saved events."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        service = EventReplayService(store)

        service.record(
            "practice_001",
            [
                {
                    "id": "e1",
                    "type": "page.submitted",
                    "body": "private-message-content",
                    "values": {
                        "password": "sensitive-test-value",
                    },
                }
            ],
        )

        stored = store.list_events("practice_001")
        payload = stored[0].payload

        assert "body" not in payload
        assert "values" not in payload
        assert payload["type"] == "page.submitted"


def test_invalid_event_identifiers(tmp_path: Path) -> None:
    """Reject events lacking an identifiable event ID or type."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        service = EventReplayService(store)

        with pytest.raises(ValueError):
            service.record(
                "practice_001",
                [{"id": "", "type": "message.opened"}],
            )

        with pytest.raises(ValueError):
            service.record(
                "practice_001",
                [{"id": "e1", "type": ""}],
            )

        with pytest.raises(ValueError):
            service.record(
                "",
                [{"id": "e1", "type": "message.opened"}],
            )
