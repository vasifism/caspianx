"""Verify durable observation-cycle tracking and terminal-state rules."""

from __future__ import annotations

from pathlib import Path

import pytest

from storage.event_store import EventStore
from storage.observation_cycles import ObservationCycleRepository


def test_completed_cycle(tmp_path: Path) -> None:
    """Store a completed observation cycle with its event count."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        repository = ObservationCycleRepository(store)

        cycle_id = repository.start("practice_001")
        repository.finish(cycle_id, event_count=0)

        record = repository.get(cycle_id)

        assert record is not None
        assert record["status"] == "completed"
        assert record["event_count"] == 0
        assert record["finished_at"] is not None


def test_failed_cycle(tmp_path: Path) -> None:
    """Record an error type without persisting sensitive error messages."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        repository = ObservationCycleRepository(store)

        cycle_id = repository.start("practice_001")
        repository.finish(cycle_id, error_type="TimeoutException")

        record = repository.get(cycle_id)

        assert record is not None
        assert record["status"] == "failed"
        assert record["error_type"] == "TimeoutException"


def test_cycle_cannot_finish_twice(tmp_path: Path) -> None:
    """Prevent overwriting the terminal outcome of an observation."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        repository = ObservationCycleRepository(store)

        cycle_id = repository.start("practice_001")
        repository.finish(cycle_id, event_count=1)

        with pytest.raises(ValueError):
            repository.finish(cycle_id, event_count=2)


def test_cycle_survives_restart(tmp_path: Path) -> None:
    """Restore a completed cycle from a reopened SQLite database."""
    path = tmp_path / "durable.sqlite3"

    with EventStore(path) as store:
        repository = ObservationCycleRepository(store)
        cycle_id = repository.start("practice_001")
        repository.finish(cycle_id, event_count=3)

    with EventStore(path) as store:
        repository = ObservationCycleRepository(store)
        record = repository.get(cycle_id)

        assert record is not None
        assert record["event_count"] == 3


def test_invalid_cycle_input(tmp_path: Path) -> None:
    """Reject invalid identifiers and ambiguous terminal outcomes."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        repository = ObservationCycleRepository(store)

        with pytest.raises(ValueError):
            repository.start("")

        cycle_id = repository.start("practice_001")

        with pytest.raises(ValueError):
            repository.finish(cycle_id)

        with pytest.raises(ValueError):
            repository.finish(
                cycle_id,
                event_count=1,
                error_type="RuntimeError",
            )
