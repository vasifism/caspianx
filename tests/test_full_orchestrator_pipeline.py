"""Exercise the complete observation pipeline with synthetic events."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

from core.engine import CaspianXOrchestrator
from core.observation_runner import ObservationRunner
from core.recording_session_reader import RecordingSessionReader
from evaluation.event_replay import EventReplayService
from llm.schemas import EventAnalysis
from scripts.run_observation import CachedAnalyzer
from storage.analysis_repository import AnalysisRepository
from storage.event_store import EventStore
from storage.observation_cache import ObservationCache
from storage.observation_cycles import ObservationCycleRepository
from storage.session_lease import SessionLeaseRepository


SESSION_ID = "synthetic_full_pipeline"


class SyntheticEvent(dict):
    """Expose synthetic event metadata through mapping and object access."""

    def __getattr__(self, name: str) -> Any:
        """Return event fields using attribute-style access.

        Args:
            name: Requested event field.

        Returns:
            Value stored under the corresponding field.

        Raises:
            AttributeError: If the requested field does not exist.

        """
        try:
            return self[name]
        except KeyError as error:
            raise AttributeError(name) from error

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Return a dictionary representation of the synthetic event.

        Args:
            **kwargs: Optional serialization arguments, ignored here.

        Returns:
            Copy of the event dictionary.

        """
        return dict(self)


class SyntheticEventBatch(list):
    """Support list-style and envelope-style event access."""

    @property
    def events(self) -> SyntheticEventBatch:
        """Expose the event collection through an events attribute."""
        return self


def make_analysis() -> EventAnalysis:
    """Create a deterministic structured analysis of two events."""
    return EventAnalysis(
        summary="Two synthetic events were observed.",
        event_types=["message.opened", "message.reply"],
        has_reply=True,
        uncertainties=[],
        requires_review=False,
    )


def test_complete_pipeline_is_durable_and_idempotent(
    tmp_path: Path,
) -> None:
    """Verify recording, analysis caching, cycles, and lease release."""

    async def run() -> None:
        """Execute two observations against an unchanged event history."""
        database_path = tmp_path / "full_pipeline.sqlite3"

        events = SyntheticEventBatch(
            [
                SyntheticEvent(
                    id="event_001",
                    type="message.opened",
                ),
                SyntheticEvent(
                    id="event_002",
                    type="message.reply",
                ),
            ]
        )

        session = SimpleNamespace(
            id=SESSION_ID,
            session_id=SESSION_ID,
            scenario_id="practice",
            status="active",
            touch_budget=30,
            touches_used=1,
        )

        api = SimpleNamespace(
            get_session=AsyncMock(return_value=session),
            get_events=AsyncMock(return_value=events),
        )

        model = SimpleNamespace(
            analyze_events=AsyncMock(return_value=make_analysis()),
        )

        with EventStore(database_path) as store:
            replay = EventReplayService(store)
            cache = ObservationCache(store)
            analyses = AnalysisRepository(store)
            cycles = ObservationCycleRepository(store)
            leases = SessionLeaseRepository(store)

            reader = RecordingSessionReader(
                reader=api,
                replay=replay,
            )

            analyzer = CachedAnalyzer(
                analyzer=model,
                cache=cache,
                session_id=SESSION_ID,
                model="synthetic-test-model",
            )

            async def persist(
                session_id: str,
                analysis: EventAnalysis,
            ) -> None:
                """Persist validated analysis after durable event recording.

                Args:
                    session_id: Owning simulation session.
                    analysis: Structured analysis to persist.

                """
                assert replay.replay(session_id).total_events == 2
                analyses.save(session_id, analysis)

            engine = CaspianXOrchestrator(
                session_reader=reader,
                analyzer=analyzer,
                persist=persist,
            )

            runner = ObservationRunner(
                engine=engine,
                cycles=cycles,
                leases=leases,
            )

            first = await runner.run(SESSION_ID)
            second = await runner.run(SESSION_ID)

            assert first.result.event_count == 2
            assert second.result.event_count == 2

            assert first.result.analysis == make_analysis()
            assert second.result.analysis == make_analysis()

            assert reader.received_events == 4
            assert reader.new_events == 2

            assert replay.replay(SESSION_ID).total_events == 2
            assert analyses.count(SESSION_ID) == 1

            assert analyzer.cache_hits == 1
            assert model.analyze_events.await_count == 1

            assert cycles.get(first.cycle_id)["status"] == "completed"
            assert cycles.get(second.cycle_id)["status"] == "completed"

            assert leases.get(SESSION_ID) is None

        # Verify that the event history survives reopening SQLite.
        with EventStore(database_path) as store:
            recovered = EventReplayService(store).replay(SESSION_ID)

            assert recovered.total_events == 2
            assert [event.event_id for event in recovered.events] == [
                "event_001",
                "event_002",
            ]

            assert AnalysisRepository(store).count(SESSION_ID) == 1

    asyncio.run(run())
