"""Run one autonomous attack session against a target through the sandbox API.

Reuses CaspianX Settings (team key, model, base URL). This is the offensive loop:
research -> plan -> compose -> send -> observe -> adapt, optimized for the fewest
contacts to the first incident.

Usage:
    python -m scripts.run_attack --target julius --objective credentials
    python -m scripts.run_attack --target tom --record

``CASPIANX_DRY_RUN=false`` must be set to actually send.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from config.settings import Settings
from offense.attack_client import APIError, AttackClient
from offense.engine import AttackEngine
from offense.llm import LLM
from offense.recording_session_reader import RecordingClient


def _build(settings: Settings) -> tuple[AttackClient, LLM]:
    """Build the client and language model from settings and environment.

    The backend is chosen with ``CASPIANX_LLM_BACKEND`` (``openai`` by default).
    For ``anthropic``, set ``CASPIANX_ANTHROPIC_API_KEY`` and
    ``CASPIANX_ANTHROPIC_MODEL`` so the two providers can be A/B tested without
    touching settings.

    Args:
        settings: Validated CaspianX settings.

    Returns:
        A tuple of the send-capable client and the language model.

    Raises:
        SystemExit: When the team key or a required model/credential is missing.

    """
    key = settings.team_key.get_secret_value() if settings.team_key else ""
    if not key:
        raise SystemExit("CASPIANX_TEAM_KEY is missing.")

    backend = os.getenv("CASPIANX_LLM_BACKEND", "openai").lower()
    if backend == "anthropic":
        anthropic_key = os.getenv("CASPIANX_ANTHROPIC_API_KEY")
        anthropic_model = os.getenv("CASPIANX_ANTHROPIC_MODEL", "")
        if not anthropic_key:
            raise SystemExit("CASPIANX_ANTHROPIC_API_KEY is missing.")
        if not anthropic_model.strip():
            raise SystemExit("CASPIANX_ANTHROPIC_MODEL is missing (e.g. a Claude model id).")
        llm = LLM("anthropic", anthropic_model, api_key=anthropic_key)
    else:
        if not settings.openai_model.strip():
            raise SystemExit("CASPIANX_OPENAI_MODEL is missing.")
        llm = LLM(
            "openai",
            settings.openai_model,
            api_key=(
                settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
            ),
        )

    client = AttackClient(settings.target_api_base_url, key, timeout=settings.http_timeout_seconds)
    return client, llm


async def run(args: argparse.Namespace) -> None:
    """Run one attack session from parsed arguments.

    Args:
        args: Parsed command-line arguments.

    Raises:
        SystemExit: When live access is disabled or configuration is missing.

    """
    settings = Settings()
    if settings.dry_run:
        raise SystemExit("Live access is disabled. Set CASPIANX_DRY_RUN=false to attack.")

    client, llm = _build(settings)
    if args.record:
        client = RecordingClient(client)
    engine = AttackEngine(client, llm)

    facts = None
    if args.facts_file:
        with open(args.facts_file, encoding="utf-8") as handle:
            facts = [line.strip() for line in handle if line.strip()]

    try:
        result = await engine.run_session(
            scenario_id=args.scenario,
            target_id=args.target,
            objective_pref=args.objective,
            target_name=args.name or "",
            target_role=args.role or "",
            language=args.language or "",
            facts=facts,
            max_touches=args.max_touches,
            first_channel=args.channel,
        )
        print("\nRESULT:", json.dumps(result, indent=2))
        if args.record:
            print("recording:", client.recording_path)
    finally:
        await client.close()


def main() -> None:
    """Parse arguments and run one attack session."""
    parser = argparse.ArgumentParser(description="CaspianX attack runner")
    parser.add_argument("--scenario", default="practice")
    parser.add_argument("--target", required=True, help="julius | tom | robert | <eval id>")
    parser.add_argument(
        "--objective", default=None, choices=[None, "credentials", "action", "disclosure"]
    )
    parser.add_argument("--name", default=None)
    parser.add_argument("--role", default=None)
    parser.add_argument("--language", default=None, help="de | en")
    parser.add_argument("--facts-file", default=None)
    parser.add_argument("--max-touches", type=int, default=None)
    parser.add_argument(
        "--channel",
        default=None,
        help="force the opening channel, e.g. slack, teams_chat, phone_call, live_chat",
    )
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except APIError as error:
        print("API error:", error, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
