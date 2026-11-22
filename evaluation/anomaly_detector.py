"""Identify unusual simulation telemetry without interpreting private content.

Only metadata is inspected. Findings are not evidence that a scored incident
occurred, and unusual event names never trigger automatic outbound actions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class AnomalyFinding:
    """Represent one metadata-only, non-sensitive diagnostic finding."""

    code: str
    severity: str
    event_id: str | None
    explanation: str

    def to_dict(self) -> dict[str, str | None]:
        """Return JSON-safe diagnostic fields without raw event content."""
        return {
            "code": self.code,
            "severity": self.severity,
            "event_id": self.event_id,
            "explanation": self.explanation,
        }


@dataclass(frozen=True, slots=True)
class AnomalyReport:
    """Describe metadata anomalies and tentative unusual-outcome signals."""

    event_count: int
    findings: tuple[AnomalyFinding, ...]
    novel_outcome_candidates: int
    confirmed_incidents: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize counts and sanitized findings for an offline report."""
        return {
            "event_count": self.event_count,
            "findings": [item.to_dict() for item in self.findings],
            "novel_outcome_candidates": self.novel_outcome_candidates,
            "confirmed_incidents": self.confirmed_incidents,
            "incident_verification": "not_performed",
        }


class AnomalyDetector:
    """Detect malformed, duplicated, unfamiliar, or out-of-order event metadata."""

    DEFAULT_TYPES = frozenset(
        {
            "message.sent",
            "message.opened",
            "message.reply",
            "message.replied",
            "link.opened",
            "file.opened",
            "page.opened",
            "page.submitted",
            "contact.sent",
            "conversation.started",
            "conversation.replied",
        }
    )

    def __init__(self, known_types: Sequence[str] | None = None) -> None:
        """Configure recognized event types without importing API packages."""
        selected = self.DEFAULT_TYPES if known_types is None else known_types
        if isinstance(selected, (str, bytes)):
            raise ValueError("known_types must be a sequence of names")
        if any(not isinstance(item, str) or not item.strip() for item in selected):
            raise ValueError("known_types must contain nonempty strings")
        self._known_types = frozenset(selected)

    def analyze(
        self,
        events: Sequence[Mapping[str, Any]],
        *,
        touches_used: int | None = None,
        touch_budget: int | None = None,
    ) -> AnomalyReport:
        """Inspect only whitelisted metadata and return conservative findings.

        Event payloads, message bodies, form values, URLs, and notes are ignored.
        Caller-supplied flags such as ``incident`` are never counted as proof.
        """
        if not isinstance(events, (list, tuple)):
            raise TypeError("events must be a list or tuple")
        for name, value in (("touches_used", touches_used), ("touch_budget", touch_budget)):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{name} must be a nonnegative integer")
        findings: list[AnomalyFinding] = []
        ids: set[str] = set()
        candidate_count = 0
        last_time: datetime | None = None

        if touches_used is not None and touch_budget is not None and touches_used > touch_budget:
            findings.append(
                AnomalyFinding(
                    "BUDGET_OVERRUN",
                    "error",
                    None,
                    "The reported contact count exceeds the configured budget.",
                )
            )

        for index, event in enumerate(events):
            if not isinstance(event, Mapping):
                raise TypeError(f"event at position {index} is not a mapping")
            raw_id = event.get("id")
            raw_type = event.get("type")
            event_id = raw_id if isinstance(raw_id, str) and raw_id.strip() else None
            event_type = raw_type if isinstance(raw_type, str) and raw_type.strip() else None
            if event_id is None:
                findings.append(
                    AnomalyFinding(
                        "MISSING_EVENT_ID",
                        "error",
                        None,
                        "An event is missing a usable identifier.",
                    )
                )
            elif event_id in ids:
                findings.append(
                    AnomalyFinding(
                        "DUPLICATE_EVENT_ID",
                        "warning",
                        event_id,
                        "The event identifier occurs more than once.",
                    )
                )
            else:
                ids.add(event_id)

            if event_type is None:
                findings.append(
                    AnomalyFinding(
                        "MISSING_EVENT_TYPE",
                        "error",
                        event_id,
                        "An event is missing a usable event type.",
                    )
                )
            elif event_type not in self._known_types:
                candidate_count += 1
                findings.append(
                    AnomalyFinding(
                        "UNRECOGNIZED_EVENT_TYPE",
                        "review",
                        event_id,
                        "Unrecognized event type; manual review required. "
                        "This is not a confirmed incident.",
                    )
                )

            # Only ISO-8601 timestamps are used; other fields are intentionally ignored.
            timestamp = event.get("sent_at")
            if timestamp is None:
                timestamp = event.get("created_at")
            if timestamp is not None:
                parsed: datetime | None = None
                if isinstance(timestamp, str):
                    try:
                        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    except ValueError:
                        pass
                if parsed is None or parsed.tzinfo is None or parsed.utcoffset() is None:
                    findings.append(
                        AnomalyFinding(
                            "INVALID_TIMESTAMP",
                            "warning",
                            event_id,
                            "Timestamp is not an offset-aware ISO-8601 value.",
                        )
                    )
                else:
                    if last_time is not None and parsed < last_time:
                        findings.append(
                            AnomalyFinding(
                                "OUT_OF_ORDER_TIMESTAMP",
                                "review",
                                event_id,
                                "Timestamp precedes an earlier listed event.",
                            )
                        )
                    last_time = parsed

        return AnomalyReport(len(events), tuple(findings), candidate_count)
