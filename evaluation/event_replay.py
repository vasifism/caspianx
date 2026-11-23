"""Record and replay sanitized simulation events without duplication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from storage.event_store import EventStore


@dataclass(frozen=True, slots=True)
class ReplayEvent:
    """Represent a sanitized event in a reconstructed session history.

    Attributes:
        event_id: Unique event identifier assigned by the API.
        event_type: Observed simulation event type.
        position: Zero-based position in the replay.

    """

    event_id: str
    event_type: str
    position: int


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """Summarize a reconstructed session event history.

    Attributes:
        session_id: Identifier of the replayed session.
        events: Recorded events in their original insertion order.
        total_events: Number of events in the replay.

    """

    session_id: str
    events: tuple[ReplayEvent, ...]
    total_events: int


class EventReplayService:
    """Persist unique events and reconstruct their observable timeline."""

    def __init__(self, store: EventStore) -> None:
        """Bind the replay service to an existing event store.

        Args:
            store: Open Peewee-backed event store.

        """
        self._store = store

    def record(
        self,
        session_id: str,
        events: list[Mapping[str, Any]],
    ) -> int:
        """Persist new event metadata without creating duplicates.

        Args:
            session_id: Identifier of the owning simulation session.
            events: Events received from the Target API.

        Returns:
            Number of newly inserted events.

        Raises:
            ValueError: If session or event identifiers are invalid.

        """
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be nonempty.")

        validated_events = []

        for event in events:
            event_id = event.get("id")
            event_type = event.get("type")

            if not isinstance(event_id, str) or not event_id.strip():
                raise ValueError("Every event must have a valid ID.")

            if not isinstance(event_type, str) or not event_type.strip():
                raise ValueError("Every event must have a valid type.")

            validated_events.append((event_id, event_type))

        inserted = 0

        with self._store.database.atomic():
            for event_id, event_type in validated_events:
                sanitized = {
                    "id": event_id,
                    "type": event_type,
                }

                was_inserted = self._store.append(
                    session_id,
                    event_id,
                    event_type,
                    sanitized,
                )

                if was_inserted:
                    inserted += 1

        return inserted

    def replay(self, session_id: str) -> ReplayResult:
        """Reconstruct a session timeline from persisted events.

        Args:
            session_id: Identifier of the session to replay.

        Returns:
            Ordered, sanitized event history.

        Raises:
            ValueError: If the session identifier is invalid.

        """
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be nonempty.")

        stored_events = self._store.list_events(session_id)

        reconstructed = [
            ReplayEvent(
                event_id=event.event_id,
                event_type=event.event_type,
                position=position,
            )
            for position, event in enumerate(stored_events)
        ]

        return ReplayResult(
            session_id=session_id,
            events=tuple(reconstructed),
            total_events=len(reconstructed),
        )
