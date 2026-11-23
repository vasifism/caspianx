"""Test persistence and recovery across interrupted observation attempts."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.observation_runner import ObservationRunner
from core.recording_session_reader import RecordingSessionReader
from evaluation.event_replay import EventReplayService
from llm.schemas import EventAnalysis
from storage.event_store import EventStore
from storage.observation_cache import ObservationCache
from storage.observation_cycles import ObservationCycleRepository


SESSION_ID = "synthetic_recovery_session"

EVENTS = [
    {"id": "event_001", "type": "message.sent"},
    {"id": "event_002", "type": "message.opened"},
]


class FailingObservationEngine:
    """Simulate an analysis failure after durable event recording."""

    def __init__(self, reader: RecordingSessionReader) -> None:
        """Configure the recording reader used by the simulated engine.

        Args:
            reader: Reader that persists events before returning them.

        """
        self._reader = reader

    async def observe_once(self, session_id: str) -> None:
        """Record received events and simulate a model failure.

        Args:
            session_id: Session being observed.

        Raises:
            TimeoutError: Always, after successfully recording events.

        """
        await self._reader.get_events(session_id)
        raise TimeoutError("Synthetic analysis timeout")


def make_analysis() -> EventAnalysis:
    """Create a deterministic analysis for recovery tests.

    Returns:
        Structured analysis of synthetic observed events.

    """
    return EventAnalysis(
        summary="Two synthetic events observed.",
        event_types=["message.sent", "message.opened"],
        has_reply=False,
        uncertainties=[],
        requires_review=False,
    )


def test_analysis_failure_preserves_events_and_cycle(
    tmp_path: Path,
) -> None:
    """Keep event metadata and failure status after an analysis error."""

    async def run() -> None:
        """Execute a simulated failing observation."""
        with EventStore(tmp_path / "recovery.sqlite3") as store:
            replay = EventReplayService(store)
            cycles = ObservationCycleRepository(store)

            api = SimpleNamespace(
                get_events=AsyncMock(return_value=EVENTS),
            )
            reader = RecordingSessionReader(api, replay)
            engine = FailingObservationEngine(reader)
            runner = ObservationRunner(engine, cycles)

            with pytest.raises(TimeoutError):
                await runner.run(SESSION_ID)

            history = replay.replay(SESSION_ID)
            assert history.total_events == 2

            cursor = store.database.execute_sql(
                """
                SELECT status, error_type
                FROM observation_cycles
                WHERE session_id = ?
                """,
                (SESSION_ID,),
            )
            assert cursor.fetchone() == ("failed", "TimeoutError")

    asyncio.run(run())


def test_repeated_fetch_after_failure_is_idempotent(
    tmp_path: Path,
) -> None:
    """Avoid duplicate records when a failed operation is retried."""

    async def run() -> None:
        """Record the same API event history twice."""
        with EventStore(tmp_path / "retry.sqlite3") as store:
            replay = EventReplayService(store)

            api = SimpleNamespace(
                get_events=AsyncMock(return_value=EVENTS),
            )
            reader = RecordingSessionReader(api, replay)

            await reader.get_events(SESSION_ID)
            await reader.get_events(SESSION_ID)

            assert reader.received_events == 4
            assert reader.new_events == 2
            assert replay.replay(SESSION_ID).total_events == 2

    asyncio.run(run())


def test_event_history_survives_interrupted_run(
    tmp_path: Path,
) -> None:
    """Recover durable event metadata after closing the initial store."""
    database_path = tmp_path / "interrupted.sqlite3"

    with EventStore(database_path) as store:
        replay = EventReplayService(store)
        assert replay.record(SESSION_ID, EVENTS) == 2

    with EventStore(database_path) as store:
        replay = EventReplayService(store)
        history = replay.replay(SESSION_ID)

        assert history.total_events == 2
        assert [event.event_id for event in history.events] == [
            "event_001",
            "event_002",
        ]
        assert replay.record(SESSION_ID, EVENTS) == 0


def test_analysis_cache_survives_store_restart(
    tmp_path: Path,
) -> None:
    """Recover structured analysis independently of process lifetime."""
    database_path = tmp_path / "analysis.sqlite3"

    fingerprint = ObservationCache.fingerprint(
        SESSION_ID,
        "synthetic-test-model",
        EVENTS,
    )

    with EventStore(database_path) as store:
        cache = ObservationCache(store)
        cache.save(fingerprint, make_analysis())

    with EventStore(database_path) as store:
        cache = ObservationCache(store)
        recovered = cache.get(fingerprint)

        assert recovered == make_analysis()
