"""Audit supplied source-backed professional facts without web crawling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from research.public_fact_registry import load_registry, summarize_subject


def parse_args() -> argparse.Namespace:
    """Parse the source registry and subject to inspect."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--subject", required=True)
    return parser.parse_args()


def main() -> int:
    """Print only registry data with explicit source provenance."""
    args = parse_args()
    output = summarize_subject(load_registry(args.registry), args.subject)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
