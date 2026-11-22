"""Test exclusive session ownership during recorded observations."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.observation_runner import (
    ObservationRunner,
    SessionLeaseBusyError,
)
from storage.event_store import EventStore
from storage.observation_cycles import ObservationCycleRepository
from storage.session_lease import SessionLeaseRepository


SESSION_ID = "practice_001"


def test_successful_run_releases_lease(tmp_path: Path) -> None:
    """Release session ownership after successful observation."""

    async def run() -> None:
        """Execute a successful observation with an active lease."""
        with EventStore(tmp_path / "test.sqlite3") as store:
            cycles = ObservationCycleRepository(store)
            leases = SessionLeaseRepository(store)
            engine = SimpleNamespace(
                observe_once=AsyncMock(return_value=SimpleNamespace(event_count=2))
            )

            runner = ObservationRunner(engine, cycles, leases)
            recorded = await runner.run(SESSION_ID)

            assert recorded.result.event_count == 2
            assert leases.get(SESSION_ID) is None
            assert cycles.get(recorded.cycle_id)["status"] == "completed"

    asyncio.run(run())


def test_failed_run_releases_lease(tmp_path: Path) -> None:
    """Release ownership and record a failed observation."""

    async def run() -> None:
        """Execute a failing observation under exclusive ownership."""
        with EventStore(tmp_path / "test.sqlite3") as store:
            cycles = ObservationCycleRepository(store)
            leases = SessionLeaseRepository(store)
            engine = SimpleNamespace(
                observe_once=AsyncMock(side_effect=TimeoutError("Synthetic timeout"))
            )

            runner = ObservationRunner(engine, cycles, leases)

            with pytest.raises(TimeoutError):
                await runner.run(SESSION_ID)

            assert leases.get(SESSION_ID) is None

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


def test_existing_lease_blocks_observation(tmp_path: Path) -> None:
    """Prevent observations when another owner holds a lease."""

    async def run() -> None:
        """Verify that a busy session rejects a new observation."""
        with EventStore(tmp_path / "test.sqlite3") as store:
            cycles = ObservationCycleRepository(store)
            leases = SessionLeaseRepository(store)

            first_owner = leases.acquire(SESSION_ID)
            assert first_owner is not None

            engine = SimpleNamespace(observe_once=AsyncMock())
            runner = ObservationRunner(engine, cycles, leases)

            with pytest.raises(SessionLeaseBusyError):
                await runner.run(SESSION_ID)

            engine.observe_once.assert_not_awaited()

            cursor = store.database.execute_sql("SELECT COUNT(*) FROM observation_cycles")
            assert cursor.fetchone()[0] == 0

            assert leases.get(SESSION_ID).owner_token == first_owner

    asyncio.run(run())


def test_concurrent_observations_are_exclusive(
    tmp_path: Path,
) -> None:
    """Reject a competing observation while the first is active."""

    async def run() -> None:
        """Coordinate two runners competing for one session."""
        with EventStore(tmp_path / "test.sqlite3") as store:
            cycles = ObservationCycleRepository(store)
            leases = SessionLeaseRepository(store)

            started = asyncio.Event()
            release_engine = asyncio.Event()

            async def observe(session_id: str) -> SimpleNamespace:
                """Block observation until explicitly released."""
                started.set()
                await release_engine.wait()
                return SimpleNamespace(event_count=0)

            engine = SimpleNamespace(observe_once=AsyncMock(side_effect=observe))

            first = ObservationRunner(engine, cycles, leases)
            second = ObservationRunner(engine, cycles, leases)

            task = asyncio.create_task(first.run(SESSION_ID))

            try:
                await started.wait()

                with pytest.raises(SessionLeaseBusyError):
                    await second.run(SESSION_ID)

                assert engine.observe_once.await_count == 1

            finally:
                release_engine.set()
                await task

            assert leases.get(SESSION_ID) is None

    asyncio.run(run())


def test_cancelled_observation_releases_lease(
    tmp_path: Path,
) -> None:
    """Release ownership when an observation task is cancelled."""

    async def run() -> None:
        """Cancel a pending observation and inspect durable state."""
        with EventStore(tmp_path / "test.sqlite3") as store:
            cycles = ObservationCycleRepository(store)
            leases = SessionLeaseRepository(store)

            started = asyncio.Event()

            async def observe(session_id: str) -> SimpleNamespace:
                """Wait until the observation task is cancelled."""
                started.set()
                await asyncio.Event().wait()
                return SimpleNamespace(event_count=0)

            engine = SimpleNamespace(observe_once=AsyncMock(side_effect=observe))
            runner = ObservationRunner(engine, cycles, leases)

            task = asyncio.create_task(runner.run(SESSION_ID))
            await started.wait()
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task

            assert leases.get(SESSION_ID) is None

            cursor = store.database.execute_sql(
                """
                SELECT status, error_type
                FROM observation_cycles
                WHERE session_id = ?
                """,
                (SESSION_ID,),
            )

            assert cursor.fetchone() == ("failed", "CancelledError")

    asyncio.run(run())
