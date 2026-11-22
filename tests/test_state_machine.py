"""Verify state transitions, contact limits, and snapshot recovery."""

from __future__ import annotations

import pytest

from core.state_machine import (
    ContactBudgetExceeded,
    InvalidStateTransition,
    SessionState,
    SessionStateMachine,
)


def make_machine() -> SessionStateMachine:
    """Create a fresh practice session for isolated tests.

    Returns:
        Initialized session state machine.

    """
    return SessionStateMachine(
        session_id="practice_001",
        touch_limit=30,
    )


def test_initial_session_state() -> None:
    """Initialize a session with the correct remaining budget."""
    machine = make_machine()

    assert machine.state is SessionState.INITIALIZED
    assert machine.remaining_contacts == 30
    assert machine.version == 0
    assert not machine.is_terminal


def test_valid_lifecycle() -> None:
    """Complete a normal observation and persistence cycle."""
    machine = make_machine()

    machine.transition(SessionState.OBSERVING)
    machine.transition(SessionState.ANALYZING)
    machine.transition(SessionState.PERSISTING)
    machine.transition(SessionState.COMPLETED)

    assert machine.is_terminal
    assert machine.version == 4


def test_invalid_transition_is_rejected() -> None:
    """Prevent skipping required lifecycle stages."""
    machine = make_machine()

    with pytest.raises(InvalidStateTransition):
        machine.transition(SessionState.PERSISTING)

    assert machine.state is SessionState.INITIALIZED


def test_terminal_state_cannot_restart() -> None:
    """Reject attempts to reactivate a completed session."""
    machine = make_machine()

    machine.transition(SessionState.OBSERVING)
    machine.transition(SessionState.COMPLETED)

    with pytest.raises(InvalidStateTransition):
        machine.transition(SessionState.OBSERVING)


def test_recovery_transition() -> None:
    """Allow an interrupted session to return to observation."""
    machine = make_machine()

    machine.transition(SessionState.OBSERVING)
    machine.transition(SessionState.RECOVERING)
    machine.transition(SessionState.OBSERVING)

    assert machine.state is SessionState.OBSERVING


def test_contact_budget_is_authoritative() -> None:
    """Synchronize usage without counting local retry attempts."""
    machine = make_machine()

    machine.synchronize_contacts(4)

    assert machine.touches_used == 4
    assert machine.remaining_contacts == 26

    machine.synchronize_contacts(4)

    assert machine.version == 1


def test_contact_budget_rejects_invalid_totals() -> None:
    """Reject decreasing counts and budget overruns."""
    machine = make_machine()
    machine.synchronize_contacts(5)

    with pytest.raises(ContactBudgetExceeded):
        machine.synchronize_contacts(4)

    with pytest.raises(ContactBudgetExceeded):
        machine.synchronize_contacts(31)

    assert machine.touches_used == 5


def test_snapshot_round_trip() -> None:
    """Recover state and counters from JSON-compatible metadata."""
    machine = make_machine()
    machine.transition(SessionState.OBSERVING)
    machine.synchronize_contacts(3)

    snapshot = machine.to_snapshot()
    restored = SessionStateMachine.from_snapshot(snapshot)

    assert restored.to_snapshot() == snapshot
    assert restored.remaining_contacts == 27


def test_invalid_initial_snapshot() -> None:
    """Reject invalid identifiers and inconsistent contact budgets."""
    with pytest.raises(ValueError):
        SessionStateMachine(session_id="", touch_limit=30)

    with pytest.raises(ContactBudgetExceeded):
        SessionStateMachine(
            session_id="practice_001",
            touch_limit=10,
            touches_used=11,
        )


def test_failed_session_is_terminal() -> None:
    """Ensure unrecoverable failures cannot resume automatically."""
    machine = make_machine()

    machine.transition(SessionState.FAILED)

    assert machine.is_terminal

    with pytest.raises(InvalidStateTransition):
        machine.transition(SessionState.OBSERVING)
