"""Run a bounded, transparent, adaptive conversation in practice or offline."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from agents.adaptive_dialogue_agent import AdaptiveDialogueAgent
from core.conversation_manager import ConversationManager
from scripts.practice_autonomous_conversation import OfflineConversationTransport
from storage.conversation_repository import ConversationRepository


class AdaptiveOfflineTransport(OfflineConversationTransport):
    """Provide a deterministic multi-turn clarification for offline testing."""

    async def turn(self, conversation_id: str, line: str, key: str) -> dict[str, Any]:
        """Provide a clarification, then an acknowledgment, then a closing reply."""
        self.sent_lines.append(line)
        count = len(self.sent_lines)
        responses = (
            "Who are you, and what is this about?",
            "Understood. The connection is functioning.",
            "Thanks, goodbye.",
        )
        return {
            "persona_says": responses[min(count - 1, 2)],
            "ended": count >= 3,
            "events": [],
        }


def parse_args() -> argparse.Namespace:
    """Parse a reproducible offline or explicitly authorized practice invocation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="offline_adaptive_01")
    parser.add_argument("--target", default="julius")
    parser.add_argument("--db", type=Path, default=Path("build/adaptive_conversations.sqlite3"))
    parser.add_argument("--max-turns", type=int, default=3)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--confirm-practice-contact",
        action="store_true",
        help="Explicitly acknowledge that a live PRACTICE conversation costs one touch",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> dict[str, object]:
    """Run the conversation and return a measured local status summary."""
    agent = AdaptiveDialogueAgent(max_agent_lines=args.max_turns)
    if args.live:
        if not args.confirm_practice_contact:
            raise ValueError("Live mode requires --confirm-practice-contact")
        from config.settings import Settings
        from integrations.conversation_transport import Revel8ConversationTransport

        settings = Settings()
        if settings.dry_run or not args.session.startswith("s_"):
            raise ValueError("Live mode requires an actual practice session and dry_run=false")
        if settings.team_key is None:
            raise ValueError("Missing CASPIANX_TEAM_KEY")
        transport = Revel8ConversationTransport(
            settings.team_key.get_secret_value(),
            settings.target_api_base_url,
            timeout=settings.http_timeout_seconds,
        )
        with ConversationRepository(args.db) as repository:
            async with transport:
                result = await ConversationManager(
                    transport, repository, agent, max_turns=args.max_turns
                ).run(args.session, args.target)
            local_summary = repository.snapshot(args.session)
    else:
        transport = AdaptiveOfflineTransport()
        with ConversationRepository(args.db) as repository:
            result = await ConversationManager(
                transport, repository, agent, max_turns=args.max_turns
            ).run(args.session, args.target)
            local_summary = repository.snapshot(args.session)
    return {
        "conversation_id": result.conversation_id,
        "status": result.status,
        "turns_sent": result.turns_sent,
        "api_events": result.events_seen,
        "touches_used": result.touches_used,
        "ledger": local_summary,
        "incident": "NOT VERIFIED",
    }


def main() -> int:
    """Execute an adaptive run without logging API keys or private config."""
    output = asyncio.run(run(parse_args()))
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
