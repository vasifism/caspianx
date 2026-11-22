"""Collect real authorized simulation metadata without sending contacts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from config.settings import Settings
from evaluation.competition_evidence import build_evidence
from integrations.target_api import TargetAPIClient


def arguments() -> argparse.Namespace:
    """Parse explicit read-only evidence collection arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", help="Existing simulation session ID")
    parser.add_argument("--list", action="store_true", help="List accessible sessions")
    parser.add_argument("--out", type=Path, help="New JSON evidence path")
    parser.add_argument(
        "--include-eval",
        action="store_true",
        help="Explicitly permit read-only retrieval of an eval session",
    )
    return parser.parse_args()


def write_new_json(path: Path, data: dict) -> None:
    """Atomically refuse to overwrite an existing evidence snapshot.

    Args:
        path: Destination path for a new evidence file.
        data: Sanitized snapshot to serialize.

    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


async def run(args: argparse.Namespace) -> int:
    """Read only selected simulator data and write sanitized evidence.

    Args:
        args: Parsed command line arguments.

    Returns:
        Process status code.

    """
    if args.list == bool(args.session):
        raise ValueError("Specify exactly one of --list or --session")
    if args.session and args.out is None:
        raise ValueError("--out is required when --session is supplied")
    if args.out is not None and args.out.exists():
        raise FileExistsError("Evidence already exists: choose another --out")
    settings = Settings()
    if settings.dry_run:
        raise RuntimeError("CASPIANX_DRY_RUN=true prevents live API reads")
    async with TargetAPIClient(settings) as client:
        if args.list:
            sessions = await client.list_sessions()
            for item in sessions:
                if item.scenario_id == "practice" or args.include_eval:
                    print(
                        f"{item.session_id} | {item.scenario_id} | "
                        f"{item.status} | used={item.touches_used}/{item.touch_budget}"
                    )
            print("Read-only session list: OK")
            return 0
        session = await client.get_session(args.session)
        if session.scenario_id != "practice" and not args.include_eval:
            raise ValueError("Eval/non-practice requires explicit --include-eval")
        reply = await client.get_events(args.session)
        snapshot = build_evidence(session, reply.events)
        write_new_json(args.out, snapshot)
        print("LIVE EVIDENCE: SAVED")
        print(f"Session: {session.session_id}")
        print(f"Events: {snapshot['event_count']}")
        print(f"Contacts: {snapshot['touches_used']}/{snapshot['touch_budget']}")
        print(f"Evidence: {args.out}")
        print("Messages sent: 0 | OpenAI calls: 0")
        return 0


def main() -> int:
    """Execute the read-only collector and surface safe error messages."""
    args = arguments()
    try:
        return asyncio.run(run(args))
    except (RuntimeError, ValueError, FileExistsError, OSError) as error:
        print(f"EVIDENCE COLLECTION FAILED: {type(error).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
