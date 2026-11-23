"""Produce privacy-preserving evidence from authorized simulation sessions."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping


_ALLOWED_FIELDS = ("id", "type", "message_id", "conversation_id", "channel", "in_reply_to")


def normalize_event(value: Any) -> dict[str, Any]:
    """Retain only non-content event metadata from a mapping or Pydantic event.

    Args:
        value: One event returned by the authorized simulation API.

    Returns:
        Redacted event metadata without message bodies, URLs, or form values.

    Raises:
        TypeError: If the event has an unsupported representation.
        ValueError: If the event type is missing.

    """
    if isinstance(value, Mapping):
        data = value
    elif callable(getattr(value, "model_dump", None)):
        data = value.model_dump()
    else:
        raise TypeError("Unsupported event object")
    event_type = data.get("type")
    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("Event type is required")
    return {
        key: data[key]
        for key in _ALLOWED_FIELDS
        if isinstance(data.get(key), str) and data[key].strip()
    }


def build_evidence(session: Any, events: list[Any]) -> dict[str, Any]:
    """Create a portable, sanitized snapshot of one real simulation session.

    Args:
        session: Session metadata returned by the simulation API.
        events: Events returned by the simulation API.

    Returns:
        Serializable evidence snapshot with no message or form contents.

    """
    metadata = [normalize_event(event) for event in events]
    digest = hashlib.sha256(
        json.dumps(metadata, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": 1,
        "source": "authorized_simulation_api",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "session_id": session.session_id,
        "scenario_id": session.scenario_id,
        "session_status": session.status,
        "touch_budget": session.touch_budget,
        "touches_used": session.touches_used,
        "remaining_touches": max(0, session.touch_budget - session.touches_used),
        "event_count": len(metadata),
        "event_metadata_sha256": digest,
        "events": metadata,
        "incident_confirmed": None,
        "incident_note": "Unverified; do not infer incidents from event type alone.",
    }


def validate_evidence(value: Any) -> dict[str, Any]:
    """Validate an evidence document before presenting its summary.

    Args:
        value: Parsed JSON document.

    Returns:
        Validated evidence document.

    Raises:
        ValueError: If expected required fields are inconsistent.

    """
    if not isinstance(value, dict):
        raise ValueError("Evidence must be an object")
    if value.get("source") != "authorized_simulation_api":
        raise ValueError("Unsupported evidence source")
    events = value.get("events")
    if not isinstance(events, list) or value.get("event_count") != len(events):
        raise ValueError("Event count does not match the saved history")
    for event in events:
        if not isinstance(event, dict) or set(event) - set(_ALLOWED_FIELDS):
            raise ValueError("Unsafe event fields in evidence file")
        normalize_event(event)
    for field in ("touch_budget", "touches_used", "remaining_touches"):
        if type(value.get(field)) is not int or value[field] < 0:
            raise ValueError(f"Invalid {field}")
    if value["touch_budget"] - value["touches_used"] != value["remaining_touches"]:
        raise ValueError("Inconsistent contact accounting")
    return value
