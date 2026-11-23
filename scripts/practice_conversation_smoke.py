"""Run one neutral conversation test with a simulated practice persona."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

import httpx

from config.settings import Settings
from integrations.target_api import TargetAPIClient


SESSION_ID = "s_678d0c7e74"
TARGET_ID = "julius"

MARKER = Path("data/practice_conversation_smoke.json")


async def main() -> int:
    """Test conversation start, one turn, and graceful termination.

    Returns:
        Zero if the conversation API behaves as expected, otherwise one.

    """
    settings = Settings()

    if settings.dry_run:
        print("Live access disabled.")
        return 1

    if not settings.team_key or not settings.team_key.get_secret_value():
        print("Missing team API key.")
        return 1

    try:
        async with TargetAPIClient(settings) as reader:
            session = await reader.get_session(SESSION_ID)

        if session.scenario_id != "practice":
            raise ValueError("Only practice sessions are permitted.")

        if session.status != "active":
            raise ValueError("Session is not active.")

        if session.touches_used >= session.touch_budget:
            raise ValueError("Contact budget exhausted.")

        MARKER.parent.mkdir(parents=True, exist_ok=True)

        start_key = uuid4().hex
        turn_key = uuid4().hex

        with MARKER.open("x", encoding="utf-8") as handle:
            json.dump(
                {
                    "session_id": SESSION_ID,
                    "start_key": start_key,
                    "turn_key": turn_key,
                    "status": "attempted",
                },
                handle,
                indent=2,
            )

        headers = {"Authorization": (f"Bearer {settings.team_key.get_secret_value()}")}

        async with httpx.AsyncClient(
            base_url=settings.target_api_base_url.rstrip("/") + "/",
            timeout=120.0,
            follow_redirects=False,
        ) as client:
            conversation = await client.post(
                f"sessions/{SESSION_ID}/conversations",
                headers={
                    **headers,
                    "Idempotency-Key": start_key,
                },
                json={
                    "to": TARGET_ID,
                    "channel": "live_chat",
                },
            )
            conversation.raise_for_status()
            started = conversation.json()

            conversation_id = started["conversation_id"]

            print(f"Conversation ID: {conversation_id}")
            print(f"Status: {started['status']}")
            print(f"Persona says: {started.get('persona_says')}")
            print(f"Contacts used: {started['touches_used']}")

            if started["status"] == "answered":
                turn = await client.post(
                    f"conversations/{conversation_id}/turns",
                    headers={
                        **headers,
                        "Idempotency-Key": turn_key,
                    },
                    json={
                        "say": (
                            "Hello! Could you confirm that this "
                            "live chat connection is working? "
                            "No sensitive information is needed."
                        )
                    },
                )
                turn.raise_for_status()
                answer = turn.json()

                print(f"Persona response: {answer.get('persona_says')}")
                print(f"Conversation ended: {answer.get('ended')}")
                print(f"Events: {len(answer.get('events') or [])}")

            end_response = await client.post(
                f"conversations/{conversation_id}/end",
                headers=headers,
            )
            end_response.raise_for_status()

        print("PRACTICE CONVERSATION: PASS")
        return 0

    except FileExistsError:
        print("Conversation test was already attempted.")
        return 1

    except Exception as error:
        print(
            f"Conversation test failed: {type(error).__name__}",
            file=sys.stderr,
        )
        print(
            "Inspect the session before attempting another contact.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
