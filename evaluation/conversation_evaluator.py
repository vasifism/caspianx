"""Classify observations without claiming unverified competition success."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConversationEvaluation:
    """Summarize simulated dialogue and observed API events."""

    reply_observed: bool
    event_count: int
    event_types: tuple[str, ...]
    confirmed_incident: bool


def evaluate_conversation(
    transcript: list[dict[str, str]], events: list[dict[str, Any]]
) -> ConversationEvaluation:
    """Compute factual signals without inferring unauthorized outcomes."""
    event_types = tuple(str(event.get("type", "unknown")) for event in events)
    return ConversationEvaluation(
        reply_observed=any(
            row.get("direction") == "persona" and bool(row.get("body", "").strip())
            for row in transcript
        ),
        event_count=len(events),
        event_types=event_types,
        confirmed_incident=False,
    )
