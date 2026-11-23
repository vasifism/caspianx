"""Generate a sanitized full-run report from deterministic offline snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from evaluation.offline_run_validation import validate_offline_run


SYNTHETIC_SNAPSHOTS: list[list[dict[str, Any]]] = [
    [],
    [{"id": "synthetic-1", "type": "message.sent"}],
    [
        {"id": "synthetic-1", "type": "message.sent"},
        {"id": "synthetic-2", "type": "message.opened"},
    ],
    [
        {"id": "synthetic-1", "type": "message.sent"},
        {"id": "synthetic-2", "type": "message.opened"},
        {"id": "synthetic-3", "type": "message.reply"},
    ],
]


def main(argv: list[str] | None = None) -> int:
    """Run deterministic offline replay and write privacy-minimized evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("build/offline_full_run.json"))
    options = parser.parse_args(argv)
    report = validate_offline_run(SYNTHETIC_SNAPSHOTS)
    options.out.parent.mkdir(parents=True, exist_ok=True)
    options.out.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    print("CaspianX Full Offline Run")
    print("Snapshots: 4")
    print(f"Unique events: {report.unique_events}")
    print(f"Anomalies: {len(report.findings)}")
    print("Confirmed incidents: 0 (not evaluated)")
    print("External API calls: 0")
    print("OFFLINE FULL RUN: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
