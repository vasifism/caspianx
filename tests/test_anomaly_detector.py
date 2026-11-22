"""Regression tests for the metadata-only anomaly detector."""

from __future__ import annotations

import pytest

from evaluation.anomaly_detector import AnomalyDetector


def test_clean_events_have_no_findings() -> None:
    """Accept a clean, ordered set of recognized events."""
    result = AnomalyDetector().analyze(
        [
            {"id": "a", "type": "message.sent", "sent_at": "2026-11-21T10:00:00+00:00"},
            {"id": "b", "type": "message.opened", "sent_at": "2026-11-21T10:01:00+00:00"},
        ],
        touches_used=1,
        touch_budget=30,
    )
    assert not result.findings
    assert result.confirmed_incidents == 0


def test_duplicate_identifiers_are_flagged() -> None:
    """Detect duplicated identifiers without disclosing event content."""
    result = AnomalyDetector().analyze(
        [{"id": "a", "type": "message.sent"}, {"id": "a", "type": "message.sent"}]
    )
    assert [item.code for item in result.findings] == ["DUPLICATE_EVENT_ID"]


def test_missing_id_and_type_are_flagged() -> None:
    """Reject incomplete event metadata with explicit diagnostic codes."""
    result = AnomalyDetector().analyze([{"body": "must-not-appear"}])
    assert {item.code for item in result.findings} == {"MISSING_EVENT_ID", "MISSING_EVENT_TYPE"}
    assert "must-not-appear" not in str(result.to_dict())


def test_unrecognized_type_is_candidate_not_incident() -> None:
    """Treat unknown events as review candidates rather than scored wins."""
    result = AnomalyDetector().analyze(
        [{"id": "x", "type": "novel.event", "incident": True, "body": "private"}]
    )
    assert result.novel_outcome_candidates == 1
    assert result.confirmed_incidents == 0
    assert "private" not in str(result.to_dict())


def test_untrusted_incident_flag_does_not_count() -> None:
    """Ignore fabricated incident flags even on otherwise recognized events."""
    result = AnomalyDetector().analyze([{"id": "x", "type": "message.reply", "incident": True}])
    assert result.confirmed_incidents == 0
    assert result.novel_outcome_candidates == 0


def test_budget_overrun_is_detected() -> None:
    """Flag impossible contact counters in supplied snapshots."""
    result = AnomalyDetector().analyze([], touches_used=31, touch_budget=30)
    assert result.findings[0].code == "BUDGET_OVERRUN"


def test_invalid_budget_inputs_are_rejected() -> None:
    """Reject booleans and negative counters to avoid silent coercion."""
    with pytest.raises(ValueError):
        AnomalyDetector().analyze([], touches_used=True)
    with pytest.raises(ValueError):
        AnomalyDetector().analyze([], touch_budget=-1)


def test_timestamp_order_and_format() -> None:
    """Report both a backwards timestamp and a malformed timestamp."""
    events = [
        {"id": "a", "type": "message.sent", "sent_at": "2026-11-21T10:00:00Z"},
        {"id": "b", "type": "message.opened", "sent_at": "2026-11-21T09:00:00Z"},
        {"id": "c", "type": "message.reply", "sent_at": "yesterday"},
    ]
    result = AnomalyDetector().analyze(events)
    assert {item.code for item in result.findings} == {
        "OUT_OF_ORDER_TIMESTAMP",
        "INVALID_TIMESTAMP",
    }


def test_empty_and_invalid_event_lists() -> None:
    """Support empty histories and reject malformed response types."""
    assert AnomalyDetector().analyze([]).event_count == 0
    with pytest.raises(TypeError):
        AnomalyDetector().analyze("not-an-event-list")
    with pytest.raises(TypeError):
        AnomalyDetector().analyze(["not-a-mapping"])


def test_custom_recognized_types() -> None:
    """Support a documented API taxonomy without modifying detector code."""
    assert (
        not AnomalyDetector(["platform.event"])
        .analyze([{"id": "a", "type": "platform.event"}])
        .findings
    )
    with pytest.raises(ValueError):
        AnomalyDetector([""])
