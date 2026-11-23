"""Execute a bounded practice-only conversation with durable request records."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from agents.conversation_agent import ConversationAgent, validate_neutral_line
from storage.conversation_repository import ConversationRepository


class ConversationTransport(Protocol):
    """Define the minimum simulation conversation API contract."""

    async def get_session(self, session_id: str) -> dict[str, Any]:
        """Retrieve session metadata."""
        ...

    async def start(
        self, session_id: str, target_id: str, channel: str, key: str
    ) -> dict[str, Any]:
        """Open a new simulation conversation."""
        ...

    async def turn(self, conversation_id: str, line: str, key: str) -> dict[str, Any]:
        """Deliver one line in an existing simulation conversation."""
        ...

    async def end(self, conversation_id: str, key: str) -> dict[str, Any]:
        """End the simulation conversation."""
        ...


@dataclass(frozen=True)
class ConversationResult:
    """Describe an observed, not necessarily successful, conversation."""

    conversation_id: str
    status: str
    turns_sent: int
    events_seen: int
    touches_used: int


class ConversationManager:
    """Run a limited practice conversation and record each attempt."""

    def __init__(
        self,
        transport: ConversationTransport,
        repository: ConversationRepository,
        agent: ConversationAgent,
        *,
        max_turns: int = 2,
    ) -> None:
        """Configure transport, durable ledger, and bounded agent behavior."""
        if not 1 <= max_turns <= 10:
            raise ValueError("max_turns must be between 1 and 10")
        self.transport = transport
        self.repository = repository
        self.agent = agent
        self.max_turns = max_turns

    async def run(
        self, session_id: str, target_id: str, channel: str = "live_chat"
    ) -> ConversationResult:
        """Execute one new practice conversation, with no implicit retries.

        On timeout or another ambiguous failure, an operation remains pending
        for reconciliation; this method never blindly resends that operation.
        """
        if not session_id.strip() or not target_id.strip():
            raise ValueError("Session and target identifiers are required")
        if channel not in {"live_chat", "phone_call", "video_call", "teams_call"}:
            raise ValueError("Unsupported conversation channel")
        session = await self.transport.get_session(session_id)
        if session.get("scenario_id") != "practice" or session.get("status") != "active":
            raise ValueError("Live dialog is restricted to active practice sessions")
        if int(session.get("touches_used", -1)) >= int(session.get("touch_budget", 0)):
            raise ValueError("Practice touch budget exhausted")
        if self.repository.pending(session_id):
            raise RuntimeError("Unresolved outbound operation: reconcile before proceeding")
        start_payload: dict[str, object] = {"to": target_id, "channel": channel}
        operation = self.repository.reserve(session_id, "start", start_payload)
        started = await self.transport.start(
            session_id, target_id, channel, operation.idempotency_key
        )
        conversation_id = str(started["conversation_id"])
        self.repository.complete(operation.operation_id, started)
        self.repository.record_conversation(
            conversation_id, session_id, target_id, channel, str(started.get("status", "unknown"))
        )
        self.repository.record_line(
            conversation_id, "persona", str(started.get("persona_says") or "")
        )
        status = str(started.get("status", "unknown"))
        touches_used = int(started.get("touches_used", 0))
        events_seen = len(started.get("events") or [])
        turns_sent = 0
        while status == "answered" and turns_sent < self.max_turns:
            history = self.repository.history(conversation_id)
            line = validate_neutral_line(await self.agent.next_line(history))
            if line is None:
                break
            turn_operation = self.repository.reserve(
                session_id, "turn", {"say": line}, conversation_id
            )
            received = await self.transport.turn(
                conversation_id, line, turn_operation.idempotency_key
            )
            self.repository.complete(turn_operation.operation_id, received)
            self.repository.record_line(conversation_id, "agent", line)
            self.repository.record_line(
                conversation_id, "persona", str(received.get("persona_says") or "")
            )
            turns_sent += 1
            events_seen += len(received.get("events") or [])
            if received.get("ended", False):
                status = "ended"
                break
        if status != "ended":
            end_operation = self.repository.reserve(session_id, "end", {}, conversation_id)
            ended = await self.transport.end(conversation_id, end_operation.idempotency_key)
            self.repository.complete(end_operation.operation_id, ended)
            status = "ended"
        self.repository.update_status(conversation_id, status)
        return ConversationResult(conversation_id, status, turns_sent, events_seen, touches_used)
