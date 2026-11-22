"""Test the read-only, non-deceptive CaspianX competition completion tools."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agents.adaptive_dialogue_agent import AdaptiveDialogueAgent
from core.scoring_window_readiness import assess_scenarios, assess_session
from evaluation.conversation_thread_export import export_thread, render_json, render_markdown
from research.public_fact_registry import PublicFact, load_registry, summarize_subject
from storage.conversation_repository import ConversationRepository


def test_eval_session_budget() -> None:
    """Report actual budget without allocating additional contacts."""
    assessment = assess_session(
        {
            "session_id": "s_eval",
            "scenario_id": "eval",
            "status": "active",
            "touches_used": 3,
            "touch_budget": 10,
        }
    )
    assert assessment.remaining == 7
    assert assessment.concerns == ()


def test_eval_session_nonstandard_budget_flagged() -> None:
    """Flag unexpected scoring budgets rather than silently assuming ten."""
    assessment = assess_session(
        {
            "session_id": "s_eval",
            "scenario_id": "eval",
            "status": "active",
            "touches_used": 3,
            "touch_budget": 30,
        }
    )
    assert "unexpected_eval_budget" in assessment.concerns


def test_bad_budget_rejected() -> None:
    """Reject impossible used-contact values."""
    with pytest.raises(ValueError):
        assess_session(
            {"session_id": "s", "scenario_id": "eval", "touches_used": 11, "touch_budget": 10}
        )


def test_hidden_eval_targets_not_invented() -> None:
    """Do not manufacture eval identities while the scenario is unreleased."""
    summary = assess_scenarios(
        [{"id": "eval", "kind": "eval", "open": False, "opens_at": "tomorrow"}]
    )
    assert summary["scenarios"][0]["target_ids"] == []
    assert summary["scenarios"][0]["targets_revealed"] is False


def test_discovered_target_ids_preserved() -> None:
    """Use only the target identifiers returned by the API."""
    summary = assess_scenarios(
        [{"id": "eval", "open": True, "targets": [{"id": "different_person"}]}]
    )
    assert summary["scenarios"][0]["target_ids"] == ["different_person"]


def test_public_fact_requires_provenance() -> None:
    """Disallow ungrounded or insecure sources."""
    fact = PublicFact("test", "Public role", "http://example.org/a", "2026-11-21T10:00:00+00:00")
    with pytest.raises(ValueError):
        fact.validate()


def test_public_fact_future_date_rejected() -> None:
    """Reject source observations whose timestamps are in the future."""
    observed = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    with pytest.raises(ValueError):
        PublicFact("test", "Public role", "https://example.org/a", observed).validate()


def test_public_fact_registry_roundtrip(tmp_path: Path) -> None:
    """Preserve and attribute only operator-provided statements."""
    path = tmp_path / "facts.json"
    path.write_text(
        json.dumps(
            [
                {
                    "subject_id": "person1",
                    "statement": "Publicly listed speaker",
                    "source_url": "https://example.org/speaker",
                    "observed_at": "2026-11-21T10:00:00+00:00",
                    "category": "event",
                }
            ]
        ),
        encoding="utf-8",
    )
    registry = load_registry(path)
    assert summarize_subject(registry, "person1")["fact_count"] == 1
    assert summarize_subject(registry, "other")["status"] == "SOURCE_REQUIRED"


def test_agent_adapts_to_clarification() -> None:
    """Respond transparently to a request for the purpose of the test."""
    policy = AdaptiveDialogueAgent(max_agent_lines=3)
    history = [
        {"direction": "persona", "body": "Hello"},
        {"direction": "agent", "body": "Testing"},
        {"direction": "persona", "body": "Who are you and what is this about?"},
    ]
    answer = asyncio.run(policy.next_line(history))
    assert answer is not None and "integration check" in answer


def test_agent_respects_stop_signal() -> None:
    """Terminate a conversation when the other side requests to stop."""
    policy = AdaptiveDialogueAgent()
    history = [
        {"direction": "persona", "body": "Hello"},
        {"direction": "agent", "body": "Testing"},
        {"direction": "persona", "body": "Please stop."},
    ]
    assert asyncio.run(policy.next_line(history)) is None


def test_agent_turn_cap() -> None:
    """Prevent additional lines after the configured upper bound."""
    policy = AdaptiveDialogueAgent(max_agent_lines=1)
    history = [{"direction": "agent", "body": "Testing"}]
    assert asyncio.run(policy.next_line(history)) is None


def test_thread_export_from_ledger(tmp_path: Path) -> None:
    """Preserve the true recorded exchange and avoid incident claims."""
    database = tmp_path / "conversation.sqlite3"
    with ConversationRepository(database) as repository:
        repository.record_conversation("c_001", "s_001", "test", "live_chat", "ended")
        repository.record_line("c_001", "persona", "Hello")
        repository.record_line("c_001", "agent", "Hello, this is a test")
    thread = export_thread(database, "c_001")
    assert thread["turn_count"] == 1
    assert thread["transcript"][0]["body"] == "Hello"
    assert "NOT VERIFIED" in render_markdown(thread)
    assert json.loads(render_json(thread))["status"] == "ended"


def test_thread_export_requires_existing_conversation(tmp_path: Path) -> None:
    """Never manufacture an absent conversation or scoring thread."""
    database = tmp_path / "conversation.sqlite3"
    with ConversationRepository(database):
        pass
    with pytest.raises(LookupError):
        export_thread(database, "c_not_real")


def test_adaptive_offline_end_to_end(tmp_path: Path) -> None:
    """Verify a three-turn adaptive dialogue through manager and SQLite."""
    from argparse import Namespace

    from scripts.practice_adaptive_conversation import run

    arguments = Namespace(
        session="offline_end_to_end",
        target="julius",
        db=tmp_path / "adaptive.sqlite3",
        max_turns=3,
        live=False,
        confirm_practice_contact=False,
    )
    output = asyncio.run(run(arguments))
    assert output["turns_sent"] == 3
    assert output["ledger"]["unresolved_operations"] == 0
    assert output["ledger"]["transcript_lines"] == 7
    assert output["incident"] == "NOT VERIFIED"


def test_adaptive_live_requires_confirmation(tmp_path: Path) -> None:
    """Refuse real practice contact without the explicit expenditure flag."""
    from argparse import Namespace

    from scripts.practice_adaptive_conversation import run

    arguments = Namespace(
        session="s_any",
        target="julius",
        db=tmp_path / "adaptive.sqlite3",
        max_turns=3,
        live=True,
        confirm_practice_contact=False,
    )
    with pytest.raises(ValueError, match="confirm-practice-contact"):
        asyncio.run(run(arguments))
