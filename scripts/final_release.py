"""Run the established CaspianX offline release checks as one command."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ReleaseCheck:
    """Define a reproducible command used by the offline release gate."""

    name: str
    module: str
    arguments: tuple[str, ...] = ()

    def command(self, python: str) -> list[str]:
        """Build a Python-module invocation without shell interpolation."""
        return [python, "-m", self.module, *self.arguments]


def default_checks() -> tuple[ReleaseCheck, ...]:
    """Return the ordered set of non-contacting validation commands."""
    return (
        ReleaseCheck("lint", "ruff", ("check", ".")),
        ReleaseCheck("format", "ruff", ("format", "--check", ".")),
        ReleaseCheck("tests", "pytest", ("-q",)),
        ReleaseCheck(
            "offline_acceptance",
            "scripts.final_acceptance",
            (
                "--out",
                "build/final_acceptance.json",
            ),
        ),
        ReleaseCheck("preflight", "scripts.final_preflight"),
        ReleaseCheck("failure_matrix", "scripts.failure_matrix"),
        ReleaseCheck("audit", "scripts.audit_readiness"),
        ReleaseCheck("recovery", "scripts.inspect_recovery"),
        ReleaseCheck(
            "release_gate",
            "scripts.release_gate",
            (
                "--db",
                "data/caspianx.sqlite3",
                "--out",
                "build/release_decision.json",
            ),
        ),
        ReleaseCheck(
            "rehearsal",
            "scripts.rehearse_demo",
            (
                "--out",
                "build/rehearsal_report.json",
            ),
        ),
        ReleaseCheck(
            "jury_package",
            "scripts.build_jury_package",
            (
                "--out",
                "build/CaspianX_Jury_Materials.zip",
            ),
        ),
        ReleaseCheck(
            "package_inspection",
            "scripts.inspect_jury_package",
            (
                "--zip",
                "build/CaspianX_Jury_Materials.zip",
            ),
        ),
    )


def run_checks(
    checks: tuple[ReleaseCheck, ...],
    *,
    python: str,
    root: Path,
) -> dict[str, Any]:
    """Execute checks sequentially and store only return codes, never output.

    Args:
        checks: Offline validation commands.
        python: Interpreter used for every command.
        root: Current project directory.

    Returns:
        Summary of check names, exit codes, and release status.

    """
    results: list[dict[str, Any]] = []
    for check in checks:
        print(f"RUN | {check.name}", flush=True)
        try:
            outcome = subprocess.run(check.command(python), cwd=root, check=False)
            code = outcome.returncode
        except OSError:
            code = 127
        status = "PASS" if code == 0 else "FAIL"
        print(f"{status} | {check.name}", flush=True)
        results.append({"name": check.name, "exit_code": code, "status": status})
        if code != 0:
            break
    passed = len(results) == len(checks) and all(result["status"] == "PASS" for result in results)
    return {
        "schema_version": 1,
        "mode": "offline_infrastructure_release",
        "status": "PASS" if passed else "FAIL",
        "results": results,
        "scoring_incidents_verified": False,
        "autonomous_social_engineering_verified": False,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the offline release gate and write a minimal machine-readable manifest."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("build/final_release.json"))
    arguments = parser.parse_args(argv)
    root = Path.cwd()
    report = run_checks(default_checks(), python=sys.executable, root=root)
    arguments.out.parent.mkdir(parents=True, exist_ok=True)
    arguments.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"FINAL RELEASE: {report['status']}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
