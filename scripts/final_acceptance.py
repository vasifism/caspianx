"""Run a privacy-preserving final acceptance check on offline event histories."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from evaluation.final_acceptance import assess_snapshots


DEMO_SNAPSHOTS = [
    [],
    [{"id": "demo_001", "type": "message.sent"}],
    [
        {"id": "demo_001", "type": "message.sent"},
        {"id": "demo_002", "type": "message.opened"},
    ],
    [
        {"id": "demo_001", "type": "message.sent"},
        {"id": "demo_002", "type": "message.opened"},
        {"id": "demo_003", "type": "message.reply"},
    ],
]


def _read_snapshots(path: Path) -> Any:
    """Read an offline JSON file, accepting an envelope or a bare list."""
    document = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(document, dict):
        return document["snapshots"]
    return document


def main(argv: list[str] | None = None) -> int:
    """Produce a sanitized acceptance report without invoking external APIs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="Offline snapshots JSON file")
    parser.add_argument("--out", type=Path, default=Path("build/final_acceptance.json"))
    arguments = parser.parse_args(argv)
    try:
        snapshots = _read_snapshots(arguments.input) if arguments.input else DEMO_SNAPSHOTS
        result = assess_snapshots(snapshots)
        arguments.out.parent.mkdir(parents=True, exist_ok=True)
        arguments.out.write_text(
            json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"FINAL ACCEPTANCE: FAIL ({type(error).__name__})", file=sys.stderr)
        return 1
    print(f"Snapshots: {result.snapshot_count}")
    print(f"Unique events: {result.unique_event_count}")
    print(f"Anomalies: {result.anomaly_count}")
    print(f"Novel candidates for review: {result.novel_candidate_count}")
    print("Verified incidents: NOT EVALUATED")
    print("Network and model calls: 0")
    print(f"Evidence: {arguments.out}")
    print(f"FINAL ACCEPTANCE: {result.status}")
    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
