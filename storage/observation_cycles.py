"""Persist individual observation cycles independently of API sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

from storage.event_store import EventStore


class CycleStatus(StrEnum):
    """Define terminal and active observation-cycle statuses."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ObservationCycleRepository:
    """Track observation attempts in SQLite for recovery and auditing."""

    def __init__(self, store: EventStore) -> None:
        """Initialize the repository and its database table.

        Args:
            store: Open Peewee-backed event store.

        """
        self._database = store.database
        self._database.execute_sql(
            """
            CREATE TABLE IF NOT EXISTS observation_cycles (
                cycle_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                status TEXT NOT NULL,
                event_count INTEGER,
                error_type TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT
            )
            """
        )

    def start(self, session_id: str) -> str:
        """Create a new observation-cycle record.

        Args:
            session_id: Identifier of the owning practice session.

        Returns:
            Unique observation-cycle identifier.

        Raises:
            ValueError: If the session identifier is invalid.

        """
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be nonempty.")

        cycle_id = uuid4().hex
        timestamp = datetime.now(timezone.utc).isoformat()

        with self._database.atomic():
            self._database.execute_sql(
                """
                INSERT INTO observation_cycles
                    (cycle_id, session_id, status, started_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    cycle_id,
                    session_id,
                    CycleStatus.RUNNING.value,
                    timestamp,
                ),
            )

        return cycle_id

    def finish(
        self,
        cycle_id: str,
        *,
        event_count: int | None = None,
        error_type: str | None = None,
    ) -> None:
        """Mark an active observation cycle as completed or failed.

        Args:
            cycle_id: Identifier returned by start().
            event_count: Number of events observed on success.
            error_type: Exception class name on failure.

        Raises:
            ValueError: If the result is invalid or cycle is not running.

        """
        if (event_count is None) == (error_type is None):
            raise ValueError("Provide exactly one of event_count or error_type.")

        if event_count is not None and (type(event_count) is not int or event_count < 0):
            raise ValueError("event_count must be nonnegative.")

        if error_type is not None and (not isinstance(error_type, str) or not error_type.strip()):
            raise ValueError("error_type must be nonempty.")

        status = CycleStatus.FAILED if error_type is not None else CycleStatus.COMPLETED

        timestamp = datetime.now(timezone.utc).isoformat()

        with self._database.atomic():
            cursor = self._database.execute_sql(
                """
                UPDATE observation_cycles
                SET status = ?,
                    event_count = ?,
                    error_type = ?,
                    finished_at = ?
                WHERE cycle_id = ? AND status = ?
                """,
                (
                    status.value,
                    event_count,
                    error_type,
                    timestamp,
                    cycle_id,
                    CycleStatus.RUNNING.value,
                ),
            )

            if cursor.rowcount != 1:
                raise ValueError("Observation cycle does not exist or is already finished.")

    def get(self, cycle_id: str) -> dict[str, object] | None:
        """Retrieve the stored status of an observation cycle.

        Args:
            cycle_id: Unique observation-cycle identifier.

        Returns:
            Cycle metadata, or None if the identifier is unknown.

        """
        cursor = self._database.execute_sql(
            """
            SELECT cycle_id, session_id, status, event_count,
                   error_type, started_at, finished_at
            FROM observation_cycles
            WHERE cycle_id = ?
            """,
            (cycle_id,),
        )

        row = cursor.fetchone()

        if row is None:
            return None

        columns = (
            "cycle_id",
            "session_id",
            "status",
            "event_count",
            "error_type",
            "started_at",
            "finished_at",
        )

        return dict(zip(columns, row, strict=True))
