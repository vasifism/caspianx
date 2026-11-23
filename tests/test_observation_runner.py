"""Test durable orchestration results with an isolated SQLite database."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.observation_runner import ObservationRunner
from storage.event_store import EventStore
from storage.observation_cycles import ObservationCycleRepository


def test_successful_observation_is_recorded(tmp_path: Path) -> None:
    """Mark a successful observation as completed."""

    async def run() -> None:
        """Execute one successful observation through a mocked engine."""
        with EventStore(tmp_path / "test.sqlite3") as store:
            cycles = ObservationCycleRepository(store)
            result = SimpleNamespace(event_count=3)
            engine = SimpleNamespace(
                observe_once=AsyncMock(return_value=result),
            )

            runner = ObservationRunner(engine, cycles)
            recorded = await runner.run("practice_001")
            record = cycles.get(recorded.cycle_id)

            assert record is not None
            assert record["status"] == "completed"
            assert record["event_count"] == 3
            assert recorded.result is result
            engine.observe_once.assert_awaited_once_with("practice_001")

    asyncio.run(run())


def test_failed_observation_is_recorded(tmp_path: Path) -> None:
    """Persist a failed observation without storing its exception message."""

    async def run() -> None:
        """Execute a failing observation and inspect its record."""
        with EventStore(tmp_path / "test.sqlite3") as store:
            cycles = ObservationCycleRepository(store)
            engine = SimpleNamespace(
                observe_once=AsyncMock(side_effect=TimeoutError("sensitive detail")),
            )

            runner = ObservationRunner(engine, cycles)

            with pytest.raises(TimeoutError):
                await runner.run("practice_001")

            cursor = store.database.execute_sql(
                """
                SELECT status, error_type
                FROM observation_cycles
                WHERE session_id = ?
                """,
                ("practice_001",),
            )
            status, error_type = cursor.fetchone()

            assert status == "failed"
            assert error_type == "TimeoutError"

    asyncio.run(run())


def test_invalid_session_does_not_start_cycle(tmp_path: Path) -> None:
    """Reject an invalid identifier without inserting a cycle."""

    async def run() -> None:
        """Verify that invalid input is rejected before persistence."""
        with EventStore(tmp_path / "test.sqlite3") as store:
            cycles = ObservationCycleRepository(store)
            engine = SimpleNamespace(observe_once=AsyncMock())
            runner = ObservationRunner(engine, cycles)

            with pytest.raises(ValueError):
                await runner.run("")

            cursor = store.database.execute_sql("SELECT COUNT(*) FROM observation_cycles")
            assert cursor.fetchone()[0] == 0
            engine.observe_once.assert_not_awaited()

    asyncio.run(run())


def test_recorded_cycle_survives_restart(tmp_path: Path) -> None:
    """Retain observation history after reopening SQLite."""
    path = tmp_path / "durable.sqlite3"

    async def run() -> str:
        """Persist an observation and return its identifier."""
        with EventStore(path) as store:
            cycles = ObservationCycleRepository(store)
            engine = SimpleNamespace(
                observe_once=AsyncMock(return_value=SimpleNamespace(event_count=0)),
            )
            runner = ObservationRunner(engine, cycles)
            recorded = await runner.run("practice_001")
            return recorded.cycle_id

    cycle_id = asyncio.run(run())

    with EventStore(path) as store:
        cycles = ObservationCycleRepository(store)
        record = cycles.get(cycle_id)

        assert record is not None
        assert record["status"] == "completed"
        assert record["event_count"] == 0
