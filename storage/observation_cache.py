"""Cache structured analyses by observable event history and model version."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from llm.schemas import EventAnalysis
from storage.event_store import EventStore


class ObservationCache:
    """Store and retrieve analyses of unchanged event histories."""

    def __init__(self, store: EventStore) -> None:
        """Initialize the cache table in an existing SQLite database.

        Args:
            store: Open Peewee-backed event store.

        """
        self._database = store.database
        self._database.execute_sql(
            """
            CREATE TABLE IF NOT EXISTS observation_cache (
                fingerprint TEXT PRIMARY KEY,
                analysis_json TEXT NOT NULL
            )
            """
        )

    @staticmethod
    def fingerprint(
        session_id: str,
        model: str,
        events: list[Mapping[str, Any]],
        *,
        analysis_version: str = "v1",
    ) -> str:
        """Calculate a deterministic key for one observable history.

        Args:
            session_id: Owning simulation session.
            model: OpenAI model identifier.
            events: Sanitized event metadata, in API response order.
            analysis_version: Version of the analysis instructions.

        Returns:
            SHA-256 fingerprint of the analysis inputs.

        Raises:
            ValueError: If required identifiers are empty.

        """
        if not session_id.strip() or not model.strip():
            raise ValueError("Session ID and model must be nonempty.")

        metadata = [
            {
                "id": event.get("id"),
                "type": event.get("type"),
            }
            for event in events
        ]

        payload = json.dumps(
            {
                "session_id": session_id,
                "model": model,
                "analysis_version": analysis_version,
                "events": metadata,
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, fingerprint: str) -> EventAnalysis | None:
        """Read a previously stored structured analysis.

        Args:
            fingerprint: Deterministic analysis cache key.

        Returns:
            Validated cached analysis, or None when absent.

        """
        cursor = self._database.execute_sql(
            """
            SELECT analysis_json
            FROM observation_cache
            WHERE fingerprint = ?
            """,
            (fingerprint,),
        )

        row = cursor.fetchone()
        if row is None:
            return None

        return EventAnalysis.model_validate_json(row[0])

    def save(
        self,
        fingerprint: str,
        analysis: EventAnalysis,
    ) -> None:
        """Save an analysis while preserving any existing cached value.

        Args:
            fingerprint: Deterministic analysis cache key.
            analysis: Validated structured result.

        """
        with self._database.atomic():
            self._database.execute_sql(
                """
                INSERT OR IGNORE INTO observation_cache
                    (fingerprint, analysis_json)
                VALUES (?, ?)
                """,
                (
                    fingerprint,
                    analysis.model_dump_json(),
                ),
            )
