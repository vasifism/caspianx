"""Test the offline release command without executing actual subprocesses."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.final_release import ReleaseCheck, default_checks, run_checks


def test_default_checks_are_offline() -> None:
    """Exclude any messaging or state-changing simulation command."""
    modules = [check.module for check in default_checks()]
    assert "scripts.practice_contact" not in modules
    assert "scripts.run_observation" not in modules
    assert "scripts.create_practice" not in modules


def test_command_uses_interpreter_without_shell() -> None:
    """Construct a module command using a direct argument vector."""
    check = ReleaseCheck("demo", "scripts.demo_replay", ("--out", "result.json"))
    assert check.command("python3") == [
        "python3",
        "-m",
        "scripts.demo_replay",
        "--out",
        "result.json",
    ]


def test_successful_checks_generate_pass(tmp_path: Path) -> None:
    """Record success without retaining process output."""
    checks = (ReleaseCheck("one", "module.one"), ReleaseCheck("two", "module.two"))
    with patch("scripts.final_release.subprocess.run") as invoke:
        invoke.return_value = SimpleNamespace(returncode=0, stdout="SENSITIVE_DATA")
        report = run_checks(checks, python="python", root=tmp_path)
    assert report["status"] == "PASS"
    assert "SENSITIVE_DATA" not in str(report)
    assert invoke.call_count == 2


def test_failed_check_stops_pipeline(tmp_path: Path) -> None:
    """Stop execution immediately on an unsuccessful release check."""
    checks = (ReleaseCheck("one", "module.one"), ReleaseCheck("two", "module.two"))
    with patch("scripts.final_release.subprocess.run") as invoke:
        invoke.return_value = SimpleNamespace(returncode=1)
        report = run_checks(checks, python="python", root=tmp_path)
    assert report["status"] == "FAIL"
    assert report["results"][0]["exit_code"] == 1
    assert invoke.call_count == 1
