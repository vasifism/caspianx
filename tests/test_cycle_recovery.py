"""Test detection of potentially interrupted observation cycles."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.cycle_recovery import CycleRecoveryInspector
from storage.event_store import EventStore
from storage.observation_cycles import ObservationCycleRepository


REFERENCE_TIME = datetime(2026, 11, 21, 12, tzinfo=timezone.utc)


def set_started_at(
    store: EventStore,
    cycle_id: str,
    timestamp: datetime,
) -> None:
    """Assign a deterministic start timestamp to a test cycle.

    Args:
        store: Test database containing the observation record.
        cycle_id: Identifier of the observation cycle.
        timestamp: Timezone-aware timestamp to persist.

    """
    store.database.execute_sql(
        """
        UPDATE observation_cycles
        SET started_at = ?
        WHERE cycle_id = ?
        """,
        (timestamp.isoformat(), cycle_id),
    )


def test_stale_running_cycle_is_detected(tmp_path: Path) -> None:
    """Identify an unfinished cycle older than the threshold."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        repository = ObservationCycleRepository(store)
        inspector = CycleRecoveryInspector(store)

        cycle_id = repository.start("practice_001")

        set_started_at(
            store,
            cycle_id,
            REFERENCE_TIME - timedelta(minutes=10),
        )

        stale = inspector.find_stale(
            older_than=timedelta(minutes=5),
            now=REFERENCE_TIME,
        )

        assert len(stale) == 1
        assert stale[0].cycle_id == cycle_id
        assert stale[0].age_seconds == 600


def test_recent_cycle_is_not_stale(tmp_path: Path) -> None:
    """Exclude running cycles younger than the recovery threshold."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        repository = ObservationCycleRepository(store)
        inspector = CycleRecoveryInspector(store)

        cycle_id = repository.start("practice_001")

        set_started_at(
            store,
            cycle_id,
            REFERENCE_TIME - timedelta(minutes=2),
        )

        stale = inspector.find_stale(
            older_than=timedelta(minutes=5),
            now=REFERENCE_TIME,
        )

        assert stale == []


def test_completed_cycle_is_excluded(tmp_path: Path) -> None:
    """Never classify completed work as interrupted."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        repository = ObservationCycleRepository(store)
        inspector = CycleRecoveryInspector(store)

        cycle_id = repository.start("practice_001")

        set_started_at(
            store,
            cycle_id,
            REFERENCE_TIME - timedelta(hours=1),
        )

        repository.finish(cycle_id, event_count=0)

        assert inspector.find_stale(now=REFERENCE_TIME) == []


def test_inspection_does_not_modify_database(tmp_path: Path) -> None:
    """Preserve original cycle status when inspecting stale work."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        repository = ObservationCycleRepository(store)
        inspector = CycleRecoveryInspector(store)

        cycle_id = repository.start("practice_001")

        set_started_at(
            store,
            cycle_id,
            REFERENCE_TIME - timedelta(hours=1),
        )

        inspector.find_stale(now=REFERENCE_TIME)

        record = repository.get(cycle_id)

        assert record is not None
        assert record["status"] == "running"


def test_invalid_recovery_parameters(tmp_path: Path) -> None:
    """Reject nonpositive thresholds and naive reference timestamps."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        ObservationCycleRepository(store)
        inspector = CycleRecoveryInspector(store)

        with pytest.raises(ValueError):
            inspector.find_stale(
                older_than=timedelta(seconds=0),
            )

        with pytest.raises(ValueError):
            inspector.find_stale(
                now=datetime(2026, 11, 21, 12),
            )
