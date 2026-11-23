"""Module for tests test api models.py."""

import pytest
from pydantic import ValidationError

from integrations.api_models import (
    Event,
    MessageRequest,
    Session,
    Scenario,
    ConversationTurnRequest,
    PageRequest,
    REDACTED,
)
from integrations.api_errors import TargetAPIError


def test_hidden_eval_scenario_is_valid():
    """Verify hidden eval scenario is valid."""
    scenario = Scenario.model_validate({"id": "eval", "kind": "eval", "open": False})
    assert scenario.targets == []


def test_remaining_touches():
    """Verify remaining touches."""
    session = Session.model_validate(
        {
            "session_id": "s_1",
            "scenario_id": "practice",
            "touch_budget": 30,
            "touches_used": 4,
            "status": "active",
            "story_time": None,
        }
    )
    assert session.remaining_touches == 26


def test_sender_uses_from_alias():
    """Verify sender uses from alias."""
    item = MessageRequest.model_validate(
        {
            "to": "julius",
            "channel": "email",
            "from": {"name": "Example"},
            "body": "Hello",
            "sent_at": "2026-11-23T09:14:00+01:00",
        }
    )
    assert item.model_dump(by_alias=True, exclude_none=True)["from"] == {"name": "Example"}


def test_form_values_redact_secrets_on_parse():
    """Verify form values redact secrets on parse."""
    event = Event.model_validate(
        {
            "type": "page.submitted",
            "fields": ["email", "password"],
            "values": {"email": "person@example.test", "password": "sensitive-data"},
        }
    )
    assert event.values == {"email": "person@example.test", "password": REDACTED}
    assert "sensitive-data" not in str(event.model_dump())


def test_unknown_event_type_is_supported():
    """Verify unknown event type is supported."""
    event = Event.model_validate({"type": "new.event", "unexpected": 42})
    assert event.model_extra["unexpected"] == 42


def test_page_must_have_content():
    """Verify page must have content."""
    with pytest.raises(ValidationError):
        PageRequest(url="https://example.test", title="Example")


def test_conversation_turn_max_length():
    """Verify conversation turn max length."""
    with pytest.raises(ValidationError):
        ConversationTurnRequest(say="A" * 4001)


def test_retryable_status_codes():
    """Verify retryable status codes."""
    assert TargetAPIError(503).retryable
    assert not TargetAPIError(422).retryable
