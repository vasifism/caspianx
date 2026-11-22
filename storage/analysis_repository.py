"""Persist sanitized simulation analyses using the existing Peewee database."""

from __future__ import annotations

from hashlib import sha256

from llm.schemas import EventAnalysis
from storage.event_store import EventStore


class AnalysisRepository:
    """Store structured observations without retaining sensitive event bodies."""

    def __init__(self, store: EventStore) -> None:
        """Initialize the repository and its SQLite table.

        Args:
            store: Existing Peewee-backed event store.

        """
        self._database = store.database
        self._database.execute_sql(
            """
            CREATE TABLE IF NOT EXISTS observation_analyses (
                analysis_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                analysis_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def save(
        self,
        session_id: str,
        analysis: EventAnalysis,
    ) -> str:
        """Persist a structured analysis idempotently.

        Args:
            session_id: Owning simulation session identifier.
            analysis: Sanitized, validated model output.

        Returns:
            Deterministic identifier of the stored analysis.

        Raises:
            ValueError: If the session identifier is empty.

        """
        if not session_id or not session_id.strip():
            raise ValueError("session_id must be nonempty.")

        serialized = analysis.model_dump_json()

        fingerprint = sha256(f"{session_id}:{serialized}".encode("utf-8")).hexdigest()

        with self._database.atomic():
            self._database.execute_sql(
                """
                INSERT OR IGNORE INTO observation_analyses
                    (analysis_id, session_id, analysis_json)
                VALUES (?, ?, ?)
                """,
                (fingerprint, session_id, serialized),
            )

        return fingerprint

    def count(self, session_id: str) -> int:
        """Count distinct analyses persisted for a session.

        Args:
            session_id: Owning simulation session identifier.

        Returns:
            Number of stored analyses.

        """
        cursor = self._database.execute_sql(
            """
            SELECT COUNT(*)
            FROM observation_analyses
            WHERE session_id = ?
            """,
            (session_id,),
        )

        return int(cursor.fetchone()[0])
