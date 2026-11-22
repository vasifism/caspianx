"""Show new event metadata between two immutable evidence snapshots."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.live_evidence_diff import compare_snapshots, load_snapshot


def main() -> int:
    """Compare two snapshots and optionally export the comparison."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = compare_snapshots(load_snapshot(args.before), load_snapshot(args.after))
    encoded = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    print(encoded, end="")
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8") as output:
            output.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
