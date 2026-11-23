"""Test the non-mutating CaspianX readiness audit on synthetic databases."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from evaluation.readiness_audit import audit_database


NOW = datetime(2026, 11, 21, 15, tzinfo=timezone.utc)


def create_database(path: Path) -> None:
    """Create representative persistence tables for audit tests."""
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE observation_cycles (
                cycle_id TEXT PRIMARY KEY, status TEXT, started_at TEXT
            );
            CREATE TABLE observation_cache (
                fingerprint TEXT PRIMARY KEY, analysis_json TEXT
            );
            CREATE TABLE observation_analyses (
                analysis_id TEXT PRIMARY KEY, analysis_json TEXT
            );
            CREATE TABLE session_execution_leases (
                session_id TEXT PRIMARY KEY, owner_token TEXT
            );
            """
        )


def test_clean_database_passes(tmp_path: Path) -> None:
    """Confirm integrity and expected table availability."""
    path = tmp_path / "clean.sqlite3"
    create_database(path)
    report = audit_database(path, now=NOW)
    assert report.passed
    assert report.integrity_ok
    assert len(report.table_counts) == 4
    assert report.findings == []


def test_missing_database_is_not_created(tmp_path: Path) -> None:
    """Report missing files without creating them."""
    path = tmp_path / "missing.sqlite3"
    report = audit_database(path, now=NOW)
    assert not report.passed
    assert not path.exists()
    assert report.findings[0].code == "DATABASE_MISSING"


def test_old_running_cycle_is_warning(tmp_path: Path) -> None:
    """Flag potentially abandoned work without declaring a failure."""
    path = tmp_path / "old.sqlite3"
    create_database(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO observation_cycles VALUES (?, ?, ?)",
            ("cycle-1", "running", (NOW - timedelta(minutes=10)).isoformat()),
        )
    report = audit_database(path, now=NOW)
    assert report.passed
    assert any(item.code == "STALE_RUNNING_CYCLE" for item in report.findings)
    assert report.cycle_statuses == {"running": 1}


def test_recent_cycle_is_not_stale(tmp_path: Path) -> None:
    """Avoid false stale warnings for recent running operations."""
    path = tmp_path / "recent.sqlite3"
    create_database(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO observation_cycles VALUES (?, ?, ?)",
            ("cycle-1", "running", (NOW - timedelta(minutes=1)).isoformat()),
        )
    report = audit_database(path, now=NOW)
    assert not any(item.code == "STALE_RUNNING_CYCLE" for item in report.findings)


def test_invalid_cycle_status_fails(tmp_path: Path) -> None:
    """Detect cycle states outside the documented lifecycle."""
    path = tmp_path / "status.sqlite3"
    create_database(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO observation_cycles VALUES (?, ?, ?)",
            ("cycle-1", "unknown", NOW.isoformat()),
        )
    report = audit_database(path, now=NOW)
    assert not report.passed
    assert any(item.code == "INVALID_CYCLE_STATUS" for item in report.findings)


def test_corrupt_analysis_json_fails(tmp_path: Path) -> None:
    """Reject invalid structured-analysis cache records."""
    path = tmp_path / "cache.sqlite3"
    create_database(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO observation_cache VALUES (?, ?)",
            ("key", "not-json"),
        )
    report = audit_database(path, now=NOW)
    assert not report.passed
    assert any(item.code == "INVALID_ANALYSIS_JSON" for item in report.findings)


def test_valid_analysis_json_passes(tmp_path: Path) -> None:
    """Accept structured JSON dictionaries in analysis tables."""
    path = tmp_path / "valid-json.sqlite3"
    create_database(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO observation_cache VALUES (?, ?)",
            ("key", json.dumps({"summary": "No events."})),
        )
    assert audit_database(path, now=NOW).passed


def test_lease_is_warning_without_token_exposure(tmp_path: Path) -> None:
    """Report existing ownership without exposing the secret token."""
    path = tmp_path / "leases.sqlite3"
    create_database(path)
    token = "confidential-owner-token"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO session_execution_leases VALUES (?, ?)",
            ("practice-001", token),
        )
    report = audit_database(path, now=NOW)
    assert report.passed
    assert any(item.code == "LEASES_PRESENT" for item in report.findings)
    assert token not in json.dumps(report.to_dict())


def test_partial_schema_uses_warnings(tmp_path: Path) -> None:
    """Identify unavailable optional schemas without mutating the database."""
    path = tmp_path / "partial.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE unrelated (value TEXT)")
    report = audit_database(path, now=NOW)
    assert report.passed
    assert sum(item.code == "TABLE_ABSENT" for item in report.findings) == 4


def test_invalid_time_arguments(tmp_path: Path) -> None:
    """Reject impossible thresholds and timezone-naive timestamps."""
    with pytest.raises(ValueError):
        audit_database(tmp_path / "missing.sqlite3", stale_after=timedelta())
    with pytest.raises(ValueError):
        audit_database(tmp_path / "missing.sqlite3", now=datetime(2026, 11, 21))


def test_audit_does_not_change_database(tmp_path: Path) -> None:
    """Verify that performing an audit leaves the database bytes unchanged."""
    path = tmp_path / "unchanged.sqlite3"
    create_database(path)
    before = path.read_bytes()
    audit_database(path, now=NOW)
    assert path.read_bytes() == before
