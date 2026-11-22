"""Check the offline final-handoff utilities without accessing services."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts.evidence_snapshot import read_evidence
from scripts.final_preflight import inspect_repository


def test_snapshot_excludes_private_payloads(tmp_path: Path) -> None:
    """Export only aggregate counts from an intentionally sensitive database."""
    db = tmp_path / "sample.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE observation_analyses (analysis_json TEXT NOT NULL)")
        conn.execute(
            "INSERT INTO observation_analyses VALUES (?)",
            ('{"private":"DO_NOT_EXPORT"}',),
        )
        conn.execute("CREATE TABLE observation_cycles (status TEXT NOT NULL)")
        conn.execute("INSERT INTO observation_cycles VALUES ('completed')")
    snapshot = read_evidence(db)
    assert snapshot["table_counts"]["observation_analyses"] == 1
    assert snapshot["observation_cycle_statuses"] == {"completed": 1}
    assert "DO_NOT_EXPORT" not in str(snapshot)


def test_missing_database_is_rejected(tmp_path: Path) -> None:
    """Reject a nonexistent database without creating a replacement."""
    path = tmp_path / "missing.sqlite3"
    with pytest.raises(FileNotFoundError):
        read_evidence(path)
    assert not path.exists()


def test_quick_preflight_checks_required_sources(tmp_path: Path) -> None:
    """Report missing project files without running quality tools."""
    checks = inspect_repository(tmp_path, run_tests=False)
    required = next(check for check in checks if check.name == "Required architecture files")
    assert required.passed is False
    assert "ARCHITECTURE.md" in required.detail


def test_unknown_tables_do_not_leak_rows(tmp_path: Path) -> None:
    """Exclude arbitrary tables that could hold confidential content."""
    path = tmp_path / "secret.sqlite3"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE secrets (value TEXT)")
        conn.execute("INSERT INTO secrets VALUES ('NEVER_INCLUDE')")
    snapshot = read_evidence(path)
    assert "NEVER_INCLUDE" not in str(snapshot)
    assert snapshot["table_counts"] == {}
