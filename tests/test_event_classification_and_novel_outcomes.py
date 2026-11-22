"""Test classification and conservative unknown-outcome review."""

from __future__ import annotations

import json

import pytest

from evaluation.event_classifier import classify_event_type, summarize_event_types
from evaluation.novel_outcomes import identify_novel_outcomes


def test_known_event_type_categories() -> None:
    """Classify event actions using declared metadata categories."""
    assert classify_event_type("message.sent") == "outbound"
    assert classify_event_type("message.reply") == "response"
    assert classify_event_type("page.submitted") == "submission_observed"


def test_unrecognized_event_types_remain_unknown() -> None:
    """Avoid treating an unrecognized name as confirmed success."""
    assert classify_event_type("unlisted.result") == "unknown"
    with pytest.raises(TypeError):
        classify_event_type(None)  # type: ignore[arg-type]


def test_event_type_summary_counts_all_events() -> None:
    """Count event categories without needing to inspect private values."""
    report = summarize_event_types(
        [
            {"type": "message.sent"},
            {"type": "message.opened"},
            {"type": "unlisted.result"},
            {"id": "missing-type"},
        ]
    )
    assert report.total == 4
    assert report.unknown == 2
    assert report.counts["outbound"] == 1


def test_event_type_summary_does_not_export_payloads() -> None:
    """Exclude body and other sensitive values from the summary."""
    report = summarize_event_types([{"type": "message.reply", "body": "private-message"}])
    assert "private-message" not in json.dumps(report.to_dict())


def test_novel_outcome_requires_organizer_review() -> None:
    """Collect unusual event types without treating them as incidents."""
    items = identify_novel_outcomes(
        [
            {"id": "e1", "type": "unlisted.event", "incident": True},
            {"id": "e2", "type": "message.opened"},
        ]
    )
    assert len(items) == 1
    assert items[0].review_status == "requires_organizer_verification"
    assert items[0].event_id == "e1"


def test_novel_outcome_deduplicates_event_ids() -> None:
    """Return only one review candidate for repeated event identifiers."""
    items = identify_novel_outcomes(
        [{"id": "e1", "type": "unlisted.event"}, {"id": "e1", "type": "unlisted.event"}]
    )
    assert len(items) == 1


def test_novel_outcome_does_not_include_message_content() -> None:
    """Limit candidate records to identifiers, types, and review status."""
    items = identify_novel_outcomes(
        [{"id": "e1", "type": "unlisted.event", "body": "private-message"}]
    )
    assert "private-message" not in json.dumps([x.to_dict() for x in items])
