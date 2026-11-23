"""Perform a read-only, offline preflight for the CaspianX repository."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Check:
    """Represent one offline readiness check and its result."""

    name: str
    passed: bool
    detail: str


def run_command(arguments: list[str], root: Path) -> Check:
    """Run a read-only verification command and summarize its exit status."""
    process = subprocess.run(
        arguments,
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    excerpt = (process.stdout + process.stderr).strip().splitlines()
    detail = excerpt[-1] if excerpt else f"exit={process.returncode}"
    return Check(" ".join(arguments[1:]), process.returncode == 0, detail[:250])


def check_git_secrets(root: Path) -> Check:
    """Check that environment files are not tracked in the local Git index."""
    process = subprocess.run(
        ["git", "ls-files", "--cached"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if process.returncode != 0:
        return Check("Git secret tracking", False, "Git index unavailable")
    tracked = [line for line in process.stdout.splitlines() if Path(line).name == ".env"]
    return Check(
        "Git secret tracking",
        not tracked,
        "No .env tracked" if not tracked else "Tracked .env: " + ", ".join(tracked),
    )


def inspect_repository(root: Path, *, run_tests: bool) -> list[Check]:
    """Inspect required files and optionally execute offline quality gates."""
    required = (
        "ARCHITECTURE.md",
        "core/engine.py",
        "core/observation_runner.py",
        "core/recording_session_reader.py",
        "storage/event_store.py",
        "storage/observation_cache.py",
        "storage/observation_cycles.py",
        "storage/session_lease.py",
        "scripts/run_observation.py",
        "scripts/demo_replay.py",
    )
    missing = [name for name in required if not (root / name).is_file()]
    checks = [
        Check(
            "Required architecture files",
            not missing,
            "All present" if not missing else "Missing: " + ", ".join(missing),
        ),
        Check(
            "Python version",
            sys.version_info >= (3, 11),
            sys.version.split()[0],
        ),
        check_git_secrets(root),
    ]
    if run_tests:
        checks.extend(
            [
                run_command([sys.executable, "-m", "ruff", "check", "."], root),
                run_command([sys.executable, "-m", "ruff", "format", "--check", "."], root),
                run_command([sys.executable, "-m", "pytest", "-q"], root),
                run_command([sys.executable, "-m", "scripts.demo_replay"], root),
            ]
        )
    return checks


def main() -> int:
    """Print an offline report and return nonzero if a check fails."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--quick", action="store_true", help="Skip Ruff and pytest")
    parser.add_argument("--json", type=Path, default=None, help="Optional output path")
    options = parser.parse_args()
    checks = inspect_repository(options.root.resolve(), run_tests=not options.quick)
    for check in checks:
        print(f"{'PASS' if check.passed else 'FAIL'} | {check.name}: {check.detail}")
    report = {
        "checks": [asdict(check) for check in checks],
        "passed": all(c.passed for c in checks),
    }
    if options.json is not None:
        options.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("FINAL PREFLIGHT: " + ("PASS" if report["passed"] else "FAIL"))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
