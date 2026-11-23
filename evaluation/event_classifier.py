"""Classify simulation event metadata into auditable, non-sensitive categories."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


KNOWN_CATEGORIES: dict[str, str] = {
    "message.sent": "outbound",
    "contact.sent": "outbound",
    "message.opened": "engagement",
    "link.opened": "engagement",
    "file.opened": "engagement",
    "page.opened": "engagement",
    "message.reply": "response",
    "message.replied": "response",
    "conversation.replied": "response",
    "page.submitted": "submission_observed",
    "conversation.started": "conversation",
}


@dataclass(frozen=True, slots=True)
class EventTypeSummary:
    """Summarize categories without including event payloads."""

    counts: dict[str, int]
    total: int
    unknown: int

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-safe counts without raw message data."""
        return {"counts": dict(self.counts), "total": self.total, "unknown": self.unknown}


def classify_event_type(event_type: str) -> str:
    """Return the category for a recognized event type or ``unknown``."""
    if not isinstance(event_type, str):
        raise TypeError("event_type must be a string")
    return KNOWN_CATEGORIES.get(event_type, "unknown")


def summarize_event_types(events: Sequence[Mapping[str, Any]]) -> EventTypeSummary:
    """Aggregate event categories without examining private event fields."""
    if not isinstance(events, (list, tuple)):
        raise TypeError("events must be a list or tuple")
    counts: Counter[str] = Counter()
    for event in events:
        if not isinstance(event, Mapping):
            raise TypeError("each event must be a mapping")
        event_type = event.get("type")
        category = classify_event_type(event_type) if isinstance(event_type, str) else "unknown"
        counts[category] += 1
    return EventTypeSummary(dict(sorted(counts.items())), len(events), counts["unknown"])
