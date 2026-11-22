"""Validate sanitized simulation history and generate conservative evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from evaluation.anomaly_detector import AnomalyDetector
from evaluation.offline_run_validation import validate_offline_run


class AcceptanceValidationError(ValueError):
    """Indicate that an evidence input violates acceptance requirements."""


@dataclass(frozen=True, slots=True)
class AcceptanceResult:
    """Describe an offline validation result without claiming incident success."""

    snapshot_count: int
    unique_event_count: int
    last_snapshot_count: int
    anomaly_count: int
    error_count: int
    review_count: int
    novel_candidate_count: int
    history_digest: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize deterministic and privacy-preserving result fields."""
        return {
            "schema_version": 1,
            "mode": "offline_evidence_only",
            "snapshot_count": self.snapshot_count,
            "unique_event_count": self.unique_event_count,
            "last_snapshot_count": self.last_snapshot_count,
            "anomaly_count": self.anomaly_count,
            "error_count": self.error_count,
            "review_count": self.review_count,
            "novel_outcome_candidates": self.novel_candidate_count,
            "history_digest": self.history_digest,
            "validation_status": self.status,
            "confirmed_incidents": None,
            "incident_verification": "not_performed",
            "outbound_contacts": 0,
            "external_api_calls": 0,
            "model_calls": 0,
        }


def _validate_snapshots(
    snapshots: Sequence[Sequence[Mapping[str, Any]]],
) -> list[list[dict[str, str]]]:
    """Normalize event metadata and reject malformed or conflicting histories."""
    if not isinstance(snapshots, (list, tuple)) or not snapshots:
        raise AcceptanceValidationError("At least one snapshot is required.")
    normalized: list[list[dict[str, str]]] = []
    observed: dict[str, str] = {}
    for index, snapshot in enumerate(snapshots):
        if not isinstance(snapshot, (list, tuple)):
            raise AcceptanceValidationError(f"Snapshot {index} must be a list.")
        current: list[dict[str, str]] = []
        local: set[str] = set()
        for position, event in enumerate(snapshot):
            if not isinstance(event, Mapping):
                raise AcceptanceValidationError(
                    f"Snapshot {index}, event {position} must be a mapping."
                )
            event_id = event.get("id")
            event_type = event.get("type")
            if not isinstance(event_id, str) or not event_id.strip():
                raise AcceptanceValidationError("An event has no valid ID.")
            if not isinstance(event_type, str) or not event_type.strip():
                raise AcceptanceValidationError("An event has no valid type.")
            if event_id in local:
                raise AcceptanceValidationError("Duplicate ID inside one snapshot.")
            if event_id in observed and observed[event_id] != event_type:
                raise AcceptanceValidationError("Existing event changed type.")
            local.add(event_id)
            observed[event_id] = event_type
            current.append({"id": event_id, "type": event_type})
        normalized.append(current)
    return normalized


def assess_snapshots(
    snapshots: Sequence[Sequence[Mapping[str, Any]]],
) -> AcceptanceResult:
    """Assess safe event metadata and reject non-monotonic event histories.

    Event bodies, form fields, addresses, and submitted secrets are never used.
    An unfamiliar event may require review but never proves an incident.
    """
    safe = _validate_snapshots(snapshots)
    previous_ids: set[str] = set()
    for snapshot in safe:
        current_ids = {item["id"] for item in snapshot}
        if not previous_ids.issubset(current_ids):
            raise AcceptanceValidationError("Cumulative history lost an earlier event.")
        previous_ids = current_ids
    checked = validate_offline_run(safe)
    detected = AnomalyDetector().analyze(safe[-1])
    errors = sum(item.severity == "error" for item in detected.findings)
    reviews = sum(item.severity == "review" for item in detected.findings)
    canonical = json.dumps(safe, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return AcceptanceResult(
        snapshot_count=len(safe),
        unique_event_count=checked.unique_events,
        last_snapshot_count=len(safe[-1]),
        anomaly_count=len(detected.findings),
        error_count=errors,
        review_count=reviews,
        novel_candidate_count=detected.novel_outcome_candidates,
        history_digest=digest,
        status="PASS" if errors == 0 else "FAIL",
    )
