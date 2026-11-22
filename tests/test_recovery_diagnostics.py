"""Test non-destructive inspection of persisted session execution state."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.recovery_diagnostics import RecoveryDiagnostics
from storage.event_store import EventStore
from storage.observation_cycles import ObservationCycleRepository
from storage.session_lease import SessionLeaseRepository


SESSION_ID = "practice_001"
REFERENCE_TIME = datetime(2026, 11, 21, 12, tzinfo=timezone.utc)


def make_old_cycle(
    store: EventStore,
    *,
    session_id: str = SESSION_ID,
) -> str:
    """Create an unfinished cycle with a deterministic old timestamp.

    Args:
        store: Open test database.
        session_id: Session owning the synthetic cycle.

    Returns:
        Identifier of the created cycle.

    """
    repository = ObservationCycleRepository(store)
    cycle_id = repository.start(session_id)

    started_at = REFERENCE_TIME - timedelta(minutes=15)

    store.database.execute_sql(
        """
        UPDATE observation_cycles
        SET started_at = ?
        WHERE cycle_id = ?
        """,
        (started_at.isoformat(), cycle_id),
    )

    return cycle_id


def test_clean_session_has_no_recovery_warnings(tmp_path: Path) -> None:
    """Report no lease or stale cycles for an untouched session."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        diagnostics = RecoveryDiagnostics(store)

        report = diagnostics.inspect(
            SESSION_ID,
            now=REFERENCE_TIME,
        )

        assert report.lease_present is False
        assert report.lease_acquired_at is None
        assert report.stale_cycles == ()


def test_existing_lease_is_detected(tmp_path: Path) -> None:
    """Detect a lease without revealing its owner token."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        leases = SessionLeaseRepository(store)
        token = leases.acquire(SESSION_ID)

        assert token is not None

        report = RecoveryDiagnostics(store).inspect(
            SESSION_ID,
            now=REFERENCE_TIME,
        )

        assert report.lease_present is True
        assert report.lease_acquired_at is not None
        assert token not in repr(report)


def test_old_running_cycle_is_reported(tmp_path: Path) -> None:
    """Identify an old unfinished observation cycle."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        cycle_id = make_old_cycle(store)

        report = RecoveryDiagnostics(store).inspect(
            SESSION_ID,
            older_than=timedelta(minutes=5),
            now=REFERENCE_TIME,
        )

        assert len(report.stale_cycles) == 1
        assert report.stale_cycles[0].cycle_id == cycle_id
        assert report.stale_cycles[0].age_seconds == 900


def test_completed_cycle_is_not_reported(tmp_path: Path) -> None:
    """Exclude completed observation cycles from stale diagnostics."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        cycles = ObservationCycleRepository(store)
        cycle_id = make_old_cycle(store)

        cycles.finish(cycle_id, event_count=2)

        report = RecoveryDiagnostics(store).inspect(
            SESSION_ID,
            now=REFERENCE_TIME,
        )

        assert report.stale_cycles == ()


def test_inspection_does_not_modify_execution_state(
    tmp_path: Path,
) -> None:
    """Preserve lease ownership and running-cycle status."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        leases = SessionLeaseRepository(store)
        cycles = ObservationCycleRepository(store)

        token = leases.acquire(SESSION_ID)
        cycle_id = make_old_cycle(store)

        report = RecoveryDiagnostics(store).inspect(
            SESSION_ID,
            now=REFERENCE_TIME,
        )

        assert report.lease_present is True
        assert len(report.stale_cycles) == 1
        assert leases.get(SESSION_ID).owner_token == token
        assert cycles.get(cycle_id)["status"] == "running"


def test_other_sessions_are_excluded(tmp_path: Path) -> None:
    """Report only unfinished cycles belonging to the requested session."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        make_old_cycle(store, session_id="practice_002")

        report = RecoveryDiagnostics(store).inspect(
            SESSION_ID,
            now=REFERENCE_TIME,
        )

        assert report.stale_cycles == ()


def test_invalid_session_is_rejected(tmp_path: Path) -> None:
    """Reject empty identifiers before inspecting database state."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        diagnostics = RecoveryDiagnostics(store)

        with pytest.raises(ValueError):
            diagnostics.inspect("")
