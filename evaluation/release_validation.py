"""Validate a release from independently produced, sanitized evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ReleaseFinding:
    """Represent one non-sensitive release validation finding."""

    code: str
    severity: str
    message: str


@dataclass(frozen=True, slots=True)
class ReleaseDecision:
    """Represent a conservative, evidence-based engineering release decision."""

    passed: bool
    findings: tuple[ReleaseFinding, ...]
    proven_capabilities: tuple[str, ...]
    unverified_capabilities: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Produce a JSON-safe document without embedding raw input evidence."""
        return {
            "passed": self.passed,
            "findings": [
                {"code": item.code, "severity": item.severity, "message": item.message}
                for item in self.findings
            ],
            "proven_capabilities": list(self.proven_capabilities),
            "unverified_capabilities": list(self.unverified_capabilities),
        }


def _has_success(checks: object, name: str) -> bool:
    """Require one explicitly passed check with a recognized safe status."""
    if not isinstance(checks, list):
        return False
    expected = {
        "preflight": "FINAL PREFLIGHT: PASS",
        "readiness_audit": "Audit: PASS",
        "recovery_diagnostics": "Recovery inspection: OK",
        "offline_replay": "Offline Replay Demonstration: PASSED",
    }
    return any(
        isinstance(check, dict)
        and check.get("name") == name
        and check.get("passed") is True
        and check.get("output") == expected[name]
        for check in checks
    )


def validate_release(
    rehearsal: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> ReleaseDecision:
    """Assess readiness without treating synthetic runs as real incidents.

    Args:
        rehearsal: Sanitized result from scripts.rehearse_demo.
        evidence: Aggregate result from scripts.evidence_snapshot.

    Returns:
        Decision with actionable status codes and explicit limitations.

    """
    findings: list[ReleaseFinding] = []
    checks = rehearsal.get("checks")
    if rehearsal.get("mode") != "offline_only" or rehearsal.get("passed") is not True:
        findings.append(
            ReleaseFinding("REHEARSAL_NOT_PASSED", "ERROR", "Offline rehearsal is not verified.")
        )
    for name in ("preflight", "readiness_audit", "recovery_diagnostics", "offline_replay"):
        if not _has_success(checks, name):
            findings.append(
                ReleaseFinding(
                    "CHECK_MISSING_" + name.upper(),
                    "ERROR",
                    f"Required offline check {name} has no verified success result.",
                )
            )

    if evidence.get("database_integrity") != "ok":
        findings.append(
            ReleaseFinding("SQLITE_INTEGRITY", "ERROR", "SQLite integrity is not verified.")
        )

    counts = evidence.get("table_counts")
    if not isinstance(counts, dict):
        counts = {}
    required = (
        "observation_analyses",
        "observation_cache",
        "observation_cycles",
        "session_execution_leases",
    )
    for table in required:
        value = counts.get(table)
        if type(value) is not int or value < 0:
            findings.append(
                ReleaseFinding(
                    "INVALID_TABLE_COUNT", "ERROR", f"Invalid or missing count: {table}."
                )
            )
    leases = counts.get("session_execution_leases")
    if type(leases) is int and leases > 0:
        findings.append(
            ReleaseFinding(
                "LEASE_REQUIRES_REVIEW",
                "ERROR",
                "At least one persisted lease requires independent owner verification.",
            )
        )

    statuses = evidence.get("observation_cycle_statuses")
    if not isinstance(statuses, dict):
        findings.append(
            ReleaseFinding("CYCLE_STATUSES_MISSING", "ERROR", "Cycle statuses unavailable.")
        )
    else:
        for name, count in statuses.items():
            if name not in {"running", "completed", "failed"}:
                findings.append(
                    ReleaseFinding("UNKNOWN_CYCLE_STATUS", "ERROR", "Unknown cycle status.")
                )
            if type(count) is not int or count < 0:
                findings.append(
                    ReleaseFinding("INVALID_CYCLE_COUNT", "ERROR", "Invalid cycle count.")
                )
        if statuses.get("running", 0):
            findings.append(
                ReleaseFinding("RUNNING_CYCLES", "ERROR", "Running cycles require review.")
            )
        total = counts.get("observation_cycles")
        if type(total) is int and all(type(v) is int for v in statuses.values()):
            if sum(statuses.values()) != total:
                findings.append(
                    ReleaseFinding(
                        "CYCLE_COUNT_MISMATCH", "ERROR", "Cycle counts are inconsistent."
                    )
                )

    return ReleaseDecision(
        passed=not any(item.severity == "ERROR" for item in findings),
        findings=tuple(findings),
        proven_capabilities=(
            "offline_replay",
            "sqlite_integrity",
            "rehearsal_preflight",
        )
        if not findings
        else (),
        unverified_capabilities=(
            "live_nonempty_event_history",
            "autonomous_multi_contact_execution",
            "scoring_run_incident",
            "external_service_availability_at_scoring_time",
        ),
    )
