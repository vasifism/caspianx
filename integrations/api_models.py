"""Typed, forward-compatible models for the revel8 simulation API.

Unknown response fields are preserved; do not assume API examples are exhaustive.
Sensitive submitted values are redacted on ingestion, before persistence/logging.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from config.constants import (
    MAX_ATTACHMENTS_PER_MESSAGE,
    MAX_CONVERSATION_SAY_CHARS,
    MAX_PAGE_FIELDS,
)


class APIModel(BaseModel):
    """Base schema that preserves additional fields returned by the API."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Target(APIModel):
    """Represent a target listed in a simulation scenario."""

    id: str
    name: str
    role: str | None = None


class Objective(APIModel):
    """Describe an objective published by the simulation."""

    id: str
    text: str


class Scenario(APIModel):
    """Describe a practice or evaluation scenario and its availability."""

    id: str
    kind: str
    open: bool
    company: str | None = None
    targets: list[Target] = Field(default_factory=list)
    objectives: list[Objective] = Field(default_factory=list)
    touch_budget: int | None = None
    max_sessions: int | None = None
    opens_at: str | None = None


class CreateSessionRequest(APIModel):
    """Specify the scenario for a new simulation session."""

    scenario_id: str = "practice"


class Session(APIModel):
    """Represent a session and its remaining contact budget."""

    session_id: str
    scenario_id: str
    touch_budget: int = Field(ge=0)
    touches_used: int = Field(ge=0)
    status: str
    story_time: str | int | float | None = None

    @property
    def remaining_touches(self) -> int:
        """Calculate the nonnegative number of contacts remaining."""
        return max(0, self.touch_budget - self.touches_used)


class Sender(APIModel):
    """Describe the sender identity presented by a simulation channel."""

    name: str | None = None
    address: str | None = None


class AttachmentReference(APIModel):
    """Describe a simulated file or transcribed audio attachment."""

    filename: str
    transcript: str | None = None


class MessageRequest(APIModel):
    """Validate the payload of a simulated message."""

    to: str
    channel: str
    sender: Sender | None = Field(default=None, alias="from")
    subject: str | None = None
    body: str = Field(min_length=1)
    attachments: list[str | AttachmentReference] = Field(
        default_factory=list, max_length=MAX_ATTACHMENTS_PER_MESSAGE
    )
    sent_at: str | int | float | None = None

    @field_validator("sent_at")
    @classmethod
    def validate_story_timestamp(cls, value: str | int | float | None):
        """Ensure the message timestamp is valid simulation time."""
        if value is not None:
            from core.story_clock import parse_story_time

            parse_story_time(value)
        return value


SENSITIVE_FIELD_NAMES = frozenset(
    {
        "password",
        "passwd",
        "passcode",
        "pin",
        "otp",
        "verification_code",
        "token",
        "api_key",
        "card_number",
        "iban",
        "secret",
        "access_token",
        "private_key",
        "client_secret",
    }
)
REDACTED = "[REDACTED]"


class Event(APIModel):
    """Represent an observed simulation event with redacted secret fields."""

    id: str | None = None
    type: str
    message_id: str | None = None
    conversation_id: str | None = None
    channel: str | None = None
    in_reply_to: str | None = None
    subject: str | None = None
    body: str | None = None
    url: str | None = None
    page_id: str | None = None
    fields: list[str] = Field(default_factory=list)
    values: dict[str, Any] | None = None

    @model_validator(mode="before")
    @classmethod
    def redact_values(cls, data: Any):
        """Mask known sensitive form fields before storing parsed event data."""
        if not isinstance(data, dict):
            return data
        data = dict(data)
        raw = data.get("values")
        if isinstance(raw, dict):
            data["values"] = {
                key: (
                    REDACTED if key.casefold().replace("-", "_") in SENSITIVE_FIELD_NAMES else value
                )
                for key, value in raw.items()
            }
        return data


class MessageResponse(APIModel):
    """Represent the outcome and events of a message contact."""

    message_id: str
    touches_used: int = Field(ge=0)
    events: list[Event] = Field(default_factory=list)


class EventsResponse(APIModel):
    """Contain events retrieved for a session."""

    events: list[Event] = Field(default_factory=list)


class StartConversationRequest(APIModel):
    """Validate parameters for opening a live simulated conversation."""

    to: str
    channel: Literal["phone_call", "video_call", "teams_call", "live_chat"]
    sender: Sender | None = Field(default=None, alias="from")
    sent_at: str | int | float | None = None


class ConversationResponse(APIModel):
    """Describe the status and opening response of a live conversation."""

    conversation_id: str
    status: str
    persona_says: str | None = None
    touches_used: int = Field(ge=0)


class ConversationTurnRequest(APIModel):
    """Validate one outgoing turn in a simulated conversation."""

    say: str = Field(min_length=1, max_length=MAX_CONVERSATION_SAY_CHARS)
    sent_at: str | int | float | None = None
    attachments: list[str | AttachmentReference] = Field(default_factory=list, max_length=5)


class ConversationTurnResponse(APIModel):
    """Describe the reply and events from one conversation turn."""

    persona_says: str | None = None
    ended: bool
    events: list[Event] = Field(default_factory=list)
    turns_used: int = Field(ge=0)


class PageRequest(APIModel):
    """Describe a simulated page registered within a session."""

    url: str
    title: str
    html: str | None = None
    text: str | None = None
    images: list[str] | None = None
    fields: list[str] = Field(default_factory=list, max_length=MAX_PAGE_FIELDS)

    @model_validator(mode="after")
    def require_visible_content(self):
        """Require either HTML or text for a simulated page."""
        if not self.html and not self.text:
            raise ValueError("A page needs html or text")
        return self


class PageResponse(APIModel):
    """Provide the identifier of a registered simulated page."""

    page_id: str


class AssetResponse(APIModel):
    """Describe an uploaded simulation asset."""

    asset_id: str
    type: str
    size: int = Field(ge=0)
