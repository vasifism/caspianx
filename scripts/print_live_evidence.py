"""Summarize recorded real-session evidence without sensitive contents."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from evaluation.competition_evidence import validate_evidence


def summarize(path: Path) -> dict:
    """Validate and summarize one immutable live evidence JSON file.

    Args:
        path: Existing evidence JSON file.

    Returns:
        Non-sensitive event-type counts and session metadata.

    """
    data = validate_evidence(json.loads(path.read_text(encoding="utf-8")))
    counts = Counter(event["type"] for event in data["events"])
    return {
        "session_id": data["session_id"],
        "scenario_id": data["scenario_id"],
        "event_count": data["event_count"],
        "event_type_counts": dict(sorted(counts.items())),
        "touches_used": data["touches_used"],
        "remaining_touches": data["remaining_touches"],
        "confirmed_incident": "NOT VERIFIED",
        "evidence_sha256": data["event_metadata_sha256"],
    }


def main() -> int:
    """Print a safe JSON summary of saved live evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.evidence), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
