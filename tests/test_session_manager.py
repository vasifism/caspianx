"""Test persistent session state and recovery using temporary SQLite files."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.session_manager import SessionManager, SessionRecoveryError
from core.state_machine import (
    ContactBudgetExceeded,
    InvalidStateTransition,
    SessionState,
)
from integrations.api_models import Session
from storage.event_store import EventStore
from storage.repositories import SessionRepository


def make_session(
    touches_used: int = 0,
    *,
    touch_budget: int = 30,
    scenario_id: str = "practice",
) -> Session:
    """Create a valid simulated session response.

    Args:
        touches_used: Confirmed number of contacts.
        touch_budget: Maximum permitted number of contacts.
        scenario_id: Scenario associated with the session.

    Returns:
        Validated Pydantic session model.

    """
    return Session(
        session_id="practice_001",
        scenario_id=scenario_id,
        touch_budget=touch_budget,
        touches_used=touches_used,
        status="active",
        story_time="2026-11-21T12:00:00+01:00",
    )


def test_new_session_is_persisted(tmp_path: Path) -> None:
    """Save a newly discovered session and its initial state."""
    with EventStore(tmp_path / "events.sqlite3") as store:
        manager = SessionManager(store)
        machine = manager.synchronize(make_session())

        assert machine.state is SessionState.INITIALIZED

        restored = manager.restore("practice_001")

        assert restored is not None
        assert restored.to_snapshot() == machine.to_snapshot()


def test_session_survives_process_restart(tmp_path: Path) -> None:
    """Restore the same lifecycle state after reopening SQLite."""
    path = tmp_path / "durable.sqlite3"

    with EventStore(path) as store:
        manager = SessionManager(store)
        machine = manager.synchronize(make_session(2))

        manager.transition(machine, SessionState.OBSERVING)
        manager.transition(machine, SessionState.ANALYZING)

        expected = machine.to_snapshot()

    with EventStore(path) as store:
        manager = SessionManager(store)
        restored = manager.restore("practice_001")

        assert restored is not None
        assert restored.to_snapshot() == expected
        assert restored.remaining_contacts == 28


def test_api_contact_counter_is_authoritative(
    tmp_path: Path,
) -> None:
    """Synchronize local contacts from the API without estimating usage."""
    with EventStore(tmp_path / "events.sqlite3") as store:
        manager = SessionManager(store)

        manager.synchronize(make_session(2))
        updated = manager.synchronize(make_session(5))

        assert updated.touches_used == 5
        assert updated.remaining_contacts == 25

        metadata = manager.get_metadata("practice_001")
        assert metadata is not None
        assert metadata["touches_used"] == 5


def test_decreasing_contact_count_is_rejected(
    tmp_path: Path,
) -> None:
    """Prevent stale API data from reducing contact consumption."""
    with EventStore(tmp_path / "events.sqlite3") as store:
        manager = SessionManager(store)

        manager.synchronize(make_session(5))

        with pytest.raises(ContactBudgetExceeded):
            manager.synchronize(make_session(3))

        restored = manager.restore("practice_001")
        assert restored is not None
        assert restored.touches_used == 5


def test_invalid_transition_does_not_modify_state(
    tmp_path: Path,
) -> None:
    """Keep in-memory and persisted states unchanged after rejection."""
    with EventStore(tmp_path / "events.sqlite3") as store:
        manager = SessionManager(store)
        machine = manager.synchronize(make_session())

        with pytest.raises(InvalidStateTransition):
            manager.transition(machine, SessionState.PERSISTING)

        restored = manager.restore("practice_001")
        assert restored is not None
        assert machine.state is SessionState.INITIALIZED
        assert restored.state is SessionState.INITIALIZED


def test_scenario_change_is_rejected(tmp_path: Path) -> None:
    """Prevent a stored session from changing its scenario."""
    with EventStore(tmp_path / "events.sqlite3") as store:
        manager = SessionManager(store)
        manager.synchronize(make_session())

        with pytest.raises(SessionRecoveryError):
            manager.synchronize(make_session(scenario_id="another_scenario"))


def test_inconsistent_snapshot_is_rejected(
    tmp_path: Path,
) -> None:
    """Reject metadata that disagrees with the stored state."""
    with EventStore(tmp_path / "events.sqlite3") as store:
        manager = SessionManager(store)
        manager.synchronize(make_session(2))

        repository = SessionRepository(
            session_model=store.models.session,
            state_model=store.models.agent_state,
        )
        repository.save_session(
            session_id="practice_001",
            scenario_id="practice",
            status="active",
            touch_budget=30,
            touches_used=9,
        )

        with pytest.raises(SessionRecoveryError):
            manager.restore("practice_001")
