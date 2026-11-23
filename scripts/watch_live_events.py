"""Poll authorized simulation events without sending any contacts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from config.settings import Settings
from evaluation.competition_evidence import build_evidence
from integrations.target_api import TargetAPIClient


def arguments() -> argparse.Namespace:
    """Parse bounded polling and explicit simulation-scope arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("build/evidence/watch"))
    parser.add_argument("--checks", type=int, default=3)
    parser.add_argument("--interval", type=float, default=10.0)
    parser.add_argument("--include-eval", action="store_true")
    return parser.parse_args()


def save_new(path: Path, snapshot: dict) -> None:
    """Write a timestamped snapshot without overwriting existing evidence.

    Args:
        path: New evidence file location.
        snapshot: Sanitized evidence data.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(snapshot, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


async def watch(args: argparse.Namespace) -> int:
    """Capture bounded snapshots when event history or budget changes.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Zero after successful read-only polling.

    """
    if not 1 <= args.checks <= 30:
        raise ValueError("--checks must be between 1 and 30")
    if args.interval < 5:
        raise ValueError("--interval must be at least 5 seconds")
    settings = Settings()
    if settings.dry_run:
        raise RuntimeError("Live reads disabled by CASPIANX_DRY_RUN")
    last_identity: tuple[str, int] | None = None
    async with TargetAPIClient(settings) as client:
        for index in range(args.checks):
            session = await client.get_session(args.session)
            if session.scenario_id != "practice" and not args.include_eval:
                raise ValueError("Non-practice sessions require --include-eval")
            if session.scenario_id not in {"practice", "eval"}:
                raise ValueError("Unsupported simulation scenario")
            response = await client.get_events(args.session)
            snapshot = build_evidence(session, response.events)
            identity = (snapshot["event_metadata_sha256"], snapshot["touches_used"])
            if identity != last_identity:
                now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                file_path = args.out_dir / f"{session.session_id}_{now}_{index:02d}.json"
                save_new(file_path, snapshot)
                print(
                    f"CAPTURED | {file_path} | events={snapshot['event_count']} "
                    f"| used={snapshot['touches_used']}/{snapshot['touch_budget']}"
                )
                last_identity = identity
            else:
                print(f"UNCHANGED | check={index + 1} | events={snapshot['event_count']}")
            if index + 1 < args.checks:
                await asyncio.sleep(args.interval)
    print("WATCH COMPLETE | contacts sent=0 | OpenAI calls=0")
    return 0


def main() -> int:
    """Run the bounded watch command and avoid printing secret values."""
    try:
        return asyncio.run(watch(arguments()))
    except (RuntimeError, ValueError, OSError) as error:
        print(f"WATCH FAILED | {type(error).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
