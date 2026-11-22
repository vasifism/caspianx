"""Inspect unresolved outbound attempts before any live conversation restart."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from storage.conversation_repository import ConversationRepository


def main() -> int:
    """Print non-secret ledger statistics and unresolved attempt identifiers."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", required=True)
    parser.add_argument("--db", type=Path, default=Path("build/conversation_practice.sqlite3"))
    args = parser.parse_args()
    with ConversationRepository(args.db) as repository:
        print(json.dumps(repository.snapshot(args.session), indent=2))
        for operation in repository.pending(args.session):
            print(f"UNRESOLVED: {operation.kind} | operation={operation.operation_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
