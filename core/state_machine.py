"""Manage validated lifecycle transitions for simulation sessions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class SessionState(StrEnum):
    """Define the supported lifecycle states of a simulation session."""

    INITIALIZED = "initialized"
    OBSERVING = "observing"
    ANALYZING = "analyzing"
    PERSISTING = "persisting"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class InvalidStateTransition(ValueError):
    """Indicate an unsupported lifecycle transition."""


class ContactBudgetExceeded(ValueError):
    """Indicate an invalid or excessive contact count."""


_ALLOWED_TRANSITIONS: dict[SessionState, frozenset[SessionState]] = {
    SessionState.INITIALIZED: frozenset(
        {
            SessionState.OBSERVING,
            SessionState.FAILED,
            SessionState.STOPPED,
        }
    ),
    SessionState.OBSERVING: frozenset(
        {
            SessionState.ANALYZING,
            SessionState.COMPLETED,
            SessionState.RECOVERING,
            SessionState.STOPPED,
        }
    ),
    SessionState.ANALYZING: frozenset(
        {
            SessionState.PERSISTING,
            SessionState.RECOVERING,
            SessionState.STOPPED,
        }
    ),
    SessionState.PERSISTING: frozenset(
        {
            SessionState.OBSERVING,
            SessionState.COMPLETED,
            SessionState.RECOVERING,
            SessionState.STOPPED,
        }
    ),
    SessionState.RECOVERING: frozenset(
        {
            SessionState.OBSERVING,
            SessionState.FAILED,
            SessionState.STOPPED,
        }
    ),
    SessionState.COMPLETED: frozenset(),
    SessionState.FAILED: frozenset(),
    SessionState.STOPPED: frozenset(),
}


@dataclass(slots=True)
class SessionStateMachine:
    """Track session lifecycle and its authoritative contact budget.

    Attributes:
        session_id: Unique identifier assigned to the session.
        touch_limit: Maximum permitted contacts.
        touches_used: Contacts confirmed by the simulation API.
        state: Current lifecycle state.
        version: Number of successful state or budget updates.

    """

    session_id: str
    touch_limit: int
    touches_used: int = 0
    state: SessionState = SessionState.INITIALIZED
    version: int = 0

    def __post_init__(self) -> None:
        """Validate the initial session snapshot.

        Raises:
            ValueError: If the identifiers, counters, or state are invalid.

        """
        if not isinstance(self.session_id, str) or not self.session_id:
            raise ValueError("session_id must be a nonempty string.")

        if type(self.touch_limit) is not int or self.touch_limit < 1:
            raise ValueError("touch_limit must be a positive integer.")

        if type(self.touches_used) is not int:
            raise ValueError("touches_used must be an integer.")

        if not 0 <= self.touches_used <= self.touch_limit:
            raise ContactBudgetExceeded("Initial contact usage is outside the permitted budget.")

        if type(self.version) is not int or self.version < 0:
            raise ValueError("version must be a nonnegative integer.")

        if not isinstance(self.state, SessionState):
            raise ValueError("state must be a SessionState value.")

    @property
    def remaining_contacts(self) -> int:
        """Return the number of contacts remaining in the session."""
        return self.touch_limit - self.touches_used

    @property
    def is_terminal(self) -> bool:
        """Indicate whether the session can no longer transition."""
        return not _ALLOWED_TRANSITIONS[self.state]

    def can_transition(self, next_state: SessionState) -> bool:
        """Check whether a lifecycle transition is supported.

        Args:
            next_state: Proposed destination state.

        Returns:
            Whether the transition is allowed.

        """
        return next_state in _ALLOWED_TRANSITIONS[self.state]

    def transition(self, next_state: SessionState) -> None:
        """Move the session to a validated lifecycle state.

        Args:
            next_state: Proposed destination state.

        Raises:
            InvalidStateTransition: If the transition is forbidden.
            TypeError: If the destination is not a SessionState.

        """
        if not isinstance(next_state, SessionState):
            raise TypeError("next_state must be a SessionState.")

        if not self.can_transition(next_state):
            raise InvalidStateTransition(
                f"Cannot transition from {self.state.value} to {next_state.value}."
            )

        self.state = next_state
        self.version += 1

    def synchronize_contacts(self, reported_total: int) -> None:
        """Apply the contact count confirmed by the Target API.

        The API's total is authoritative. This method never estimates
        contact consumption from HTTP requests or local retry attempts.

        Args:
            reported_total: Total contacts confirmed by the API.

        Raises:
            ContactBudgetExceeded: If the total decreases or exceeds
                the permitted contact budget.
            TypeError: If the reported total is not an integer.

        """
        if type(reported_total) is not int:
            raise TypeError("reported_total must be an integer.")

        if reported_total < self.touches_used or reported_total > self.touch_limit:
            raise ContactBudgetExceeded("Reported contacts must be monotonic and within budget.")

        if reported_total != self.touches_used:
            self.touches_used = reported_total
            self.version += 1

    def to_snapshot(self) -> dict[str, Any]:
        """Produce a JSON-compatible snapshot for persistent storage.

        Returns:
            Session metadata suitable for the state repository.

        """
        return {
            "session_id": self.session_id,
            "touch_limit": self.touch_limit,
            "touches_used": self.touches_used,
            "state": self.state.value,
            "version": self.version,
        }

    @classmethod
    def from_snapshot(
        cls,
        snapshot: dict[str, Any],
    ) -> SessionStateMachine:
        """Restore a validated state machine from persisted metadata.

        Args:
            snapshot: Previously stored session snapshot.

        Returns:
            Restored session state machine.

        Raises:
            ValueError: If the snapshot contains invalid state data.
            KeyError: If required metadata is absent.

        """
        return cls(
            session_id=snapshot["session_id"],
            touch_limit=snapshot["touch_limit"],
            touches_used=snapshot["touches_used"],
            state=SessionState(snapshot["state"]),
            version=snapshot["version"],
        )
