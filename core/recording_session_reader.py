"""Persist sanitized API events before exposing them to the orchestrator."""

from __future__ import annotations

from typing import Any

from evaluation.event_replay import EventReplayService
from scripts.replay_practice import extract_events


class RecordingSessionReader:
    """Wrap a session reader with durable event recording."""

    def __init__(
        self,
        reader: Any,
        replay: EventReplayService,
    ) -> None:
        """Initialize the recording adapter.

        Args:
            reader: Existing Target API session reader.
            replay: Service for storing sanitized event metadata.

        """
        self._reader = reader
        self._replay = replay
        self.new_events = 0
        self.received_events = 0

    async def get_session(self, session_id: str) -> Any:
        """Retrieve session metadata without modifying it.

        Args:
            session_id: Identifier of the requested session.

        Returns:
            Original session response from the Target API.

        """
        return await self._reader.get_session(session_id)

    async def get_events(self, session_id: str) -> Any:
        """Fetch events and durably record them before returning.

        Args:
            session_id: Identifier of the requested session.

        Returns:
            Original API response, preserving the caller's contract.

        Raises:
            TypeError: If the event response has an unsupported structure.
            ValueError: If an event is missing required metadata.

        """
        response = await self._reader.get_events(session_id)
        events = extract_events(response)

        inserted = self._replay.record(session_id, events)

        self.received_events += len(events)
        self.new_events += inserted

        return response
