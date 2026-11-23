"""Test conservative release gating with sanitized synthetic evidence."""

from __future__ import annotations

from copy import deepcopy

import pytest

from evaluation.release_validation import ReleaseDecision, validate_release


@pytest.fixture
def rehearsal() -> dict:
    """Provide a complete, verified offline rehearsal fixture."""
    statuses = {
        "preflight": "FINAL PREFLIGHT: PASS",
        "readiness_audit": "Audit: PASS",
        "recovery_diagnostics": "Recovery inspection: OK",
        "offline_replay": "Offline Replay Demonstration: PASSED",
    }
    return {
        "mode": "offline_only",
        "passed": True,
        "checks": [
            {"name": name, "passed": True, "output": status} for name, status in statuses.items()
        ],
    }


@pytest.fixture
def evidence() -> dict:
    """Provide a healthy aggregate SQLite snapshot fixture."""
    return {
        "database_integrity": "ok",
        "table_counts": {
            "observation_analyses": 4,
            "observation_cache": 1,
            "observation_cycles": 6,
            "session_execution_leases": 0,
        },
        "observation_cycle_statuses": {"completed": 6},
    }


def test_clean_release_passes(rehearsal: dict, evidence: dict) -> None:
    """Accept a complete clean infrastructure release."""
    result = validate_release(rehearsal, evidence)
    assert result.passed
    assert result.findings == ()
    assert "scoring_run_incident" in result.unverified_capabilities


def test_bad_rehearsal_fails(rehearsal: dict, evidence: dict) -> None:
    """Block releases when the rehearsal itself reports failure."""
    rehearsal["passed"] = False
    assert not validate_release(rehearsal, evidence).passed


def test_missing_check_fails(rehearsal: dict, evidence: dict) -> None:
    """Require every expected check rather than only the global flag."""
    rehearsal["checks"].pop()
    assert not validate_release(rehearsal, evidence).passed


def test_spoofed_success_text_fails(rehearsal: dict, evidence: dict) -> None:
    """Reject a failed check even if its output claims success."""
    rehearsal["checks"][0]["passed"] = False
    assert not validate_release(rehearsal, evidence).passed


def test_wrong_success_marker_fails(rehearsal: dict, evidence: dict) -> None:
    """Require an exact, allowlisted success marker."""
    rehearsal["checks"][0]["output"] = "everything looks fine"
    assert not validate_release(rehearsal, evidence).passed


def test_sqlite_integrity_fails(rehearsal: dict, evidence: dict) -> None:
    """Block releases when database integrity is not verified."""
    evidence["database_integrity"] = "malformed"
    assert not validate_release(rehearsal, evidence).passed


def test_missing_table_count_fails(rehearsal: dict, evidence: dict) -> None:
    """Require each expected table's aggregate count."""
    del evidence["table_counts"]["observation_cache"]
    assert not validate_release(rehearsal, evidence).passed


def test_boolean_table_count_rejected(rehearsal: dict, evidence: dict) -> None:
    """Reject booleans masquerading as integer counts."""
    evidence["table_counts"]["observation_cache"] = True
    assert not validate_release(rehearsal, evidence).passed


def test_negative_table_count_rejected(rehearsal: dict, evidence: dict) -> None:
    """Reject impossible negative record counts."""
    evidence["table_counts"]["observation_cycles"] = -1
    assert not validate_release(rehearsal, evidence).passed


def test_active_lease_blocks_release(rehearsal: dict, evidence: dict) -> None:
    """Require independent review of a persisted execution lease."""
    evidence["table_counts"]["session_execution_leases"] = 1
    assert not validate_release(rehearsal, evidence).passed


def test_running_cycle_blocks_release(rehearsal: dict, evidence: dict) -> None:
    """Require review of unfinished observation cycles."""
    evidence["observation_cycle_statuses"] = {"completed": 5, "running": 1}
    assert not validate_release(rehearsal, evidence).passed


def test_unknown_cycle_status_blocks_release(rehearsal: dict, evidence: dict) -> None:
    """Reject unknown persisted cycle state values."""
    evidence["observation_cycle_statuses"] = {"completed": 5, "mystery": 1}
    assert not validate_release(rehearsal, evidence).passed


def test_mismatched_counts_block_release(rehearsal: dict, evidence: dict) -> None:
    """Require aggregate cycle statuses to match table record counts."""
    evidence["observation_cycle_statuses"]["completed"] = 5
    assert not validate_release(rehearsal, evidence).passed


def test_invalid_status_count_blocks_release(rehearsal: dict, evidence: dict) -> None:
    """Reject non-integer status totals."""
    evidence["observation_cycle_statuses"]["completed"] = "six"
    assert not validate_release(rehearsal, evidence).passed


def test_missing_statuses_blocks_release(rehearsal: dict, evidence: dict) -> None:
    """Require a status breakdown rather than assuming clean state."""
    evidence.pop("observation_cycle_statuses")
    assert not validate_release(rehearsal, evidence).passed


def test_input_evidence_is_not_modified(rehearsal: dict, evidence: dict) -> None:
    """Validate copies without mutating source records."""
    before_rehearsal = deepcopy(rehearsal)
    before_evidence = deepcopy(evidence)
    validate_release(rehearsal, evidence)
    assert rehearsal == before_rehearsal
    assert evidence == before_evidence


def test_release_report_contains_no_raw_inputs(rehearsal: dict, evidence: dict) -> None:
    """Avoid embedding secret-like arbitrary fields into release reports."""
    rehearsal["secret"] = "CANARY_REHEARSAL_SECRET"
    evidence["secret"] = "CANARY_DATABASE_SECRET"
    result = validate_release(rehearsal, evidence)
    report = str(result.to_dict())
    assert "CANARY_REHEARSAL_SECRET" not in report
    assert "CANARY_DATABASE_SECRET" not in report
    assert isinstance(result, ReleaseDecision)


def test_proven_capabilities_not_claimed_on_failure(rehearsal: dict, evidence: dict) -> None:
    """Only claim verified capabilities when the gate passes."""
    evidence["database_integrity"] = "error"
    assert validate_release(rehearsal, evidence).proven_capabilities == ()
