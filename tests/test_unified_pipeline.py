"""Test durable event recording and cached analysis with synthetic data."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.recording_session_reader import RecordingSessionReader
from evaluation.event_replay import EventReplayService
from llm.schemas import EventAnalysis
from scripts.run_observation import CachedAnalyzer
from storage.event_store import EventStore
from storage.observation_cache import ObservationCache


def make_analysis(event_types: list[str]) -> EventAnalysis:
    """Create a deterministic structured analysis for integration tests.

    Args:
        event_types: Event types represented in the synthetic history.

    Returns:
        Valid structured event analysis.

    """
    return EventAnalysis(
        summary="Synthetic event analysis completed.",
        event_types=event_types,
        has_reply="message.reply" in event_types,
        uncertainties=[],
        requires_review=False,
    )


def test_new_events_are_recorded_before_analysis(
    tmp_path: Path,
) -> None:
    """Ensure event metadata is durable before analysis begins."""

    async def run() -> None:
        """Execute a synthetic observation with a storage assertion."""
        with EventStore(tmp_path / "pipeline.sqlite3") as store:
            replay = EventReplayService(store)
            cache = ObservationCache(store)

            events = [
                {
                    "id": "event_001",
                    "type": "message.opened",
                    "body": "PRIVATE_SYNTHETIC_CONTENT",
                },
                {
                    "id": "event_002",
                    "type": "message.reply",
                },
            ]

            api = SimpleNamespace(
                get_events=AsyncMock(return_value=events),
            )
            reader = RecordingSessionReader(api, replay)

            async def analyze(saved_events: list[dict]) -> EventAnalysis:
                """Verify persistence before returning a model result."""
                history = replay.replay("practice_001")

                assert history.total_events == 2
                assert history.events[0].event_id == "event_001"
                assert history.events[1].event_id == "event_002"

                assert "body" not in store.list_events("practice_001")[0].payload

                return make_analysis([event["type"] for event in saved_events])

            model = SimpleNamespace(
                analyze_events=AsyncMock(side_effect=analyze),
            )
            analyzer = CachedAnalyzer(
                analyzer=model,
                cache=cache,
                session_id="practice_001",
                model="synthetic-test-model",
            )

            fetched = await reader.get_events("practice_001")

            # Supply only whitelisted metadata to the analyzer.
            sanitized = [
                {
                    "id": event["id"],
                    "type": event["type"],
                }
                for event in fetched
            ]

            result = await analyzer.analyze_events(sanitized)

            assert reader.new_events == 2
            assert result.has_reply is True
            assert analyzer.cache_hits == 0
            model.analyze_events.assert_awaited_once()

    asyncio.run(run())


def test_unchanged_history_reuses_cached_analysis(
    tmp_path: Path,
) -> None:
    """Reuse cached analysis when the same event history is fetched."""

    async def run() -> None:
        """Fetch and analyze an unchanged synthetic event list twice."""
        with EventStore(tmp_path / "pipeline.sqlite3") as store:
            replay = EventReplayService(store)
            cache = ObservationCache(store)

            events = [
                {"id": "event_001", "type": "message.opened"},
            ]

            api = SimpleNamespace(
                get_events=AsyncMock(return_value=events),
            )
            reader = RecordingSessionReader(api, replay)

            model = SimpleNamespace(
                analyze_events=AsyncMock(return_value=make_analysis(["message.opened"])),
            )

            analyzer = CachedAnalyzer(
                analyzer=model,
                cache=cache,
                session_id="practice_001",
                model="synthetic-test-model",
            )

            first = await reader.get_events("practice_001")
            first_result = await analyzer.analyze_events(first)

            second = await reader.get_events("practice_001")
            second_result = await analyzer.analyze_events(second)

            assert first_result == second_result
            assert reader.received_events == 2
            assert reader.new_events == 1
            assert analyzer.cache_hits == 1
            assert model.analyze_events.await_count == 1

    asyncio.run(run())


def test_new_event_invalidates_cached_analysis(
    tmp_path: Path,
) -> None:
    """Request a new analysis when a previously unseen event appears."""

    async def run() -> None:
        """Compare cached analyses before and after an event arrives."""
        with EventStore(tmp_path / "pipeline.sqlite3") as store:
            replay = EventReplayService(store)
            cache = ObservationCache(store)

            initial = [
                {"id": "event_001", "type": "message.opened"},
            ]
            updated = [
                *initial,
                {"id": "event_002", "type": "message.reply"},
            ]

            api = SimpleNamespace(
                get_events=AsyncMock(side_effect=[initial, updated]),
            )
            reader = RecordingSessionReader(api, replay)

            model = SimpleNamespace(
                analyze_events=AsyncMock(
                    side_effect=[
                        make_analysis(["message.opened"]),
                        make_analysis(["message.opened", "message.reply"]),
                    ]
                ),
            )

            analyzer = CachedAnalyzer(
                analyzer=model,
                cache=cache,
                session_id="practice_001",
                model="synthetic-test-model",
            )

            first = await reader.get_events("practice_001")
            first_result = await analyzer.analyze_events(first)

            second = await reader.get_events("practice_001")
            second_result = await analyzer.analyze_events(second)

            assert first_result.has_reply is False
            assert second_result.has_reply is True

            assert reader.new_events == 2
            assert replay.replay("practice_001").total_events == 2
            assert analyzer.cache_hits == 0
            assert model.analyze_events.await_count == 2

    asyncio.run(run())


def test_invalid_event_batch_never_reaches_analyzer(
    tmp_path: Path,
) -> None:
    """Block analysis when an event batch cannot be validated."""

    async def run() -> None:
        """Verify that malformed input does not reach the model."""
        with EventStore(tmp_path / "pipeline.sqlite3") as store:
            replay = EventReplayService(store)

            api = SimpleNamespace(
                get_events=AsyncMock(
                    return_value=[
                        {"id": "event_001", "type": "message.sent"},
                        {"id": "", "type": "message.opened"},
                    ]
                ),
            )

            reader = RecordingSessionReader(api, replay)
            model = SimpleNamespace(
                analyze_events=AsyncMock(),
            )

            with pytest.raises(ValueError):
                fetched = await reader.get_events("practice_001")
                await model.analyze_events(fetched)

            assert replay.replay("practice_001").total_events == 0
            model.analyze_events.assert_not_awaited()

    asyncio.run(run())
