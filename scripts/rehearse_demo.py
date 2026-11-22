"""Run a deterministic offline technical rehearsal and save its evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("preflight", ("-m", "scripts.final_preflight")),
    ("readiness_audit", ("-m", "scripts.audit_readiness")),
    ("recovery_diagnostics", ("-m", "scripts.inspect_recovery")),
)


def run_check(name: str, arguments: tuple[str, ...], root: Path) -> dict[str, Any]:
    """Run a local verification step and retain sanitized console output.

    Args:
        name: Stable identifier for the check.
        arguments: Python module and its arguments.
        root: Repository directory.

    Returns:
        Status, duration-independent command description, and safe output.

    """
    try:
        completed = subprocess.run(
            [sys.executable, *arguments],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {
            "name": name,
            "passed": False,
            "output": f"Execution failed: {type(error).__name__}",
        }

    # Do not save stdout verbatim: external tools could unexpectedly print secrets.
    output = completed.stdout + "\n" + completed.stderr
    summary = select_summary(name, output)
    return {"name": name, "passed": completed.returncode == 0, "output": summary}


def select_summary(name: str, output: str) -> str:
    """Allowlist safe status lines instead of exporting raw process logs.

    Args:
        name: Check being summarized.
        output: Raw subprocess output, used only for matching fixed phrases.

    Returns:
        A small, non-sensitive status summary.

    """
    if name == "preflight":
        markers = ("FINAL PREFLIGHT: PASS", "FINAL PREFLIGHT: FAIL")
    elif name == "readiness_audit":
        markers = ("Audit: PASS", "Audit: FAIL")
    elif name == "recovery_diagnostics":
        markers = ("Recovery inspection: OK",)
    elif name == "offline_replay":
        markers = ("Offline Replay Demonstration: PASSED",)
    else:
        markers = ()
    return next((marker for marker in markers if marker in output), "No recognized status")


def run_rehearsal(root: Path) -> dict[str, Any]:
    """Execute the complete offline rehearsal from an existing repository.

    Args:
        root: Root directory containing the CaspianX scripts.

    Returns:
        Structured outcomes without messages, API responses, or credentials.

    Raises:
        FileNotFoundError: If the project layout is not recognized.

    """
    if not (root / "scripts" / "final_preflight.py").is_file():
        raise FileNotFoundError("CaspianX final_preflight.py was not found.")

    results = [run_check(name, args, root) for name, args in CHECKS]
    # Offline replay is already covered by preflight, but is repeated here
    # so it can be shown live during the five-minute demonstration.
    results.append(run_check("offline_replay", ("-m", "scripts.demo_replay"), root))
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "offline_only",
        "checks": results,
        "passed": all(item["passed"] for item in results),
        "limitations": [
            "Offline checks do not establish successful scoring incidents.",
            "Synthetic events are not real AI-twin reactions.",
        ],
    }


def main() -> int:
    """Run the offline rehearsal and optionally write sanitized JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=None)
    options = parser.parse_args()
    try:
        report = run_rehearsal(options.root.resolve())
    except (OSError, ValueError) as error:
        print(f"REHEARSAL: FAIL ({type(error).__name__})")
        return 1

    for item in report["checks"]:
        status = "PASS" if item["passed"] else "FAIL"
        print(f"{status} | {item['name']}: {item['output']}")

    if options.out is not None:
        options.out.parent.mkdir(parents=True, exist_ok=True)
        options.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Sanitized evidence written to: {options.out}")

    print("REHEARSAL: " + ("PASS" if report["passed"] else "FAIL"))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
