"""Run an offline demo or one explicitly authorized neutral live practice chat."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from agents.conversation_agent import NeutralConversationAgent, OpenAINeutralConversationAgent
from core.conversation_manager import ConversationManager
from storage.conversation_repository import ConversationRepository


class OfflineConversationTransport:
    """Provide a deterministic simulated conversation without network calls."""

    def __init__(self) -> None:
        """Initialize the offline mock transport."""
        self.sent_lines: list[str] = []

    async def get_session(self, session_id: str) -> dict[str, Any]:
        """Return synthetic practice session metadata."""
        return {
            "session_id": session_id,
            "scenario_id": "practice",
            "status": "active",
            "touches_used": 0,
            "touch_budget": 30,
        }

    async def start(
        self, session_id: str, target_id: str, channel: str, key: str
    ) -> dict[str, Any]:
        """Start a synthetic conversation."""
        return {
            "conversation_id": "offline_conversation_001",
            "status": "answered",
            "persona_says": "Hello, how can I help?",
            "touches_used": 1,
        }

    async def turn(self, conversation_id: str, line: str, key: str) -> dict[str, Any]:
        """Respond once to a simulated agent utterance."""
        self.sent_lines.append(line)
        return {"persona_says": "The simulated chat works. Thanks!", "ended": False, "events": []}

    async def end(self, conversation_id: str, key: str) -> dict[str, Any]:
        """Close the mock conversation."""
        return {"status": "ended"}


def parse_args() -> argparse.Namespace:
    """Parse one bounded and explicit practice-session invocation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="offline_practice")
    parser.add_argument("--target", default="julius")
    parser.add_argument("--db", type=Path, default=Path("build/conversation_practice.sqlite3"))
    parser.add_argument("--max-turns", type=int, default=2)
    parser.add_argument(
        "--live", action="store_true", help="Spend exactly one authorized practice contact"
    )
    parser.add_argument("--use-openai", action="store_true", help="Use model for neutral greeting")
    return parser.parse_args()


async def main() -> int:
    """Run a complete, bounded conversation and print sanitized statistics."""
    args = parse_args()
    from config.settings import Settings

    settings = Settings()
    if args.live:
        if settings.dry_run:
            raise ValueError("Set CASPIANX_DRY_RUN=false explicitly for a live practice run")
        if not args.session.startswith("s_"):
            raise ValueError("Live execution requires a real practice session ID")
        from integrations.conversation_transport import Revel8ConversationTransport

        if settings.team_key is None:
            raise ValueError("CASPIANX_TEAM_KEY is missing")
        transport = Revel8ConversationTransport(
            settings.team_key.get_secret_value(),
            settings.target_api_base_url,
            timeout=settings.http_timeout_seconds,
        )
    else:
        if args.use_openai:
            raise ValueError("OpenAI mode is only available with --live")
        transport = OfflineConversationTransport()

    if args.use_openai:
        if settings.openai_api_key is None:
            raise ValueError("CASPIANX_OPENAI_API_KEY is missing")
        agent = OpenAINeutralConversationAgent(
            settings.openai_api_key.get_secret_value(), settings.openai_model
        )
    else:
        agent = NeutralConversationAgent()

    # Open the network client only once and do not silently retry POST calls.
    with ConversationRepository(args.db) as repository:
        if args.live:
            async with transport:
                result = await ConversationManager(
                    transport, repository, agent, max_turns=args.max_turns
                ).run(args.session, args.target)
        else:
            result = await ConversationManager(
                transport, repository, agent, max_turns=args.max_turns
            ).run(args.session, args.target)
        print(
            json.dumps(
                {
                    "conversation_id": result.conversation_id,
                    "status": result.status,
                    "turns_sent": result.turns_sent,
                    "api_events": result.events_seen,
                    "touches_used": result.touches_used,
                    "local_ledger": repository.snapshot(args.session),
                    "competition_incident": "NOT VERIFIED",
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
