"""Test the isolated SQLite fault-injection rehearsal."""

from __future__ import annotations

import json

from evaluation.failure_matrix import (
    FailureMatrixResult,
    failure_matrix_json,
    run_failure_matrix,
)
from scripts.failure_matrix import main


def test_failure_matrix_passes() -> None:
    """Check the four synthetic durability guarantees."""
    result = run_failure_matrix()
    assert result.passed
    assert result.rollback_preserved
    assert result.deduplication_preserved
    assert result.lock_exclusion_preserved
    assert result.crash_marker_preserved


def test_failure_matrix_serialization() -> None:
    """Serialize the synthetic checks as booleans only."""
    value = json.loads(failure_matrix_json())
    assert value["passed"] is True
    assert set(value) == {
        "rollback_preserved",
        "deduplication_preserved",
        "lock_exclusion_preserved",
        "crash_marker_preserved",
        "passed",
    }


def test_failed_invariant_marks_failure() -> None:
    """Fail the aggregate if even one invariant fails."""
    result = FailureMatrixResult(True, True, False, True)
    assert not result.passed
    assert result.to_dict()["passed"] is False


def test_failure_matrix_cli(capsys) -> None:
    """Return a zero exit status for the deterministic offline matrix."""
    assert main() == 0
    assert "FAILURE MATRIX: PASS" in capsys.readouterr().out
