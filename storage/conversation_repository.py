"""Durably record simulation conversations and idempotent outbound operations."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def utc_now() -> str:
    """Return the current timezone-aware UTC timestamp as an ISO string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PendingOperation:
    """Represent one irreversible or ambiguous outbound operation."""

    operation_id: str
    session_id: str
    conversation_id: str | None
    kind: str
    idempotency_key: str
    state: str


class ConversationRepository:
    """Use a separate SQLite ledger for contact and turn safety."""

    def __init__(self, path: Path) -> None:
        """Open a SQLite database and initialize the conversation tables."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path), timeout=20)
        self.connection.execute("PRAGMA busy_timeout=20000")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS cx_conversations (
                conversation_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cx_operations (
                operation_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                conversation_id TEXT,
                kind TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                state TEXT NOT NULL,
                request_json TEXT NOT NULL,
                response_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS cx_operations_session
                ON cx_operations(session_id, created_at);
            CREATE TABLE IF NOT EXISTS cx_turns (
                row_id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                direction TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def __enter__(self) -> ConversationRepository:
        """Return this repository as a context manager."""
        return self

    def __exit__(self, *args: object) -> None:
        """Close the local database after the context ends."""
        self.connection.close()

    def reserve(
        self,
        session_id: str,
        kind: str,
        payload: dict[str, object],
        conversation_id: str | None = None,
    ) -> PendingOperation:
        """Persist an outbound operation before making a network request.

        Do not retry an unknown-outcome operation automatically. Its stable
        idempotency key can be used for an explicitly controlled reconciliation.
        """
        if not session_id.strip() or kind not in {"start", "turn", "end"}:
            raise ValueError("Invalid operation identifiers")
        operation_id = uuid4().hex
        key = str(uuid4())
        now = utc_now()
        with self.connection:
            self.connection.execute(
                """INSERT INTO cx_operations
                (operation_id, session_id, conversation_id, kind,
                 idempotency_key, state, request_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
                (
                    operation_id,
                    session_id,
                    conversation_id,
                    kind,
                    key,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    now,
                    now,
                ),
            )
        return PendingOperation(operation_id, session_id, conversation_id, kind, key, "pending")

    @staticmethod
    def _sanitize_response(response: dict[str, object]) -> dict[str, object]:
        """Retain dialogue metadata while excluding event form submissions."""
        safe_fields = {
            "conversation_id",
            "status",
            "persona_says",
            "touches_used",
            "ended",
            "turns_used",
            "message_id",
        }
        sanitized = {key: value for key, value in response.items() if key in safe_fields}
        events = response.get("events")
        if isinstance(events, list):
            sanitized["events"] = [
                {
                    key: item[key]
                    for key in ("id", "type", "message_id", "conversation_id")
                    if key in item
                }
                for item in events
                if isinstance(item, dict)
            ]
        return sanitized

    def complete(self, operation_id: str, response: dict[str, object]) -> None:
        """Mark a pending operation acknowledged by the API."""
        with self.connection:
            cursor = self.connection.execute(
                """UPDATE cx_operations
                SET state='completed', response_json=?, updated_at=?
                WHERE operation_id=? AND state='pending'""",
                (
                    json.dumps(self._sanitize_response(response), ensure_ascii=False),
                    utc_now(),
                    operation_id,
                ),
            )
            if cursor.rowcount != 1:
                raise ValueError("Operation is missing or already finalized")

    def record_conversation(
        self, conversation_id: str, session_id: str, target_id: str, channel: str, status: str
    ) -> None:
        """Store the server-confirmed conversation identity and status."""
        now = utc_now()
        with self.connection:
            self.connection.execute(
                """INSERT INTO cx_conversations
                (conversation_id, session_id, target_id, channel, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                status=excluded.status, updated_at=excluded.updated_at""",
                (conversation_id, session_id, target_id, channel, status, now, now),
            )

    def update_status(self, conversation_id: str, status: str) -> None:
        """Update a previously persisted conversation status."""
        with self.connection:
            self.connection.execute(
                "UPDATE cx_conversations SET status=?, updated_at=? WHERE conversation_id=?",
                (status, utc_now(), conversation_id),
            )

    def record_line(self, conversation_id: str, direction: str, body: str) -> None:
        """Store a simulation-only transcript line without secret form values."""
        if direction not in {"persona", "agent"}:
            raise ValueError("Unsupported transcript direction")
        with self.connection:
            self.connection.execute(
                """INSERT INTO cx_turns(conversation_id, direction, body, created_at)
                VALUES (?, ?, ?, ?)""",
                (conversation_id, direction, body, utc_now()),
            )

    def history(self, conversation_id: str) -> list[dict[str, str]]:
        """Return recorded transcript lines in insertion order."""
        rows = self.connection.execute(
            """SELECT direction, body FROM cx_turns
            WHERE conversation_id=? ORDER BY row_id""",
            (conversation_id,),
        ).fetchall()
        return [{"direction": direction, "body": body} for direction, body in rows]

    def pending(self, session_id: str) -> list[PendingOperation]:
        """Find potentially uncertain operations for manual reconciliation."""
        rows = self.connection.execute(
            """SELECT operation_id, session_id, conversation_id, kind,
            idempotency_key, state FROM cx_operations
            WHERE session_id=? AND state='pending' ORDER BY created_at""",
            (session_id,),
        ).fetchall()
        return [PendingOperation(*row) for row in rows]

    def snapshot(self, session_id: str) -> dict[str, object]:
        """Return a compact, non-secret operational summary."""
        conversations = self.connection.execute(
            "SELECT COUNT(*) FROM cx_conversations WHERE session_id=?", (session_id,)
        ).fetchone()[0]
        turns = self.connection.execute(
            """SELECT COUNT(*) FROM cx_turns t JOIN cx_conversations c
            ON t.conversation_id=c.conversation_id WHERE c.session_id=?""",
            (session_id,),
        ).fetchone()[0]
        return {
            "session_id": session_id,
            "conversations": conversations,
            "transcript_lines": turns,
            "unresolved_operations": len(self.pending(session_id)),
        }
