"""Inspect saved scenario and session snapshots without contacting targets."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from core.scoring_window_readiness import assess_scenarios, assess_session


def parse_args() -> argparse.Namespace:
    """Read input paths for an offline scenario and session readiness audit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", type=Path, help="Official GET /scenarios JSON array")
    parser.add_argument("--sessions", type=Path, help="Official GET /sessions JSON array")
    return parser.parse_args()


def main() -> int:
    """Print derived constraints while making no API or OpenAI calls."""
    args = parse_args()
    if not args.scenarios and not args.sessions:
        raise SystemExit("Specify --scenarios and/or --sessions")
    result: dict[str, object] = {"mode": "offline_read_only", "contacts_sent": 0}
    if args.scenarios:
        scenarios = json.loads(args.scenarios.read_text(encoding="utf-8"))
        if isinstance(scenarios, dict):
            scenarios = scenarios["scenarios"]
        result["scenario_discovery"] = assess_scenarios(scenarios)
    if args.sessions:
        sessions = json.loads(args.sessions.read_text(encoding="utf-8"))
        if isinstance(sessions, dict):
            sessions = sessions["sessions"]
        result["session_assessments"] = [asdict(assess_session(s)) for s in sessions]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
