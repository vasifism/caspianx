"""Validate offline acceptance results, privacy, and failure handling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.final_acceptance import AcceptanceValidationError, assess_snapshots
from scripts.final_acceptance import DEMO_SNAPSHOTS, main


def test_demo_is_accepted() -> None:
    """Accept the expected cumulative offline demonstration history."""
    result = assess_snapshots(DEMO_SNAPSHOTS)
    assert result.status == "PASS"
    assert result.unique_event_count == 3
    assert result.snapshot_count == 4


def test_history_digest_is_deterministic() -> None:
    """Return identical evidence fingerprints for identical metadata."""
    assert (
        assess_snapshots(DEMO_SNAPSHOTS).history_digest
        == assess_snapshots(DEMO_SNAPSHOTS).history_digest
    )


def test_private_fields_do_not_change_digest() -> None:
    """Ensure private message content never enters deterministic evidence."""
    with_private = [[{"id": "e1", "type": "message.sent", "body": "SECRET_ONE"}]]
    with_other = [[{"id": "e1", "type": "message.sent", "body": "SECRET_TWO"}]]
    assert (
        assess_snapshots(with_private).history_digest == assess_snapshots(with_other).history_digest
    )


def test_rejects_nonmonotonic_snapshots() -> None:
    """Reject cumulative histories that lose previously observed events."""
    with pytest.raises(AcceptanceValidationError, match="lost"):
        assess_snapshots([[{"id": "a", "type": "message.sent"}], []])


def test_rejects_event_type_mutation() -> None:
    """Reject an event that changes identity metadata across snapshots."""
    with pytest.raises(AcceptanceValidationError, match="changed type"):
        assess_snapshots(
            [[{"id": "a", "type": "message.sent"}], [{"id": "a", "type": "message.reply"}]]
        )


def test_rejects_duplicate_ids() -> None:
    """Reject duplicate event identifiers within one snapshot."""
    item = {"id": "a", "type": "message.sent"}
    with pytest.raises(AcceptanceValidationError, match="Duplicate"):
        assess_snapshots([[item, item]])


def test_rejects_empty_snapshot_sequence() -> None:
    """Reject missing offline inputs rather than report an empty success."""
    with pytest.raises(AcceptanceValidationError):
        assess_snapshots([])


def test_rejects_invalid_event() -> None:
    """Reject unidentifiable event metadata."""
    with pytest.raises(AcceptanceValidationError):
        assess_snapshots([[{"id": "", "type": "message.sent"}]])


def test_unknown_type_is_not_confirmed_incident() -> None:
    """Treat unrecognized event types as candidates, not scoring success."""
    result = assess_snapshots([[{"id": "x", "type": "unknown.example"}]])
    assert result.novel_candidate_count == 1
    assert result.to_dict()["confirmed_incidents"] is None
    assert result.review_count >= 1


def test_cli_creates_report(tmp_path: Path) -> None:
    """Write an offline report containing only permitted summary fields."""
    output = tmp_path / "result.json"
    assert main(["--out", str(output)]) == 0
    document = json.loads(output.read_text(encoding="utf-8"))
    assert document["validation_status"] == "PASS"
    assert document["external_api_calls"] == 0
    assert document["confirmed_incidents"] is None


def test_cli_rejects_malformed_input(tmp_path: Path) -> None:
    """Fail closed on malformed JSON rather than emit invented results."""
    source = tmp_path / "bad.json"
    source.write_text("not-json", encoding="utf-8")
    assert main(["--input", str(source), "--out", str(tmp_path / "out.json")]) == 1


def test_cli_accepts_envelope(tmp_path: Path) -> None:
    """Read offline snapshots from the documented JSON envelope."""
    source = tmp_path / "events.json"
    source.write_text(json.dumps({"snapshots": DEMO_SNAPSHOTS}), encoding="utf-8")
    assert main(["--input", str(source), "--out", str(tmp_path / "out.json")]) == 0
