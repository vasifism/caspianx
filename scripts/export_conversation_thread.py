"""Produce a local conversation transcript without sending network requests."""

from __future__ import annotations

import argparse
from pathlib import Path

from evaluation.conversation_thread_export import export_thread, render_markdown


def parse_args() -> argparse.Namespace:
    """Parse one local export request."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--conversation", required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    """Write a local thread to a new markdown file without overwriting evidence."""
    args = parse_args()
    thread = export_thread(args.db, args.conversation)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as file:
        file.write(render_markdown(thread))
    print(f"THREAD EXPORTED | {args.out} | verified incidents=NOT VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
