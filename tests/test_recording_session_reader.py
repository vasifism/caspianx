"""Test event persistence before downstream observation."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.recording_session_reader import RecordingSessionReader
from evaluation.event_replay import EventReplayService
from storage.event_store import EventStore


def test_events_are_persisted_before_return(tmp_path: Path) -> None:
    """Record events while preserving the original API response."""

    async def run() -> None:
        """Execute and verify a recording operation."""
        with EventStore(tmp_path / "events.sqlite3") as store:
            replay = EventReplayService(store)
            response = [
                {"id": "e1", "type": "message.sent"},
                {"id": "e2", "type": "message.opened"},
            ]
            api = SimpleNamespace(
                get_events=AsyncMock(return_value=response),
            )

            reader = RecordingSessionReader(api, replay)
            returned = await reader.get_events("practice_001")

            assert returned is response
            assert reader.received_events == 2
            assert reader.new_events == 2
            assert replay.replay("practice_001").total_events == 2

    asyncio.run(run())


def test_duplicate_fetch_does_not_duplicate_storage(
    tmp_path: Path,
) -> None:
    """Avoid duplicate persistence across repeated API reads."""

    async def run() -> None:
        """Fetch an unchanged event list twice."""
        with EventStore(tmp_path / "events.sqlite3") as store:
            replay = EventReplayService(store)
            api = SimpleNamespace(
                get_events=AsyncMock(
                    return_value=[
                        {"id": "e1", "type": "message.sent"},
                    ]
                ),
            )
            reader = RecordingSessionReader(api, replay)

            await reader.get_events("practice_001")
            await reader.get_events("practice_001")

            assert reader.received_events == 2
            assert reader.new_events == 1
            assert replay.replay("practice_001").total_events == 1

    asyncio.run(run())


def test_session_metadata_is_forwarded(tmp_path: Path) -> None:
    """Return session metadata without changing its representation."""

    async def run() -> None:
        """Verify forwarding to the underlying API client."""
        with EventStore(tmp_path / "events.sqlite3") as store:
            session = SimpleNamespace(
                scenario_id="practice",
                touches_used=1,
            )
            api = SimpleNamespace(
                get_session=AsyncMock(return_value=session),
            )

            reader = RecordingSessionReader(
                api,
                EventReplayService(store),
            )

            result = await reader.get_session("practice_001")

            assert result is session
            api.get_session.assert_awaited_once_with("practice_001")

    asyncio.run(run())


def test_invalid_event_prevents_downstream_delivery(
    tmp_path: Path,
) -> None:
    """Reject malformed events without persisting a partial batch."""

    async def run() -> None:
        """Verify that malformed metadata blocks event delivery."""
        with EventStore(tmp_path / "events.sqlite3") as store:
            replay = EventReplayService(store)
            api = SimpleNamespace(
                get_events=AsyncMock(
                    return_value=[
                        {"id": "e1", "type": "message.sent"},
                        {"id": "", "type": "message.opened"},
                    ]
                ),
            )
            reader = RecordingSessionReader(api, replay)

            with pytest.raises(ValueError):
                await reader.get_events("practice_001")

            assert replay.replay("practice_001").total_events == 0
            assert reader.new_events == 0

    asyncio.run(run())
