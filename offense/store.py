"""Persist attack-run outcomes in a durable, queryable SQLite store."""

from __future__ import annotations

import json
import os
import sqlite3
import statistics
import time
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  ts             REAL,
  scenario       TEXT,
  target         TEXT,
  incident       INTEGER,
  objective      TEXT,
  evidence       TEXT,
  touches        INTEGER,
  final_suspicion REAL,
  tried_topics   TEXT,
  thread         TEXT,
  claims         TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_target ON runs(target);
CREATE INDEX IF NOT EXISTS idx_runs_incident ON runs(incident);
"""


class SQLiteStore:
    """Store and query attack-run outcomes in a WAL-mode SQLite database."""

    def __init__(self, path: str = "state/runs.db") -> None:
        """Create the store and ensure its schema exists.

        Args:
            path: Filesystem path to the SQLite database.

        """
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.path = path
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        """Open a WAL-mode connection with row access by name.

        Returns:
            A configured SQLite connection.

        """
        conn = sqlite3.connect(self.path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def record_run(
        self, result: dict[str, Any], thread: list | None = None, claims: list | None = None
    ) -> int:
        """Insert one completed run and return its row id.

        Args:
            result: The run result summary.
            thread: The full turn-by-turn thread.
            claims: Claims asserted during the run.

        Returns:
            The new row's primary key.

        """
        with self._conn() as conn:
            cursor = conn.execute(
                "INSERT INTO runs (ts, scenario, target, incident, objective, evidence,"
                " touches, final_suspicion, tried_topics, thread, claims)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    time.time(),
                    result.get("scenario", ""),
                    result.get("target", ""),
                    1 if result.get("incident") else 0,
                    result.get("objective", ""),
                    result.get("evidence", ""),
                    result.get("touches", 0),
                    result.get("final_suspicion", 0.0),
                    json.dumps(result.get("tried_topics", [])),
                    json.dumps(thread or []),
                    json.dumps(claims or []),
                ),
            )
            return cursor.lastrowid

    def winning_openers(self, target_id: str, limit: int = 5) -> list[dict]:
        """Return past incident-reaching runs for a target, fewest touches first.

        Args:
            target_id: The target to filter by.
            limit: Maximum number of rows to return.

        Returns:
            A list of run rows as dictionaries.

        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT target, objective, touches, tried_topics FROM runs"
                " WHERE target=? AND incident=1 ORDER BY touches ASC LIMIT ?",
                (target_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def stats(self, scenario: str | None = None) -> dict[str, Any]:
        """Summarise incident rate and median contacts-to-incident.

        Args:
            scenario: Restrict to one scenario, or aggregate all when ``None``.

        Returns:
            A summary with overall and per-target figures.

        """
        query = "SELECT target, incident, touches FROM runs"
        args: tuple = ()
        if scenario:
            query += " WHERE scenario=?"
            args = (scenario,)
        with self._conn() as conn:
            rows = [dict(row) for row in conn.execute(query, args).fetchall()]
        total = len(rows)
        hits = [row for row in rows if row["incident"]]
        by_target: dict[str, dict] = {}
        for row in rows:
            bucket = by_target.setdefault(
                row["target"], {"runs": 0, "incidents": 0, "touches": []}
            )
            bucket["runs"] += 1
            if row["incident"]:
                bucket["incidents"] += 1
                bucket["touches"].append(row["touches"])
        for bucket in by_target.values():
            touches = bucket.pop("touches")
            bucket["median_touches_to_incident"] = (
                round(statistics.median(touches), 1) if touches else None
            )
        return {
            "runs": total,
            "incident_rate": round(len(hits) / total, 2) if total else 0.0,
            "median_touches_to_incident": (
                round(statistics.median([row["touches"] for row in hits]), 1) if hits else None
            ),
            "by_target": by_target,
        }
