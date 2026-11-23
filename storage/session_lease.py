"""Coordinate exclusive session execution across Python processes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from storage.event_store import EventStore


@dataclass(frozen=True, slots=True)
class SessionLease:
    """Represent ownership of one simulation session.

    Attributes:
        session_id: Identifier of the protected simulation session.
        owner_token: Unique token identifying the lease holder.
        acquired_at: Timestamp when ownership was acquired.

    """

    session_id: str
    owner_token: str
    acquired_at: str


class SessionLeaseRepository:
    """Provide durable, exclusive session ownership using SQLite.

    Leases do not expire automatically. This prevents an active
    process from losing ownership solely because an API call
    takes longer than expected.
    """

    def __init__(self, store: EventStore) -> None:
        """Initialize the lease repository.

        Args:
            store: Open SQLite-backed event store.

        """
        self._database = store.database

        self._database.execute_sql(
            """
            CREATE TABLE IF NOT EXISTS session_execution_leases (
                session_id TEXT PRIMARY KEY,
                owner_token TEXT NOT NULL,
                acquired_at TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def _validate_identifier(value: str, field: str) -> None:
        """Validate a nonempty identifier.

        Args:
            value: Identifier to validate.
            field: Field name used in error messages.

        Raises:
            ValueError: If the identifier is missing or invalid.

        """
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a nonempty string.")

    def acquire(self, session_id: str) -> str | None:
        """Attempt to acquire exclusive ownership of a session.

        Args:
            session_id: Identifier of the protected session.

        Returns:
            Unique owner token, or None when already locked.

        Raises:
            ValueError: If the session identifier is invalid.

        """
        self._validate_identifier(session_id, "session_id")

        owner_token = uuid4().hex
        acquired_at = datetime.now(timezone.utc).isoformat()

        with self._database.atomic():
            cursor = self._database.execute_sql(
                """
                INSERT OR IGNORE INTO session_execution_leases (
                    session_id,
                    owner_token,
                    acquired_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    session_id,
                    owner_token,
                    acquired_at,
                ),
            )

            if cursor.rowcount != 1:
                return None

        return owner_token

    def get(self, session_id: str) -> SessionLease | None:
        """Retrieve the current ownership record for a session.

        Args:
            session_id: Identifier of the protected session.

        Returns:
            Current lease, or None when the session is unlocked.

        """
        self._validate_identifier(session_id, "session_id")

        cursor = self._database.execute_sql(
            """
            SELECT session_id, owner_token, acquired_at
            FROM session_execution_leases
            WHERE session_id = ?
            """,
            (session_id,),
        )

        row = cursor.fetchone()

        if row is None:
            return None

        return SessionLease(
            session_id=row[0],
            owner_token=row[1],
            acquired_at=row[2],
        )

    def release(self, session_id: str, owner_token: str) -> bool:
        """Release a lease only when the supplied owner matches.

        Args:
            session_id: Identifier of the protected session.
            owner_token: Token returned by a successful acquisition.

        Returns:
            True if the lease was released, otherwise False.

        """
        self._validate_identifier(session_id, "session_id")
        self._validate_identifier(owner_token, "owner_token")

        with self._database.atomic():
            cursor = self._database.execute_sql(
                """
                DELETE FROM session_execution_leases
                WHERE session_id = ?
                  AND owner_token = ?
                """,
                (session_id, owner_token),
            )

            return cursor.rowcount == 1
