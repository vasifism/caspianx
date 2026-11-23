"""Produce a fact-checked, metadata-only thread brief for the jury."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from evaluation.live_evidence_diff import load_snapshot


def render(snapshot: dict) -> str:
    """Render a thread brief without inventing conversations or incidents.

    Args:
        snapshot: Validated redacted live evidence.

    Returns:
        Markdown summary clearly labeling the unavailable content.

    """
    counts = Counter(event["type"] for event in snapshot["events"])
    lines = [
        "# CaspianX — Real Session Evidence Brief",
        "",
        f"- Session: `{snapshot['session_id']}`",
        f"- Scenario: `{snapshot['scenario_id']}`",
        f"- Captured (UTC): {snapshot['captured_at_utc']}",
        f"- Used contacts: {snapshot['touches_used']} / {snapshot['touch_budget']}",
        f"- Events returned: {snapshot['event_count']}",
        "- Confirmed incident: **NOT VERIFIED**",
        "",
        "## Observed event timeline (metadata only)",
        "",
    ]
    if not snapshot["events"]:
        lines.append("No API events were returned. No reaction can be inferred.")
    else:
        for position, event in enumerate(snapshot["events"], start=1):
            label = event["type"].replace("`", "")
            event_id = event.get("id", "unknown")
            lines.append(f"{position}. `{event_id}` — `{label}`")
    lines.extend(
        [
            "",
            "## Event type counts",
            "",
        ]
    )
    for event_type, count in sorted(counts.items()):
        lines.append(f"- `{event_type}`: {count}")
    lines.extend(
        [
            "",
            "## Evidence limitations",
            "",
            "This brief does not include message bodies or target replies.",
            "It is not a rendered real thread and does not establish an incident.",
            "For the jury's real-thread criterion, use the official simulator",
            "turn-by-turn replay and cite its actual run/session identifier.",
            "Never present synthetic messages as live scoring-run evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    """Build one immutable Markdown brief from live evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    snapshot = load_snapshot(args.evidence)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as file:
        file.write(render(snapshot))
    print(f"THREAD BRIEF: SAVED | {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
