"""Validate simulated event history progression without network or LLM calls."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from evaluation.anomaly_detector import AnomalyDetector, AnomalyFinding


@dataclass(frozen=True, slots=True)
class OfflineStep:
    """Represent one replayed snapshot of a synthetic or recorded history."""

    position: int
    total_events: int
    new_events: int
    reused_events: int
    fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize one step without copying event content."""
        return {
            "position": self.position,
            "total_events": self.total_events,
            "new_events": self.new_events,
            "reused_events": self.reused_events,
            "fingerprint": self.fingerprint,
        }


@dataclass(frozen=True, slots=True)
class OfflineRunReport:
    """Represent an offline replay validation and its bounded conclusions."""

    steps: tuple[OfflineStep, ...]
    findings: tuple[AnomalyFinding, ...]
    unique_events: int
    novel_outcome_candidates: int
    confirmed_incidents: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Return sanitized evidence, with no claim of scoring success."""
        return {
            "mode": "offline_only",
            "steps": [step.to_dict() for step in self.steps],
            "findings": [item.to_dict() for item in self.findings],
            "unique_events": self.unique_events,
            "novel_outcome_candidates": self.novel_outcome_candidates,
            "confirmed_incidents": self.confirmed_incidents,
            "live_contacts_sent": 0,
            "external_api_calls": 0,
            "openai_calls": 0,
        }


def _fingerprint(events: Sequence[Mapping[str, Any]]) -> str:
    """Hash ordered event identifiers and types, excluding all other fields."""
    safe = [{"id": event.get("id"), "type": event.get("type")} for event in events]
    packed = json.dumps(safe, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()


def validate_offline_run(
    snapshots: Sequence[Sequence[Mapping[str, Any]]],
    *,
    known_types: Sequence[str] | None = None,
) -> OfflineRunReport:
    """Replay successive cumulative snapshots, ignoring duplicate identifiers.

    Distinct event metadata must not change for an existing event identifier.
    The function does not attempt incident verification or outbound contact.
    """
    if not isinstance(snapshots, (list, tuple)) or not snapshots:
        raise ValueError("snapshots must be a nonempty list or tuple")
    detector = AnomalyDetector(known_types)
    seen: dict[str, str] = {}
    steps: list[OfflineStep] = []
    all_findings: list[AnomalyFinding] = []
    novel_types: set[str] = set()
    for position, snapshot in enumerate(snapshots):
        if not isinstance(snapshot, (list, tuple)):
            raise TypeError("each snapshot must be a list or tuple")
        result = detector.analyze(snapshot)
        all_findings.extend(result.findings)
        new_count = 0
        reused_count = 0
        for event in snapshot:
            event_id = event.get("id")
            event_type = event.get("type")
            if not isinstance(event_id, str) or not event_id.strip():
                continue
            if not isinstance(event_type, str) or not event_type.strip():
                continue
            previous = seen.get(event_id)
            if previous is not None:
                reused_count += 1
                if previous != event_type:
                    all_findings.append(
                        AnomalyFinding(
                            "CONFLICTING_EVENT_ID",
                            "error",
                            event_id,
                            "An existing event identifier changed type.",
                        )
                    )
            else:
                seen[event_id] = event_type
                new_count += 1
        for finding in result.findings:
            if finding.code == "UNRECOGNIZED_EVENT_TYPE" and finding.event_id:
                novel_types.add(finding.event_id)
        steps.append(
            OfflineStep(position, len(snapshot), new_count, reused_count, _fingerprint(snapshot))
        )
    return OfflineRunReport(tuple(steps), tuple(all_findings), len(seen), len(novel_types))
