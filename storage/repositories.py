"""Persist session metadata and sanitized agent state through Peewee."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from peewee import Model

from storage.event_store import sanitize_payload


class SessionRepository:
    """Store and retrieve session metadata and state snapshots."""

    def __init__(self, session_model: type[Model], state_model: type[Model]) -> None:
        """Bind the repository to the current database models.

        Args:
            session_model: Model for session metadata.
            state_model: Model for sanitized snapshots.

        """
        self.session_model = session_model
        self.state_model = state_model

    def save_session(
        self,
        session_id: str,
        scenario_id: str,
        status: str,
        touch_budget: int,
        touches_used: int,
        story_time: str | None = None,
    ) -> None:
        """Upsert validated session metadata.

        Args:
            session_id: Unique session identifier.
            scenario_id: Scenario identifier.
            status: Status returned by the simulation.
            touch_budget: Maximum contact count.
            touches_used: Confirmed number of consumed contacts.
            story_time: Last confirmed virtual timestamp, if any.

        Raises:
            ValueError: If identifiers or counters are invalid.

        """
        if not all(
            isinstance(item, str) and item.strip() for item in (session_id, scenario_id, status)
        ):
            raise ValueError("Session identifiers and status must be nonempty.")
        if not 0 <= touches_used <= touch_budget:
            raise ValueError("Invalid session touch counters.")

        values = {
            "scenario_id": scenario_id,
            "status": status,
            "touch_budget": touch_budget,
            "touches_used": touches_used,
            "story_time": story_time,
            "updated_at": datetime.now(timezone.utc),
        }
        with self.session_model._meta.database.atomic():
            (
                self.session_model.insert(session_id=session_id, **values)
                .on_conflict(
                    conflict_target=[self.session_model.session_id],
                    update=values,
                )
                .execute()
            )

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Return metadata for one session, or None if unknown.

        Args:
            session_id: Unique session identifier.

        Returns:
            Session data, if a matching record exists.

        """
        record = self.session_model.get_or_none(self.session_model.session_id == session_id)
        if record is None:
            return None
        return {
            "session_id": record.session_id,
            "scenario_id": record.scenario_id,
            "status": record.status,
            "touch_budget": record.touch_budget,
            "touches_used": record.touches_used,
            "story_time": record.story_time,
        }

    def save_state(self, session_id: str, state: Mapping[str, Any]) -> None:
        """Upsert an agent state snapshot after sanitization.

        Args:
            session_id: Owning session identifier.
            state: JSON-compatible snapshot.

        Raises:
            ValueError: If the session identifier is empty.

        """
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("Session ID cannot be empty.")
        serialized = json.dumps(sanitize_payload(state), sort_keys=True)
        values = {
            "state_json": serialized,
            "updated_at": datetime.now(timezone.utc),
        }
        with self.state_model._meta.database.atomic():
            (
                self.state_model.insert(session_id=session_id, **values)
                .on_conflict(
                    conflict_target=[self.state_model.session_id],
                    update=values,
                )
                .execute()
            )

    def get_state(self, session_id: str) -> dict[str, Any] | None:
        """Load the last sanitized snapshot for a session.

        Args:
            session_id: Owning session identifier.

        Returns:
            Deserialized snapshot, or None when absent.

        """
        record = self.state_model.get_or_none(self.state_model.session_id == session_id)
        return None if record is None else json.loads(record.state_json)
