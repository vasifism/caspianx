"""Test live evidence minimization and offline reporting."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluation.competition_evidence import (
    build_evidence,
    normalize_event,
    validate_evidence,
)
from scripts.capture_live_evidence import write_new_json
from scripts.print_live_evidence import summarize


def session() -> SimpleNamespace:
    """Return a synthetic metadata-only practice session."""
    return SimpleNamespace(
        session_id="test_session",
        scenario_id="practice",
        status="active",
        touch_budget=30,
        touches_used=1,
    )


def test_event_minimization_discards_sensitive_fields() -> None:
    """Exclude bodies, URLs, personal information, and submitted values."""
    result = normalize_event(
        {
            "id": "e1",
            "type": "message.reply",
            "body": "secret message",
            "url": "https://example.invalid/secret",
            "values": {"password": "TEST_PASSWORD"},
        }
    )
    assert result == {"id": "e1", "type": "message.reply"}


def test_event_requires_type() -> None:
    """Reject events without an observable type."""
    with pytest.raises(ValueError):
        normalize_event({"id": "e1"})


def test_build_evidence_does_not_assert_incident() -> None:
    """Do not label a simulator event as a confirmed objective."""
    evidence = build_evidence(
        session(), [{"id": "e1", "type": "page.submitted", "values": {"pin": "123"}}]
    )
    assert evidence["incident_confirmed"] is None
    assert "123" not in json.dumps(evidence)
    assert validate_evidence(evidence) is evidence


def test_counter_consistency_is_verified() -> None:
    """Reject a contact-budget accounting mismatch."""
    evidence = build_evidence(session(), [])
    evidence["remaining_touches"] = 99
    with pytest.raises(ValueError):
        validate_evidence(evidence)


def test_unsafe_metadata_is_rejected() -> None:
    """Prevent analysis of evidence containing unapproved event fields."""
    evidence = build_evidence(session(), [])
    evidence["events"] = [{"id": "e1", "type": "reply", "body": "secret"}]
    evidence["event_count"] = 1
    with pytest.raises(ValueError):
        validate_evidence(evidence)


def test_immutable_evidence_export(tmp_path: Path) -> None:
    """Refuse overwriting an evidence snapshot with another capture."""
    path = tmp_path / "evidence.json"
    evidence = build_evidence(session(), [])
    write_new_json(path, evidence)
    with pytest.raises(FileExistsError):
        write_new_json(path, evidence)
    assert json.loads(path.read_text())["session_id"] == "test_session"


def test_offline_summary_uses_real_source_label(tmp_path: Path) -> None:
    """Summarize event types without claiming a successful attack."""
    path = tmp_path / "saved.json"
    write_new_json(path, build_evidence(session(), [{"type": "message.opened"}]))
    result = summarize(path)
    assert result["event_type_counts"] == {"message.opened": 1}
    assert result["confirmed_incident"] == "NOT VERIFIED"
