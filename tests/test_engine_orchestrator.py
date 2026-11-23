"""Test the read-only CaspianX orchestrator with offline dependencies."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.engine import CaspianXOrchestrator, OrchestratorError
from core.state_machine import SessionState
from llm.schemas import EventAnalysis


def make_analysis() -> EventAnalysis:
    """Create a deterministic structured event analysis."""
    return EventAnalysis(
        summary="One event was observed.",
        event_types=["reply"],
        has_reply=True,
        uncertainties=[],
        requires_review=False,
    )


def make_dependencies() -> tuple[
    SimpleNamespace,
    SimpleNamespace,
    AsyncMock,
]:
    """Create offline API, analyzer, and storage dependencies."""
    reader = SimpleNamespace(
        get_session=AsyncMock(
            return_value=SimpleNamespace(
                session_id="practice_001",
                touch_budget=30,
                touches_used=2,
            )
        ),
        get_events=AsyncMock(
            return_value=SimpleNamespace(
                events=[
                    SimpleNamespace(
                        id="event_001",
                        type="reply",
                        body="private information",
                    )
                ]
            )
        ),
    )

    analyzer = SimpleNamespace(
        analyze_events=AsyncMock(
            return_value=make_analysis(),
        )
    )

    persist = AsyncMock()

    return reader, analyzer, persist


def test_orchestrator_completes_observation() -> None:
    """Complete a read-only observation and persist its analysis."""

    async def run() -> None:
        """Exercise one successful orchestration cycle."""
        reader, analyzer, persist = make_dependencies()

        engine = CaspianXOrchestrator(
            session_reader=reader,
            analyzer=analyzer,
            persist=persist,
        )

        result = await engine.observe_once("practice_001")

        assert result.state is SessionState.COMPLETED
        assert result.event_count == 1
        assert result.touches_used == 2
        assert result.analysis == make_analysis()

        reader.get_session.assert_awaited_once()
        reader.get_events.assert_awaited_once()
        analyzer.analyze_events.assert_awaited_once()
        persist.assert_awaited_once()

    asyncio.run(run())


def test_orchestrator_filters_sensitive_content() -> None:
    """Never forward event bodies to the analyzer."""

    async def run() -> None:
        """Inspect the metadata passed to structured analysis."""
        reader, analyzer, persist = make_dependencies()

        engine = CaspianXOrchestrator(
            session_reader=reader,
            analyzer=analyzer,
            persist=persist,
        )

        await engine.observe_once("practice_001")

        analyzer.analyze_events.assert_awaited_once_with([{"id": "event_001", "type": "reply"}])

    asyncio.run(run())


def test_orchestrator_rejects_invalid_session_id() -> None:
    """Reject empty identifiers before calling dependencies."""

    async def run() -> None:
        """Verify early input validation."""
        reader, analyzer, persist = make_dependencies()

        engine = CaspianXOrchestrator(
            session_reader=reader,
            analyzer=analyzer,
            persist=persist,
        )

        with pytest.raises(ValueError):
            await engine.observe_once("")

        reader.get_session.assert_not_awaited()

    asyncio.run(run())


def test_orchestrator_rejects_mismatched_session() -> None:
    """Reject API responses belonging to another session."""

    async def run() -> None:
        """Simulate an inconsistent server response."""
        reader, analyzer, persist = make_dependencies()

        reader.get_session.return_value.session_id = "other_session"

        engine = CaspianXOrchestrator(
            session_reader=reader,
            analyzer=analyzer,
            persist=persist,
        )

        with pytest.raises(OrchestratorError):
            await engine.observe_once("practice_001")

        reader.get_events.assert_not_awaited()
        persist.assert_not_awaited()

    asyncio.run(run())


def test_orchestrator_handles_analysis_failure() -> None:
    """Propagate analysis errors without persisting invalid results."""

    async def run() -> None:
        """Simulate an unavailable analysis service."""
        reader, analyzer, persist = make_dependencies()

        analyzer.analyze_events.side_effect = RuntimeError("Analysis unavailable")

        engine = CaspianXOrchestrator(
            session_reader=reader,
            analyzer=analyzer,
            persist=persist,
        )

        with pytest.raises(OrchestratorError):
            await engine.observe_once("practice_001")

        persist.assert_not_awaited()

    asyncio.run(run())


def test_orchestrator_preserves_contact_budget() -> None:
    """Never increase the contact count during read-only observation."""

    async def run() -> None:
        """Verify that no contact operation is performed."""
        reader, analyzer, persist = make_dependencies()

        reader.get_session.return_value.touches_used = 10
        reader.get_session.return_value.touch_budget = 10

        engine = CaspianXOrchestrator(
            session_reader=reader,
            analyzer=analyzer,
            persist=persist,
        )

        result = await engine.observe_once("practice_001")

        assert result.touches_used == 10
        assert result.state is SessionState.COMPLETED

    asyncio.run(run())
