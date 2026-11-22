"""Compare immutable, redacted simulation evidence snapshots."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.competition_evidence import validate_evidence


def load_snapshot(path: Path) -> dict[str, Any]:
    """Load and validate a saved evidence snapshot.

    Args:
        path: Path to an existing sanitized evidence file.

    Returns:
        Validated evidence data.

    """
    return validate_evidence(json.loads(path.read_text(encoding="utf-8")))


def event_key(event: dict[str, Any]) -> str:
    """Derive a deterministic, content-free event identity.

    Args:
        event: Allowlisted metadata of one event.

    Returns:
        Stable string identifying the event metadata.

    """
    return hashlib.sha256(
        json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def compare_snapshots(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Compute event additions and removals without assuming a verdict.

    Args:
        before: Earlier validated evidence snapshot.
        after: Later validated evidence snapshot for the same session.

    Returns:
        Sanitized comparison with newly seen event metadata.

    Raises:
        ValueError: If the snapshots belong to different sessions or scenarios.

    """
    old = validate_evidence(before)
    new = validate_evidence(after)
    for field in ("session_id", "scenario_id"):
        if old[field] != new[field]:
            raise ValueError(f"Snapshots have different {field}")
    remaining = Counter(event_key(event) for event in old["events"])
    added: list[dict[str, Any]] = []
    for event in new["events"]:
        key = event_key(event)
        if remaining[key]:
            remaining[key] -= 1
        else:
            added.append(event)
    before_keys = Counter(event_key(event) for event in old["events"])
    after_keys = Counter(event_key(event) for event in new["events"])
    removed = sum((before_keys - after_keys).values())
    return {
        "session_id": new["session_id"],
        "scenario_id": new["scenario_id"],
        "events_before": old["event_count"],
        "events_after": new["event_count"],
        "new_event_count": len(added),
        "removed_event_count": removed,
        "new_events": added,
        "touches_before": old["touches_used"],
        "touches_after": new["touches_used"],
        "touches_delta": new["touches_used"] - old["touches_used"],
        "confirmed_incident": "NOT VERIFIED",
        "note": "Events and changes are observations, not scoring verdicts.",
    }
