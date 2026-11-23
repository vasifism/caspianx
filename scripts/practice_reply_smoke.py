"""Send one neutral message to an authorized practice AI twin."""

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

MESSAGE = {
    "to": TARGET_ID,
    "channel": "email",
    "subject": "Practice channel acknowledgement",
    "body": (
        "Hello! This is a connectivity check in the authorized "
        "practice simulation. Could you please reply with a brief "
        "acknowledgement that this message reached you? "
        "No personal or confidential information is requested."
    ),
}


async def main() -> int:
    """Send one bounded practice message without automatic resubmission.

    Returns:
        Zero when the API accepts the message, otherwise one.

    """
    settings = Settings()

    if settings.dry_run:
        print("Live API calls are disabled.")
        return 1

    if not settings.team_key or not settings.team_key.get_secret_value():
        print("Missing CASPIANX_TEAM_KEY.")
        return 1

    marker = Path("data/practice_reply_smoke_001.json")
    marker.parent.mkdir(parents=True, exist_ok=True)

    try:
        async with TargetAPIClient(settings) as api:
            session = await api.get_session(SESSION_ID)

        if session.scenario_id != "practice":
            raise ValueError("Non-practice session rejected.")

        if session.status != "active":
            raise ValueError("Practice session is not active.")

        if session.touches_used >= session.touch_budget:
            raise ValueError("Practice contact budget exhausted.")

        idempotency_key = str(uuid4())

        # Reserve this operation before contacting the API.
        # Never overwrite the marker after an ambiguous failure.
        with marker.open("x", encoding="utf-8") as handle:
            json.dump(
                {
                    "session_id": SESSION_ID,
                    "target_id": TARGET_ID,
                    "idempotency_key": idempotency_key,
                    "status": "attempted",
                },
                handle,
                indent=2,
            )

        print("Sending one neutral practice message...")

        async with httpx.AsyncClient(
            base_url=settings.target_api_base_url.rstrip("/") + "/",
            timeout=settings.http_timeout_seconds,
            follow_redirects=False,
        ) as client:
            response = await client.post(
                f"sessions/{SESSION_ID}/messages",
                headers={
                    "Authorization": ("Bearer " + settings.team_key.get_secret_value()),
                    "Idempotency-Key": idempotency_key,
                },
                json=MESSAGE,
            )

            response.raise_for_status()
            result = response.json()

        print("Message accepted by the practice API.")
        print(f"Message ID: {result.get('message_id', 'unknown')}")
        print(f"Contacts used: {result.get('touches_used', 'unknown')}")
        print(f"Immediate events: {len(result.get('events') or [])}")
        print("PRACTICE SEND: PASS")
        return 0

    except FileExistsError:
        print("This test was already attempted. No message sent.")
        return 1

    except Exception as error:
        print(
            f"Practice send failed: {type(error).__name__}",
            file=sys.stderr,
        )
        print(
            "Do not automatically retry. Inspect the session "
            "and the existing operation marker first.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
