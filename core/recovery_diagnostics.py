"""Inspect session ownership and potentially interrupted observation cycles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from core.cycle_recovery import CycleRecoveryInspector, StaleObservationCycle
from storage.event_store import EventStore
from storage.observation_cycles import ObservationCycleRepository
from storage.session_lease import SessionLeaseRepository


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    """Represent a read-only recovery diagnostic report.

    Attributes:
        session_id: Identifier of the inspected session.
        lease_present: Whether a session lease currently exists.
        lease_acquired_at: Recorded lease acquisition timestamp, if any.
        stale_cycles: Potentially interrupted observation cycles.

    """

    session_id: str
    lease_present: bool
    lease_acquired_at: str | None
    stale_cycles: tuple[StaleObservationCycle, ...]


class RecoveryDiagnostics:
    """Inspect persisted execution state without modifying ownership."""

    def __init__(self, store: EventStore) -> None:
        """Initialize diagnostics using existing SQLite repositories.

        Args:
            store: Open SQLite-backed event store.

        """
        self._leases = SessionLeaseRepository(store)
        self._cycles = ObservationCycleRepository(store)
        self._inspector = CycleRecoveryInspector(store)

    def inspect(
        self,
        session_id: str,
        *,
        older_than: timedelta = timedelta(minutes=5),
        now: datetime | None = None,
    ) -> RecoveryReport:
        """Inspect a session lease and potentially stale observation cycles.

        Args:
            session_id: Identifier of the session to inspect.
            older_than: Minimum age for a running cycle to be flagged.
            now: Optional timezone-aware reference timestamp.

        Returns:
            Immutable recovery diagnostics for the session.

        Raises:
            ValueError: If an identifier or time parameter is invalid.

        """
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be nonempty.")

        lease = self._leases.get(session_id)

        stale_cycles = tuple(
            cycle
            for cycle in self._inspector.find_stale(
                older_than=older_than,
                now=now,
            )
            if cycle.session_id == session_id
        )

        return RecoveryReport(
            session_id=session_id,
            lease_present=lease is not None,
            lease_acquired_at=(lease.acquired_at if lease is not None else None),
            stale_cycles=stale_cycles,
        )
