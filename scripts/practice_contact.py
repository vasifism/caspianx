"""Send one neutral contact inside an authorized practice simulation."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

import httpx

from config.settings import Settings
from core.session_manager import SessionManager
from integrations.target_api import TargetAPIClient
from storage.event_store import EventStore


SESSION_ID = "s_678d0c7e74"
TARGET_ID = "julius"

MESSAGE = {
    "to": TARGET_ID,
    "channel": "email",
    "subject": "Practice simulation connectivity check",
    "body": (
        "Hello, this is a technical connectivity check within "
        "the authorized revel8 practice simulation. "
        "No action or information is requested. Thank you."
    ),
}


async def main() -> int:
    """Send at most one practice contact and synchronize local metadata.

    Returns:
        Zero after a successful send and synchronization, otherwise one.

    """
    settings = Settings()

    if settings.dry_run:
        print("Live access is disabled.")
        return 1

    if not settings.team_key or not settings.team_key.get_secret_value():
        print("CASPIANX_TEAM_KEY is missing.")
        return 1

    try:
        async with TargetAPIClient(settings) as reader:
            scenarios = await reader.list_scenarios()
            session = await reader.get_session(SESSION_ID)

        practice = next(
            (item for item in scenarios if item.id == "practice"),
            None,
        )

        if practice is None or not practice.open:
            raise RuntimeError("Practice scenario is unavailable.")

        if TARGET_ID not in {item.id for item in practice.targets}:
            raise RuntimeError("Target is absent from practice scenario.")

        if session.scenario_id != "practice":
            raise RuntimeError("Refusing to use a non-practice session.")

        if session.status != "active":
            raise RuntimeError("Practice session is not active.")

        if session.touches_used >= session.touch_budget:
            raise RuntimeError("Contact budget is exhausted.")

        marker = Path("data") / f"contact_{SESSION_ID}_001.json"
        marker.parent.mkdir(parents=True, exist_ok=True)

        idempotency_key = str(uuid4())

        # The marker prevents this script from sending the same contact
        # again, including after an ambiguous network failure.
        with marker.open("x", encoding="utf-8") as file:
            json.dump(
                {
                    "session_id": SESSION_ID,
                    "target_id": TARGET_ID,
                    "idempotency_key": idempotency_key,
                    "status": "attempted",
                },
                file,
                indent=2,
            )

        print("Sending one neutral practice contact...")
        print(f"Session: {SESSION_ID}")
        print(f"Target ID: {TARGET_ID}")

        async with httpx.AsyncClient(
            base_url=settings.target_api_base_url.rstrip("/") + "/",
            timeout=120.0,
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

        # Do not print event bodies or form values.
        print(f"Message ID: {result['message_id']}")
        print(f"Contacts used: {result['touches_used']}")
        print(f"Immediate events: {len(result.get('events', []))}")

        for event in result.get("events", []):
            print(f"Event type: {event.get('type', 'unknown')}")

        async with TargetAPIClient(settings) as reader:
            updated_session = await reader.get_session(SESSION_ID)

        with EventStore(settings.sqlite_path) as store:
            manager = SessionManager(store)
            machine = manager.synchronize(updated_session)

        print(f"Contacts remaining: {machine.remaining_contacts}")
        print("SQLite synchronization: OK")
        print("Practice contact test: OK")

        return 0

    except FileExistsError:
        print("This practice contact was already attempted. Refusing to send it again.")
        return 1

    except Exception as error:
        print(
            f"Practice test failed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        print("Do not rerun this script automatically. Inspect the session first.")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
