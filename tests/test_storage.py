"""Integration tests for the Peewee-backed local persistence layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from storage.event_store import REDACTED, EventStore
from storage.repositories import SessionRepository


@pytest.fixture
def store(tmp_path: Path):
    """Provide a fresh local event store for every test.

    Args:
        tmp_path: Temporary directory supplied by pytest.

    Yields:
        The open event store instance.

    """
    with EventStore(tmp_path / "events.sqlite3") as instance:
        yield instance


def test_event_round_trip(store: EventStore) -> None:
    """Persist and recover an event with identical metadata."""
    assert store.append("s1", "e1", "reply", {"body": "hello"})
    assert store.count("s1") == 1
    assert store.list_events("s1")[0].payload["body"] == "hello"


def test_duplicate_event_is_idempotent(store: EventStore) -> None:
    """Prevent duplicate event records for the same session."""
    assert store.append("s1", "e1", "reply", {})
    assert not store.append("s1", "e1", "reply", {})
    assert store.count("s1") == 1


def test_event_ids_are_scoped_per_session(store: EventStore) -> None:
    """Allow separate sessions to use identical event identifiers."""
    assert store.append("s1", "e1", "reply", {})
    assert store.append("s2", "e1", "reply", {})
    assert store.count("s2") == 1


def test_events_keep_insertion_order(store: EventStore) -> None:
    """Replay events in their original insertion order."""
    for number in range(4):
        store.append("s1", f"e{number}", "reply", {"order": number})
    assert [event.payload["order"] for event in store.list_events("s1")] == list(range(4))


def test_form_values_are_not_persisted(store: EventStore) -> None:
    """Strip all filled form values from persisted events."""
    store.append(
        "s1",
        "e1",
        "page.submitted",
        {
            "type": "page.submitted",
            "fields": ["email"],
            "values": {"email": "private@example.test"},
        },
    )
    assert store.list_events("s1")[0].payload["values"] == REDACTED


def test_repository_upserts_metadata(store: EventStore) -> None:
    """Update existing session metadata instead of duplicating it."""
    repository = SessionRepository(store.models.session, store.models.agent_state)
    repository.save_session("s1", "practice", "active", 30, 1)
    repository.save_session("s1", "practice", "active", 30, 3)
    assert repository.get_session("s1")["touches_used"] == 3
    assert store.models.session.select().count() == 1


def test_repository_sanitizes_snapshot(store: EventStore) -> None:
    """Redact sensitive keys from saved agent snapshots."""
    repository = SessionRepository(store.models.session, store.models.agent_state)
    repository.save_state("s1", {"stage": "observe", "api_key": "secret"})
    assert repository.get_state("s1") == {"stage": "observe", "api_key": REDACTED}


def test_unknown_session_returns_none(store: EventStore) -> None:
    """Return None for unknown metadata and snapshots."""
    repository = SessionRepository(store.models.session, store.models.agent_state)
    assert repository.get_session("missing") is None
    assert repository.get_state("missing") is None


def test_database_survives_restart(tmp_path: Path) -> None:
    """Recover committed events after closing and reopening SQLite."""
    path = tmp_path / "durable.sqlite3"
    with EventStore(path) as first:
        first.append("s1", "e1", "reply", {"body": "saved"})
    with EventStore(path) as second:
        assert second.list_events("s1")[0].payload["body"] == "saved"


def test_invalid_identifiers_are_rejected(store: EventStore) -> None:
    """Reject missing identifiers before attempting insertion."""
    with pytest.raises(ValueError):
        store.append("s1", "", "reply", {})
