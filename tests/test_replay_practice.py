"""Test normalization of event collections from the practice API."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.replay_practice import extract_events


def test_extract_events_from_list() -> None:
    """Normalize a direct list of event dictionaries."""
    events = [
        {"id": "e1", "type": "message.opened"},
    ]

    assert extract_events(events) == events


def test_extract_events_from_response_object() -> None:
    """Normalize events nested in a response object."""
    response = SimpleNamespace(
        events=[
            {"id": "e2", "type": "message.reply"},
        ],
    )

    assert extract_events(response) == [
        {"id": "e2", "type": "message.reply"},
    ]


def test_extract_events_rejects_invalid_response() -> None:
    """Reject unsupported responses instead of silently losing events."""
    with pytest.raises(TypeError):
        extract_events("invalid response")
