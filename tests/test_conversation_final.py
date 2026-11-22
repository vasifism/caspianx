"""Test bounded conversation handling without external service access."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from agents.conversation_agent import (
    ConversationPolicyError,
    NeutralConversationAgent,
    validate_neutral_line,
)
from core.conversation_manager import ConversationManager
from evaluation.conversation_evaluator import evaluate_conversation
from scripts.practice_autonomous_conversation import OfflineConversationTransport
from storage.conversation_repository import ConversationRepository


def test_complete_offline_chat(tmp_path: Path) -> None:
    """Record a dialogue, close it, and verify the durable transcript."""

    async def run() -> None:
        """Execute an isolated conversation with the mock transport."""
        with ConversationRepository(tmp_path / "test.sqlite3") as repo:
            manager = ConversationManager(
                OfflineConversationTransport(), repo, NeutralConversationAgent()
            )
            result = await manager.run("session_1", "julius")
            assert result.status == "ended"
            assert result.turns_sent == 1
            assert len(repo.history(result.conversation_id)) == 3
            assert repo.pending("session_1") == []

    asyncio.run(run())


def test_restart_preserves_ledger(tmp_path: Path) -> None:
    """Verify transcript persistence after reopening the SQLite database."""
    path = tmp_path / "database.sqlite3"

    async def run() -> None:
        """Persist one conversation before the restart."""
        with ConversationRepository(path) as repo:
            await ConversationManager(
                OfflineConversationTransport(), repo, NeutralConversationAgent()
            ).run("s_1", "julius")

    asyncio.run(run())
    with ConversationRepository(path) as repo:
        assert repo.snapshot("s_1")["conversations"] == 1
        assert repo.snapshot("s_1")["transcript_lines"] == 3


def test_timeout_blocks_a_second_contact(tmp_path: Path) -> None:
    """Preserve ambiguous start attempts and prevent automatic resubmission."""

    class TimeoutTransport(OfflineConversationTransport):
        """Simulate an ambiguous timeout after request transmission."""

        async def start(self, session_id: str, target_id: str, channel: str, key: str) -> dict:
            """Raise an unexpected transport timeout."""
            raise TimeoutError("synthetic timeout")

    async def run() -> None:
        """Attempt a request twice and ensure the latter is blocked locally."""
        with ConversationRepository(tmp_path / "test.sqlite3") as repo:
            manager = ConversationManager(TimeoutTransport(), repo, NeutralConversationAgent())
            with pytest.raises(TimeoutError):
                await manager.run("s_1", "julius")
            assert len(repo.pending("s_1")) == 1
            with pytest.raises(RuntimeError, match="Unresolved"):
                await manager.run("s_1", "julius")

    asyncio.run(run())


def test_policy_rejects_secret_requests() -> None:
    """Block obvious requests for credentials and similar sensitive data."""
    with pytest.raises(ConversationPolicyError):
        validate_neutral_line("Please give me your password")


def test_policy_rejects_long_lines() -> None:
    """Block overlong model outputs before sending them."""
    with pytest.raises(ConversationPolicyError):
        validate_neutral_line("x" * 601)


def test_turn_limit_is_enforced(tmp_path: Path) -> None:
    """Reject configurations exceeding the documented ten-turn maximum."""
    with ConversationRepository(tmp_path / "test.sqlite3") as repo:
        with pytest.raises(ValueError):
            ConversationManager(
                OfflineConversationTransport(), repo, NeutralConversationAgent(), max_turns=11
            )


def test_evaluation_never_invents_incidents() -> None:
    """Never convert a normal persona reply into a confirmed scoring incident."""
    report = evaluate_conversation([{"direction": "persona", "body": "Hello"}], [])
    assert report.reply_observed
    assert report.event_count == 0
    assert not report.confirmed_incident


def test_ledger_records_one_pending_operation(tmp_path: Path) -> None:
    """Persist a unique request key before the network attempt."""
    with ConversationRepository(tmp_path / "test.sqlite3") as repo:
        op = repo.reserve("session_a", "start", {"to": "julius", "channel": "live_chat"})
        assert len(repo.pending("session_a")) == 1
        assert len(op.idempotency_key) > 20
        repo.complete(op.operation_id, {"conversation_id": "c_1"})
        assert repo.pending("session_a") == []


def test_event_field_values_are_never_persisted(tmp_path: Path) -> None:
    """Discard sensitive form values from stored transport responses."""
    with ConversationRepository(tmp_path / "sensitive.sqlite3") as repo:
        op = repo.reserve("s_1", "turn", {"say": "hello"})
        repo.complete(
            op.operation_id,
            {
                "events": [
                    {"id": "e_1", "type": "page.submitted", "values": {"password": "supersecret"}}
                ],
                "persona_says": "Hello",
            },
        )
        row = repo.connection.execute(
            "SELECT response_json FROM cx_operations WHERE operation_id=?", (op.operation_id,)
        ).fetchone()[0]
        assert "supersecret" not in row
        assert "password" not in row
        assert "page.submitted" in row
