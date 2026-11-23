"""Audit CaspianX SQLite persistence without mutating project data."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote


@dataclass(frozen=True, slots=True)
class AuditFinding:
    """Describe one detected condition without revealing sensitive data."""

    severity: str
    code: str
    detail: str


@dataclass(slots=True)
class AuditReport:
    """Summarize read-only database checks and execution metadata."""

    database_exists: bool = False
    integrity_ok: bool = False
    table_counts: dict[str, int] = field(default_factory=dict)
    cycle_statuses: dict[str, int] = field(default_factory=dict)
    findings: list[AuditFinding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return whether the audit found no errors or missing database."""
        return (
            self.database_exists
            and self.integrity_ok
            and not any(item.severity == "ERROR" for item in self.findings)
        )

    def to_dict(self) -> dict[str, object]:
        """Return JSON-serializable report data."""
        return {**asdict(self), "passed": self.passed}


def _parse_utc(value: object) -> datetime | None:
    """Parse an aware timestamp, returning None for malformed input."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def audit_database(
    database_path: str | Path,
    *,
    stale_after: timedelta = timedelta(minutes=5),
    now: datetime | None = None,
) -> AuditReport:
    """Inspect an existing database using a SQLite read-only connection.

    Args:
        database_path: Existing CaspianX SQLite file.
        stale_after: Age used to flag potentially unfinished cycles.
        now: Optional timezone-aware UTC reference time for tests.

    Returns:
        Audit results with only aggregate counts and diagnostic codes.

    Raises:
        ValueError: If the threshold or reference time is invalid.

    """
    if stale_after <= timedelta(0):
        raise ValueError("stale_after must be positive.")

    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None or reference.utcoffset() is None:
        raise ValueError("now must be timezone-aware.")
    reference = reference.astimezone(timezone.utc)

    path = Path(database_path).expanduser()
    report = AuditReport(database_exists=path.is_file())
    if not report.database_exists:
        report.findings.append(
            AuditFinding("ERROR", "DATABASE_MISSING", "Database file does not exist.")
        )
        return report

    # URI mode=ro prevents an accidental database creation or write.
    uri = f"file:{quote(str(path.resolve()), safe='/')}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True, timeout=5) as connection:
            connection.execute("BEGIN")
            result = connection.execute("PRAGMA quick_check").fetchone()
            report.integrity_ok = result is not None and result[0] == "ok"
            if not report.integrity_ok:
                report.findings.append(
                    AuditFinding("ERROR", "SQLITE_INTEGRITY", "SQLite quick_check failed.")
                )

            tables = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            expected = (
                "observation_cycles",
                "observation_cache",
                "observation_analyses",
                "session_execution_leases",
            )
            for table in expected:
                if table not in tables:
                    report.findings.append(
                        AuditFinding("WARNING", "TABLE_ABSENT", f"Table {table} is absent.")
                    )
                    continue
                # Table names come exclusively from a hard-coded allowlist.
                report.table_counts[table] = connection.execute(
                    f'SELECT COUNT(*) FROM "{table}"'
                ).fetchone()[0]

            if "observation_cycles" in tables:
                for status, count in connection.execute(
                    "SELECT status, COUNT(*) FROM observation_cycles GROUP BY status"
                ):
                    report.cycle_statuses[str(status)] = count
                    if status not in {"running", "completed", "failed"}:
                        report.findings.append(
                            AuditFinding("ERROR", "INVALID_CYCLE_STATUS", "Unknown cycle status.")
                        )

                for (started_at,) in connection.execute(
                    "SELECT started_at FROM observation_cycles WHERE status = 'running'"
                ):
                    started = _parse_utc(started_at)
                    if started is None:
                        report.findings.append(
                            AuditFinding(
                                "ERROR",
                                "INVALID_CYCLE_TIMESTAMP",
                                "A running cycle has an invalid UTC timestamp.",
                            )
                        )
                    elif reference - started >= stale_after:
                        report.findings.append(
                            AuditFinding(
                                "WARNING",
                                "STALE_RUNNING_CYCLE",
                                "A running cycle requires owner-liveness review.",
                            )
                        )

            for table in ("observation_cache", "observation_analyses"):
                if table not in tables:
                    continue
                for (value,) in connection.execute(f'SELECT analysis_json FROM "{table}"'):
                    try:
                        decoded = json.loads(value)
                    except (TypeError, ValueError):
                        decoded = None
                    if not isinstance(decoded, dict):
                        report.findings.append(
                            AuditFinding(
                                "ERROR",
                                "INVALID_ANALYSIS_JSON",
                                f"Invalid analysis JSON in {table}.",
                            )
                        )

            if "session_execution_leases" in tables:
                leases = report.table_counts["session_execution_leases"]
                if leases:
                    report.findings.append(
                        AuditFinding(
                            "WARNING",
                            "LEASES_PRESENT",
                            "Execution leases exist; ownership liveness is unknown.",
                        )
                    )

            connection.rollback()
    except sqlite3.DatabaseError:
        report.findings.append(
            AuditFinding("ERROR", "SQLITE_ACCESS", "Unable to inspect SQLite database.")
        )
    return report
