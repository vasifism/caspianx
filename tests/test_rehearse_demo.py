"""Test the offline rehearsal report without executing external services."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.rehearse_demo import run_check, run_rehearsal, select_summary


def test_select_summary_recognizes_success() -> None:
    """Recognize fixed success messages without retaining log contents."""
    assert select_summary("preflight", "key=secret\nFINAL PREFLIGHT: PASS") == (
        "FINAL PREFLIGHT: PASS"
    )


def test_select_summary_does_not_copy_unknown_output() -> None:
    """Avoid exporting arbitrary subprocess output such as credentials."""
    assert select_summary("preflight", "OPENAI_API_KEY=secret") == ("No recognized status")


def test_run_rehearsal_requires_existing_repository(tmp_path: Path) -> None:
    """Reject a path that does not have the expected project structure."""
    with pytest.raises(FileNotFoundError):
        run_rehearsal(tmp_path)


def test_run_check_records_success_without_raw_output(tmp_path: Path) -> None:
    """Keep only an allowlisted success marker in the report."""
    with patch("scripts.rehearse_demo.subprocess.run") as execute:
        execute.return_value.returncode = 0
        execute.return_value.stdout = "secret=example\nAudit: PASS\n"
        execute.return_value.stderr = ""
        result = run_check("readiness_audit", ("-m", "module"), tmp_path)
    assert result["passed"] is True
    assert result["output"] == "Audit: PASS"
    assert "secret" not in str(result)


def test_run_check_reports_nonzero_status(tmp_path: Path) -> None:
    """Report a failed subprocess without copying its raw error output."""
    with patch("scripts.rehearse_demo.subprocess.run") as execute:
        execute.return_value.returncode = 1
        execute.return_value.stdout = ""
        execute.return_value.stderr = "token=example"
        result = run_check("preflight", ("-m", "module"), tmp_path)
    assert result["passed"] is False
    assert "token" not in str(result)
