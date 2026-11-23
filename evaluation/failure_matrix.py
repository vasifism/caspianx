"""Run deterministic fault-injection checks on SQLite persistence primitives."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory


@dataclass(frozen=True, slots=True)
class FailureMatrixResult:
    """Summarize deterministic, offline durability invariants."""

    rollback_preserved: bool
    deduplication_preserved: bool
    lock_exclusion_preserved: bool
    crash_marker_preserved: bool

    @property
    def passed(self) -> bool:
        """Report success only when all independent invariants hold."""
        return all(
            (
                self.rollback_preserved,
                self.deduplication_preserved,
                self.lock_exclusion_preserved,
                self.crash_marker_preserved,
            )
        )

    def to_dict(self) -> dict[str, bool]:
        """Serialize only boolean results without exposing any event content."""
        return {
            "rollback_preserved": self.rollback_preserved,
            "deduplication_preserved": self.deduplication_preserved,
            "lock_exclusion_preserved": self.lock_exclusion_preserved,
            "crash_marker_preserved": self.crash_marker_preserved,
            "passed": self.passed,
        }


def _initialize(path: Path) -> sqlite3.Connection:
    """Initialize a miniature isolated database for persistence fault tests."""
    db = sqlite3.connect(path, timeout=5, isolation_level=None)
    db.execute(
        "CREATE TABLE events (session_id TEXT, event_id TEXT, event_type TEXT, "
        "PRIMARY KEY (session_id, event_id))"
    )
    db.execute("CREATE TABLE leases (session_id TEXT PRIMARY KEY, token TEXT NOT NULL)")
    db.execute("CREATE TABLE cycles (cycle_id TEXT PRIMARY KEY, status TEXT NOT NULL)")
    return db


def run_failure_matrix() -> FailureMatrixResult:
    """Exercise transaction failure, duplicates, leases, and crash markers.

    This deliberately uses a miniature SQLite schema rather than claiming
    to exercise the production Orchestrator or external APIs.

    Returns:
        Aggregate results of four independent synthetic invariants.

    """
    with TemporaryDirectory(prefix="caspianx_failure_matrix_") as directory:
        path = Path(directory) / "faults.sqlite3"
        with _initialize(path) as connection:
            connection.execute("BEGIN")
            connection.execute("INSERT INTO events VALUES (?, ?, ?)", ("s", "e1", "sent"))
            try:
                connection.execute("INSERT INTO events VALUES (?, ?, ?)", ("s", "e1", "sent"))
            except sqlite3.IntegrityError:
                connection.execute("ROLLBACK")
            else:
                connection.execute("ROLLBACK")
                raise AssertionError("Duplicate insertion was unexpectedly accepted.")

            rollback_preserved = (
                connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0
            )

            connection.execute("INSERT OR IGNORE INTO events VALUES (?, ?, ?)", ("s", "e1", "sent"))
            connection.execute("INSERT OR IGNORE INTO events VALUES (?, ?, ?)", ("s", "e1", "sent"))
            deduplication_preserved = (
                connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 1
            )

            connection.execute("INSERT INTO leases VALUES (?, ?)", ("s", "owner1"))
            with sqlite3.connect(path, timeout=5) as competitor:
                cursor = competitor.execute(
                    "INSERT OR IGNORE INTO leases VALUES (?, ?)", ("s", "owner2")
                )
                lock_exclusion_preserved = cursor.rowcount == 0

            connection.execute("INSERT INTO cycles VALUES (?, ?)", ("cycle1", "running"))

        with sqlite3.connect(path) as restarted:
            crash_marker_preserved = restarted.execute(
                "SELECT status FROM cycles WHERE cycle_id = ?", ("cycle1",)
            ).fetchone() == ("running",)

    return FailureMatrixResult(
        rollback_preserved=rollback_preserved,
        deduplication_preserved=deduplication_preserved,
        lock_exclusion_preserved=lock_exclusion_preserved,
        crash_marker_preserved=crash_marker_preserved,
    )


def failure_matrix_json() -> str:
    """Return a compact safe JSON summary of the offline failure matrix."""
    return json.dumps(run_failure_matrix().to_dict(), sort_keys=True)
