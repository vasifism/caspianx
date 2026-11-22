"""Run durable observation cycles with optional exclusive session ownership."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol

from core.engine import ObservationResult
from storage.observation_cycles import ObservationCycleRepository
from storage.session_lease import SessionLeaseRepository


class ObservationEngine(Protocol):
    """Define the observation operation provided by the orchestrator."""

    async def observe_once(self, session_id: str) -> ObservationResult:
        """Execute one bounded observation cycle."""
        ...


class SessionLeaseBusyError(RuntimeError):
    """Indicate that another execution already owns a session."""


@dataclass(frozen=True, slots=True)
class RecordedObservation:
    """Describe one successfully recorded observation cycle.

    Attributes:
        cycle_id: Identifier of the persisted observation cycle.
        result: Structured outcome returned by the orchestrator.

    """

    cycle_id: str
    result: ObservationResult


class ObservationRunner:
    """Run observations while tracking outcomes and optional ownership."""

    def __init__(
        self,
        engine: ObservationEngine,
        cycles: ObservationCycleRepository,
        leases: SessionLeaseRepository | None = None,
    ) -> None:
        """Initialize the runner and its persistence dependencies.

        Args:
            engine: Orchestrator responsible for observations.
            cycles: Repository that stores observation outcomes.
            leases: Optional repository enforcing exclusive execution.

        """
        self._engine = engine
        self._cycles = cycles
        self._leases = leases

    async def run(self, session_id: str) -> RecordedObservation:
        """Execute an observation with durable lifecycle recording.

        A lease, when configured, is acquired before the cycle begins
        and released when execution leaves the protected region.

        Args:
            session_id: Identifier of the session to observe.

        Returns:
            Identifier and result of the completed observation.

        Raises:
            ValueError: If the session identifier is invalid.
            SessionLeaseBusyError: If another owner holds the session.
            Exception: If observation or persistence fails.

        """
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be nonempty.")

        owner_token: str | None = None

        if self._leases is not None:
            owner_token = self._leases.acquire(session_id)

            if owner_token is None:
                raise SessionLeaseBusyError(f"Session {session_id!r} already has an active lease.")

        try:
            cycle_id = self._cycles.start(session_id)

            try:
                result = await self._engine.observe_once(session_id)

            except asyncio.CancelledError:
                self._cycles.finish(
                    cycle_id,
                    error_type="CancelledError",
                )
                raise

            except Exception as error:
                self._cycles.finish(
                    cycle_id,
                    error_type=type(error).__name__,
                )
                raise

            self._cycles.finish(
                cycle_id,
                event_count=result.event_count,
            )

            return RecordedObservation(
                cycle_id=cycle_id,
                result=result,
            )

        finally:
            if self._leases is not None and owner_token is not None:
                self._leases.release(session_id, owner_token)
