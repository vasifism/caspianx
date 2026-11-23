"""Print a safe, read-only summary of CaspianX persistence health."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from evaluation.readiness_audit import audit_database


def main() -> int:
    """Audit one SQLite file without connecting to external services."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(os.getenv("CASPIANX_SQLITE_PATH", "data/caspianx.sqlite3")),
        help="Path to existing CaspianX SQLite database.",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON.")
    args = parser.parse_args()
    report = audit_database(args.database)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print("CaspianX Read-Only Readiness Audit")
        print("Database available:", report.database_exists)
        print("SQLite integrity:", "OK" if report.integrity_ok else "NOT VERIFIED")
        for name, count in sorted(report.table_counts.items()):
            print(f"{name}: {count}")
        for status, count in sorted(report.cycle_statuses.items()):
            print(f"Cycles {status}: {count}")
        for finding in report.findings:
            print(f"[{finding.severity}] {finding.code}: {finding.detail}")
        print("Audit:", "PASS" if report.passed else "FAIL")

    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
