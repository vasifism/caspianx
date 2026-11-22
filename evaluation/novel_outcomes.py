"""Track unusual outcome candidates for organizer review without scoring claims."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from evaluation.anomaly_detector import AnomalyDetector


@dataclass(frozen=True, slots=True)
class OutcomeCandidate:
    """Represent an unverified outcome signal based solely on event metadata."""

    event_id: str
    event_type: str
    review_status: str = "requires_organizer_verification"

    def to_dict(self) -> dict[str, str]:
        """Serialize the candidate without including arbitrary event payloads."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "review_status": self.review_status,
        }


def identify_novel_outcomes(
    events: Sequence[Mapping[str, Any]],
    *,
    known_types: Sequence[str] | None = None,
) -> tuple[OutcomeCandidate, ...]:
    """Collect unfamiliar event types for later independent review.

    This function does not establish an incident. It does not inspect message
    bodies or form values and does not contact the simulation or external APIs.
    """
    detector = AnomalyDetector(known_types)
    report = detector.analyze(events)
    ids = {
        finding.event_id for finding in report.findings if finding.code == "UNRECOGNIZED_EVENT_TYPE"
    }
    candidates: dict[str, OutcomeCandidate] = {}
    for event in events:
        event_id = event.get("id")
        event_type = event.get("type")
        if isinstance(event_id, str) and event_id in ids and isinstance(event_type, str):
            candidates.setdefault(event_id, OutcomeCandidate(event_id, event_type))
    return tuple(candidates.values())
