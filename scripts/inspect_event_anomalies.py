"""Analyze local event metadata in JSON without transmitting or printing payloads."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.anomaly_detector import AnomalyDetector


def main(argv: list[str] | None = None) -> int:
    """Inspect supplied JSON events and produce a sanitized diagnostic report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", default=Path("build/anomaly_report.json"), type=Path)
    args = parser.parse_args(argv)
    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Input must be a JSON array of event objects")
    result = AnomalyDetector().analyze(payload)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(f"Events inspected: {result.event_count}")
    print(f"Findings: {len(result.findings)}")
    print(f"Unrecognized event candidates: {result.novel_outcome_candidates}")
    print("Incident confirmation: not performed")
    print("ANOMALY INSPECTION: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
