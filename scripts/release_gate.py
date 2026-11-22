"""Make a conservative release decision using local sanitized evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evaluation.release_validation import validate_release
from scripts.evidence_snapshot import read_evidence
from scripts.rehearse_demo import run_rehearsal


def main() -> int:
    """Run offline rehearsal, inspect SQLite, and save a sanitized decision."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/caspianx.sqlite3"))
    parser.add_argument("--out", type=Path, default=Path("build/release_decision.json"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    options = parser.parse_args()
    try:
        rehearsal = run_rehearsal(options.root.resolve())
        evidence = read_evidence(options.db)
        decision = validate_release(rehearsal, evidence)
        options.out.parent.mkdir(parents=True, exist_ok=True)
        options.out.write_text(
            json.dumps(decision.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as error:
        print(f"RELEASE GATE: FAIL ({type(error).__name__})", file=sys.stderr)
        return 1

    for finding in decision.findings:
        print(f"{finding.severity} | {finding.code}: {finding.message}")
    print(f"Evidence saved: {options.out}")
    print("This assesses infrastructure only, not scoring-run success.")
    print("RELEASE GATE: " + ("PASS" if decision.passed else "FAIL"))
    return 0 if decision.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
