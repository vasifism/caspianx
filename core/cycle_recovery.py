"""Identify potentially interrupted observation cycles without mutating them."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from storage.event_store import EventStore


@dataclass(frozen=True, slots=True)
class StaleObservationCycle:
    """Describe an observation cycle that may have been interrupted.

    Attributes:
        cycle_id: Unique identifier of the observation cycle.
        session_id: Identifier of the owning simulation session.
        started_at: UTC timestamp when the cycle began.
        age_seconds: Time elapsed since the cycle started.

    """

    cycle_id: str
    session_id: str
    started_at: datetime
    age_seconds: float


class CycleRecoveryInspector:
    """Find unfinished observation cycles requiring recovery checks.

    A long-running cycle is not necessarily abandoned. This component
    performs inspection only and never changes a cycle's status.
    """

    def __init__(self, store: EventStore) -> None:
        """Bind the inspector to an existing SQLite event store.

        Args:
            store: Open Peewee-backed event store.

        """
        self._database = store.database

    def find_stale(
        self,
        *,
        older_than: timedelta = timedelta(minutes=5),
        now: datetime | None = None,
    ) -> list[StaleObservationCycle]:
        """Find running cycles older than the configured threshold.

        Args:
            older_than: Minimum age required to consider a cycle stale.
            now: Optional timezone-aware reference timestamp.

        Returns:
            Potentially interrupted cycles sorted by start time.

        Raises:
            ValueError: If the threshold or reference time is invalid.

        """
        if older_than <= timedelta(0):
            raise ValueError("older_than must be positive.")

        reference_time = now or datetime.now(timezone.utc)

        if reference_time.tzinfo is None or reference_time.utcoffset() is None:
            raise ValueError("now must be timezone-aware.")

        reference_time = reference_time.astimezone(timezone.utc)
        cutoff = reference_time - older_than

        cursor = self._database.execute_sql(
            """
            SELECT cycle_id, session_id, started_at
            FROM observation_cycles
            WHERE status = ?
            ORDER BY started_at ASC
            """,
            ("running",),
        )

        stale_cycles: list[StaleObservationCycle] = []

        for cycle_id, session_id, timestamp in cursor.fetchall():
            started_at = datetime.fromisoformat(timestamp)

            if started_at.tzinfo is None or started_at.utcoffset() is None:
                raise ValueError("Stored observation timestamp must include a timezone.")

            started_at = started_at.astimezone(timezone.utc)

            if started_at > cutoff:
                continue

            stale_cycles.append(
                StaleObservationCycle(
                    cycle_id=cycle_id,
                    session_id=session_id,
                    started_at=started_at,
                    age_seconds=(reference_time - started_at).total_seconds(),
                )
            )

        return stale_cycles
