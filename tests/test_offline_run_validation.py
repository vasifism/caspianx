"""Verify conservative, deterministic offline event-history validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.offline_run_validation import validate_offline_run
from scripts.offline_full_run import main


def test_full_run_tracks_incremental_events_and_reuses() -> None:
    """Count new versus previously known events across snapshots."""
    report = validate_offline_run(
        [
            [],
            [{"id": "a", "type": "message.sent"}],
            [
                {"id": "a", "type": "message.sent"},
                {"id": "b", "type": "message.opened"},
            ],
        ]
    )
    assert [step.new_events for step in report.steps] == [0, 1, 1]
    assert [step.reused_events for step in report.steps] == [0, 0, 1]
    assert report.unique_events == 2
    assert report.confirmed_incidents == 0


def test_repeated_history_produces_same_fingerprint() -> None:
    """Use stable cache keys when observable metadata is unchanged."""
    event = {"id": "a", "type": "message.sent"}
    report = validate_offline_run([[event], [event]])
    assert report.steps[0].fingerprint == report.steps[1].fingerprint


def test_new_history_changes_fingerprint() -> None:
    """Invalidate replay fingerprints on new events."""
    report = validate_offline_run(
        [
            [{"id": "a", "type": "message.sent"}],
            [{"id": "a", "type": "message.sent"}, {"id": "b", "type": "message.reply"}],
        ]
    )
    assert report.steps[0].fingerprint != report.steps[1].fingerprint


def test_mutated_identifier_is_flagged() -> None:
    """Detect attempts to alter a previously recorded event's type."""
    report = validate_offline_run(
        [[{"id": "a", "type": "message.sent"}], [{"id": "a", "type": "message.reply"}]]
    )
    assert "CONFLICTING_EVENT_ID" in [item.code for item in report.findings]


def test_novel_outcome_does_not_claim_scoring_success() -> None:
    """Present a novel outcome only as a candidate for human verification."""
    report = validate_offline_run([[{"id": "x", "type": "unrecognized.action", "incident": True}]])
    assert report.novel_outcome_candidates == 1
    assert report.confirmed_incidents == 0
    assert report.to_dict()["external_api_calls"] == 0


def test_report_never_includes_sensitive_fields() -> None:
    """Ensure synthetic passwords and message bodies are not in output."""
    report = validate_offline_run(
        [[{"id": "x", "type": "message.sent", "body": "private-body", "password": "topsecret"}]]
    )
    result = json.dumps(report.to_dict())
    assert "private-body" not in result
    assert "topsecret" not in result


def test_invalid_snapshots_raise() -> None:
    """Reject missing or incorrectly shaped replay inputs."""
    with pytest.raises(ValueError):
        validate_offline_run([])
    with pytest.raises(TypeError):
        validate_offline_run(["wrong"])


def test_offline_cli_creates_report(tmp_path: Path) -> None:
    """Generate complete synthetic run evidence without external services."""
    outfile = tmp_path / "offline.json"
    assert main(["--out", str(outfile)]) == 0
    report = json.loads(outfile.read_text(encoding="utf-8"))
    assert report["unique_events"] == 3
    assert report["confirmed_incidents"] == 0
    assert report["live_contacts_sent"] == 0
