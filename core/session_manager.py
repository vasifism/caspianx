"""Persist, restore, and reconcile simulation session lifecycle state."""

from __future__ import annotations

from typing import Any

from core.state_machine import (
    ContactBudgetExceeded,
    SessionState,
    SessionStateMachine,
)
from integrations.api_models import Session
from storage.event_store import EventStore
from storage.repositories import SessionRepository


class SessionRecoveryError(RuntimeError):
    """Indicate inconsistent persisted session metadata."""


class SessionManager:
    """Coordinate authoritative session metadata and SQLite snapshots."""

    def __init__(self, store: EventStore) -> None:
        """Bind session management to an existing Peewee event store.

        Args:
            store: Open event store providing the database and ORM models.

        """
        self._store = store
        self._repository = SessionRepository(
            session_model=store.models.session,
            state_model=store.models.agent_state,
        )

    def restore(self, session_id: str) -> SessionStateMachine | None:
        """Restore a previously persisted session state.

        Args:
            session_id: Unique simulation session identifier.

        Returns:
            Restored state machine, or None if no snapshot exists.

        Raises:
            SessionRecoveryError: If persisted metadata is inconsistent.

        """
        metadata = self._repository.get_session(session_id)
        snapshot = self._repository.get_state(session_id)

        if metadata is None and snapshot is None:
            return None

        if metadata is None or snapshot is None:
            raise SessionRecoveryError("Session metadata and state snapshot are incomplete.")

        try:
            machine = SessionStateMachine.from_snapshot(snapshot)
        except (KeyError, TypeError, ValueError) as error:
            raise SessionRecoveryError("Stored session snapshot is invalid.") from error

        if machine.session_id != session_id:
            raise SessionRecoveryError("Stored snapshot belongs to another session.")

        if machine.touch_limit != metadata["touch_budget"]:
            raise SessionRecoveryError("Stored contact budgets do not match.")

        if machine.touches_used != metadata["touches_used"]:
            raise SessionRecoveryError("Stored contact counters do not match.")

        return machine

    def synchronize(
        self,
        session: Session,
    ) -> SessionStateMachine:
        """Reconcile persisted state with authoritative API metadata.

        A new session starts in INITIALIZED. An existing session retains
        its lifecycle state and receives only confirmed contact updates.

        Args:
            session: Session metadata returned by the simulation API.

        Returns:
            Newly created or restored session state machine.

        Raises:
            SessionRecoveryError: If the stored budget has changed.
            ContactBudgetExceeded: If the API counters are inconsistent.

        """
        machine = self.restore(session.session_id)

        if machine is None:
            machine = SessionStateMachine(
                session_id=session.session_id,
                touch_limit=session.touch_budget,
                touches_used=session.touches_used,
            )
        else:
            if machine.touch_limit != session.touch_budget:
                raise SessionRecoveryError("The authoritative session budget has changed.")

            machine.synchronize_contacts(session.touches_used)

        self.save(
            machine,
            scenario_id=session.scenario_id,
            status=session.status,
            story_time=session.story_time,
        )

        return machine

    def save(
        self,
        machine: SessionStateMachine,
        *,
        scenario_id: str,
        status: str,
        story_time: str | int | float | None = None,
    ) -> None:
        """Atomically persist session metadata and lifecycle state.

        Args:
            machine: Validated state machine to persist.
            scenario_id: Simulation scenario identifier.
            status: Session status reported by the API.
            story_time: Last confirmed simulation timestamp.

        Raises:
            ValueError: If required metadata is invalid.
            SessionRecoveryError: If the stored session identity differs.

        """
        existing = self._repository.get_session(machine.session_id)

        if existing is not None:
            if existing["scenario_id"] != scenario_id:
                raise SessionRecoveryError("Cannot change an existing session's scenario.")

            if existing["touch_budget"] != machine.touch_limit:
                raise SessionRecoveryError("Cannot change an existing session's contact budget.")

            if existing["touches_used"] > machine.touches_used:
                raise ContactBudgetExceeded("Cannot persist a decreasing contact count.")

        normalized_time = None if story_time is None else str(story_time)

        with self._store.database.atomic():
            self._repository.save_session(
                session_id=machine.session_id,
                scenario_id=scenario_id,
                status=status,
                touch_budget=machine.touch_limit,
                touches_used=machine.touches_used,
                story_time=normalized_time,
            )
            self._repository.save_state(
                machine.session_id,
                machine.to_snapshot(),
            )

    def transition(
        self,
        machine: SessionStateMachine,
        next_state: SessionState,
    ) -> None:
        """Persist a valid lifecycle transition.

        Args:
            machine: Session state machine to update.
            next_state: Destination state.

        Raises:
            SessionRecoveryError: If session metadata is absent.
            InvalidStateTransition: If the transition is not allowed.

        """
        metadata = self._repository.get_session(machine.session_id)

        if metadata is None:
            raise SessionRecoveryError("Synchronize the session before transitioning.")

        # Make changes on a copy, then persist before exposing them.
        updated = SessionStateMachine.from_snapshot(machine.to_snapshot())
        updated.transition(next_state)

        self.save(
            updated,
            scenario_id=metadata["scenario_id"],
            status=metadata["status"],
            story_time=metadata["story_time"],
        )

        machine.state = updated.state
        machine.version = updated.version

    def get_metadata(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve persisted API session metadata.

        Args:
            session_id: Unique simulation session identifier.

        Returns:
            Saved session metadata, or None if unknown.

        """
        return self._repository.get_session(session_id)
