"""Test read-only live-evidence diffing and presentation safeguards."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluation.competition_evidence import build_evidence, validate_evidence
from evaluation.live_evidence_diff import compare_snapshots, event_key, load_snapshot
from scripts.build_thread_brief import render
from scripts.watch_live_events import save_new


def make_snapshot(events: list[dict], *, used: int = 1, session_id: str = "s_test") -> dict:
    """Create validated, synthetic evidence using the production sanitizer."""
    session = SimpleNamespace(
        session_id=session_id,
        scenario_id="practice",
        status="active",
        touch_budget=30,
        touches_used=used,
    )
    return build_evidence(session, events)


def test_new_realistic_event_detected() -> None:
    """Detect a newly visible event without asserting an incident."""
    before = make_snapshot([])
    after = make_snapshot([{"id": "e1", "type": "message.opened"}])
    result = compare_snapshots(before, after)
    assert result["new_event_count"] == 1
    assert result["confirmed_incident"] == "NOT VERIFIED"


def test_duplicate_event_counts_are_preserved() -> None:
    """Treat repeated event records as a multiset rather than a set."""
    event = {"id": "e1", "type": "message.opened"}
    result = compare_snapshots(make_snapshot([event]), make_snapshot([event, event]))
    assert result["new_event_count"] == 1


def test_removed_event_count_detected() -> None:
    """Flag API histories that drop an earlier event."""
    result = compare_snapshots(
        make_snapshot([{"id": "e1", "type": "message.opened"}]),
        make_snapshot([]),
    )
    assert result["removed_event_count"] == 1


def test_different_sessions_refused() -> None:
    """Prevent misleading cross-session comparisons."""
    with pytest.raises(ValueError):
        compare_snapshots(make_snapshot([], session_id="s1"), make_snapshot([], session_id="s2"))


def test_touch_change_without_events() -> None:
    """Report contact-budget changes separately from returned events."""
    result = compare_snapshots(make_snapshot([], used=1), make_snapshot([], used=2))
    assert result["touches_delta"] == 1
    assert result["new_event_count"] == 0


def test_sensitive_event_content_excluded() -> None:
    """Drop bodies and form values before evidence comparison."""
    secret = "FORBIDDEN_PRIVATE_CONTENT"
    after = make_snapshot([{"id": "e1", "type": "message.reply", "body": secret}])
    result = compare_snapshots(make_snapshot([]), after)
    assert secret not in str(result)


def test_event_key_is_order_independent() -> None:
    """Hash identical field sets consistently despite key insertion order."""
    assert event_key({"id": "e1", "type": "x"}) == event_key({"type": "x", "id": "e1"})


def test_empty_thread_does_not_invent_reaction() -> None:
    """Label zero-event history without presenting a fictional thread."""
    rendered = render(make_snapshot([]))
    assert "No API events were returned" in rendered
    assert "NOT VERIFIED" in rendered


def test_nonempty_brief_remains_metadata_only() -> None:
    """Include event metadata but no message content."""
    evidence = make_snapshot([{"id": "e1", "type": "message.reply", "body": "SECRET"}])
    rendered = render(evidence)
    assert "message.reply" in rendered
    assert "SECRET" not in rendered
    assert "not a rendered real thread" in rendered


def test_snapshot_is_immutable(tmp_path: Path) -> None:
    """Refuse overwriting the first evidence capture."""
    path = tmp_path / "evidence.json"
    save_new(path, make_snapshot([]))
    with pytest.raises(FileExistsError):
        save_new(path, make_snapshot([]))
    assert load_snapshot(path)["event_count"] == 0


def test_validator_rejects_body_in_evidence() -> None:
    """Reject manually modified snapshots that expose message content."""
    evidence = make_snapshot([{"id": "e1", "type": "message.reply"}])
    evidence["events"][0]["body"] = "unsafe"
    with pytest.raises(ValueError):
        validate_evidence(evidence)
