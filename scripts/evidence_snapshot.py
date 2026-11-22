"""Export a privacy-minimized read-only SQLite evidence snapshot."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any


ALLOWED_TABLES = (
    "observation_analyses",
    "observation_cache",
    "observation_cycles",
    "session_execution_leases",
)


def read_evidence(db_path: Path) -> dict[str, Any]:
    """Count known records and summarize statuses without exporting content."""
    if not db_path.is_file():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")
    connection = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        existing = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ALLOWED_TABLES
            if table in existing
        }
        cycle_statuses: dict[str, int] = {}
        if "observation_cycles" in existing:
            cycle_statuses = {
                str(status): int(count)
                for status, count in connection.execute(
                    "SELECT status, COUNT(*) FROM observation_cycles GROUP BY status"
                )
            }
        return {
            "database_integrity": integrity,
            "table_counts": counts,
            "observation_cycle_statuses": cycle_statuses,
            "contains_raw_event_text": False,
            "note": "Aggregate counts only; no message bodies, keys or event payloads exported.",
        }
    finally:
        connection.close()


def main() -> int:
    """Write a sanitized local evidence JSON from an existing database."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/caspianx.sqlite3"))
    parser.add_argument("--out", type=Path, default=Path("demo_evidence.json"))
    arguments = parser.parse_args()
    try:
        snapshot = read_evidence(arguments.db)
        arguments.out.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    except (OSError, sqlite3.Error) as error:
        print(f"Evidence snapshot failed: {type(error).__name__}: {error}")
        return 1
    print(f"Evidence snapshot written: {arguments.out}")
    print("No message bodies, tokens, or person-level events exported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
