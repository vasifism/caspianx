"""Coordinate read-only simulation observation and structured event analysis."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from core.state_machine import SessionState, SessionStateMachine
from llm.schemas import EventAnalysis


class SessionReader(Protocol):
    """Describe the read-only simulation operations required by the engine."""

    async def get_session(self, session_id: str) -> Any:
        """Retrieve authoritative session metadata."""
        ...

    async def get_events(self, session_id: str) -> Any:
        """Retrieve events observed during a simulation session."""
        ...


class EventAnalyzer(Protocol):
    """Describe the structured event analysis interface."""

    async def analyze_events(
        self,
        events: list[Mapping[str, Any]],
    ) -> EventAnalysis:
        """Analyze sanitized event metadata."""
        ...


class OrchestratorError(RuntimeError):
    """Represent an unsuccessful orchestration cycle."""


@dataclass(frozen=True, slots=True)
class ObservationResult:
    """Contain the validated outcome of one observation cycle.

    Attributes:
        session_id: Identifier of the observed simulation session.
        event_count: Number of events returned by the simulation.
        analysis: Structured event analysis, if any.
        state: Final state of the orchestration cycle.
        touches_used: Authoritative number of consumed contacts.

    """

    session_id: str
    event_count: int
    analysis: EventAnalysis | None
    state: SessionState
    touches_used: int


class CaspianXOrchestrator:
    """Coordinate a bounded read-only observation and analysis cycle."""

    def __init__(
        self,
        *,
        session_reader: SessionReader,
        analyzer: EventAnalyzer,
        persist: Callable[
            [str, EventAnalysis],
            Awaitable[None],
        ],
    ) -> None:
        """Configure the orchestration dependencies.

        Args:
            session_reader: Read-only simulation API adapter.
            analyzer: Structured event analysis service.
            persist: Async callback for storing sanitized analysis.

        """
        self._reader = session_reader
        self._analyzer = analyzer
        self._persist = persist
        self._locks: dict[str, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    async def _session_lock(self, session_id: str) -> asyncio.Lock:
        """Return the shared in-process lock for a session.

        Args:
            session_id: Identifier of the session.

        Returns:
            Lock that serializes observation cycles for this session.

        """
        async with self._locks_guard:
            return self._locks.setdefault(
                session_id,
                asyncio.Lock(),
            )

    async def observe_once(
        self,
        session_id: str,
    ) -> ObservationResult:
        """Read, analyze, and persist one session observation.

        Args:
            session_id: Existing simulation session identifier.

        Returns:
            Completed observation result.

        Raises:
            ValueError: If the session identifier is empty.
            OrchestratorError: If a dependency fails during observation.

        """
        if not isinstance(session_id, str) or not session_id:
            raise ValueError("session_id must be a nonempty string.")

        lock = await self._session_lock(session_id)

        async with lock:
            return await self._observe_locked(session_id)

    async def _observe_locked(
        self,
        session_id: str,
    ) -> ObservationResult:
        """Perform one serialized observation cycle.

        Args:
            session_id: Validated session identifier.

        Returns:
            Result of the completed cycle.

        Raises:
            OrchestratorError: If a dependency fails.

        """
        machine: SessionStateMachine | None = None

        try:
            session = await self._reader.get_session(session_id)

            if session.session_id != session_id:
                raise ValueError("API returned a mismatched session ID.")

            machine = SessionStateMachine(
                session_id=session_id,
                touch_limit=session.touch_budget,
                touches_used=session.touches_used,
            )

            machine.transition(SessionState.OBSERVING)

            response = await self._reader.get_events(session_id)
            events = response.events

            # Only these metadata fields are passed to the model.
            metadata = [
                {
                    "id": event.id,
                    "type": event.type,
                }
                for event in events
            ]

            machine.transition(SessionState.ANALYZING)

            analysis = await self._analyzer.analyze_events(
                metadata,
            )

            machine.transition(SessionState.PERSISTING)

            await self._persist(session_id, analysis)

            machine.transition(SessionState.COMPLETED)

            return ObservationResult(
                session_id=session_id,
                event_count=len(events),
                analysis=analysis,
                state=machine.state,
                touches_used=machine.touches_used,
            )

        except Exception as error:
            if machine is not None and machine.can_transition(SessionState.RECOVERING):
                machine.transition(SessionState.RECOVERING)

            raise OrchestratorError(f"Observation failed: {type(error).__name__}") from error
