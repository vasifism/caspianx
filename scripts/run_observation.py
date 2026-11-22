"""Run one cached, read-only CaspianX observation using live API services."""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Mapping
from typing import Any

from config.settings import Settings
from core.engine import CaspianXOrchestrator
from core.observation_runner import ObservationRunner
from core.session_manager import SessionManager
from integrations.target_api import TargetAPIClient
from llm.openai_client import OpenAIClient
from llm.schemas import EventAnalysis
from storage.analysis_repository import AnalysisRepository
from storage.event_store import EventStore
from storage.observation_cache import ObservationCache
from storage.observation_cycles import ObservationCycleRepository
from core.recording_session_reader import RecordingSessionReader
from evaluation.event_replay import EventReplayService
from storage.session_lease import SessionLeaseRepository


SESSION_ID = "s_678d0c7e74"


class CachedAnalyzer:
    """Reuse structured analyses for unchanged simulation event histories."""

    def __init__(
        self,
        *,
        analyzer: OpenAIClient,
        cache: ObservationCache,
        session_id: str,
        model: str,
    ) -> None:
        """Initialize the cache-aware analysis adapter.

        Args:
            analyzer: OpenAI client used for uncached analyses.
            cache: Persistent SQLite-backed analysis cache.
            session_id: Identifier of the observed practice session.
            model: Configured OpenAI model identifier.

        """
        self._analyzer = analyzer
        self._cache = cache
        self._session_id = session_id
        self._model = model
        self.cache_hits = 0

    async def analyze_events(
        self,
        events: list[Mapping[str, Any]],
    ) -> EventAnalysis:
        """Return a cached analysis or request a new one.

        Args:
            events: Sanitized event metadata supplied by the orchestrator.

        Returns:
            Validated structured analysis of the observed events.

        """
        fingerprint = self._cache.fingerprint(
            self._session_id,
            self._model,
            events,
        )

        cached = self._cache.get(fingerprint)

        if cached is not None:
            self.cache_hits += 1
            return cached

        analysis = await self._analyzer.analyze_events(events)
        self._cache.save(fingerprint, analysis)

        return analysis


async def main() -> int:
    """Observe a practice session and persist its structured analysis.

    Returns:
        Zero on successful observation, otherwise one.

    """
    settings = Settings()

    if settings.dry_run:
        print("Target API is disabled in dry-run mode.")
        return 1

    if (
        not settings.openai_api_key
        or not settings.openai_api_key.get_secret_value()
        or not settings.openai_model
    ):
        print("OpenAI API credentials or model are missing.")
        return 1

    print("CaspianX End-to-End Observation")
    print(f"Session: {SESSION_ID}")
    print(f"Model: {settings.openai_model}")
    print("Mode: read-only")
    print("Contacts sent: 0")

    try:
        with EventStore(settings.sqlite_path) as store:
            manager = SessionManager(store)
            analyses = AnalysisRepository(store)
            cycles = ObservationCycleRepository(store)
            leases = SessionLeaseRepository(store)
            cache = ObservationCache(store)
            replay = EventReplayService(store)

            async with TargetAPIClient(settings) as target:
                session = await target.get_session(SESSION_ID)

                if session.scenario_id != "practice":
                    raise ValueError("Only practice sessions may be observed.")

                manager.synchronize(session)

                async with OpenAIClient(
                    api_key=settings.openai_api_key,
                    model=settings.openai_model,
                    allow_live_calls=True,
                ) as analyzer:
                    cached_analyzer = CachedAnalyzer(
                        analyzer=analyzer,
                        cache=cache,
                        session_id=SESSION_ID,
                        model=settings.openai_model,
                    )

                    async def persist(
                        session_id: str,
                        analysis: EventAnalysis,
                    ) -> None:
                        """Persist one validated structured analysis.

                        Args:
                            session_id: Owning simulation session.
                            analysis: Structured result from the analyzer.

                        """
                        analyses.save(session_id, analysis)

                    recording_target = RecordingSessionReader(
                        reader=target,
                        replay=replay,
                    )

                    engine = CaspianXOrchestrator(
                        session_reader=recording_target,
                        analyzer=cached_analyzer,
                        persist=persist,
                    )

                    runner = ObservationRunner(
                        engine=engine,
                        cycles=cycles,
                        leases=leases,
                    )

                    recorded = await runner.run(SESSION_ID)
                    result = recorded.result

            restored = manager.restore(SESSION_ID)

            if restored is None:
                raise RuntimeError("Session recovery failed.")

            cycle = cycles.get(recorded.cycle_id)

            if cycle is None:
                raise RuntimeError("Observation cycle was not persisted.")

            print(f"Events observed: {result.event_count}")
            print(f"API events fetched: {recording_target.received_events}")
            print(f"New events persisted: {recording_target.new_events}")
            print(f"Replayed events: {replay.replay(SESSION_ID).total_events}")
            print(f"Observation cycle ID: {recorded.cycle_id}")
            print(f"Cycle status: {cycle['status']}")
            print(f"API contacts used: {result.touches_used}")
            print(f"Observation state: {result.state.value}")
            print(f"Stored analyses: {analyses.count(SESSION_ID)}")
            print(f"Session snapshot: {restored.state.value}")
            print(f"LLM cache hit: {cached_analyzer.cache_hits > 0}")

            if result.analysis is not None:
                print("Structured analysis:")
                print(result.analysis.model_dump_json(indent=2))

            print("End-to-end observation: OK")

        return 0

    except Exception as error:
        print(
            f"Observation failed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
