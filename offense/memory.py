"""Record the per-session thread and the claims asserted within it."""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from typing import Any

from offense.models import Plan


class SessionMemory:
    """Hold everything said and observed in one session.

    The target remembers every contact in a session, so the composer must stay
    consistent with the recorded claims.
    """

    def __init__(self, target_id: str) -> None:
        """Initialise empty memory for one target.

        Args:
            target_id: The target this session addresses.

        """
        self.target_id = target_id
        self.thread: list[dict[str, Any]] = []
        self.claims: list[str] = []

    def record_move(self, plan: Plan, rendered: dict[str, Any]) -> None:
        """Append one outbound move to the thread.

        Args:
            plan: The plan that produced the move.
            rendered: The rendered message or conversation line.

        """
        self.thread.append(
            {"t": time.time(), "kind": "move", "plan": asdict(plan), "rendered": rendered}
        )

    def record_events(self, events: list[dict]) -> None:
        """Append observed events to the thread.

        Args:
            events: Reaction events to record.

        """
        for event in events:
            self.thread.append({"t": time.time(), "kind": "event", "event": event})

    def add_claims(self, claims: list[str]) -> None:
        """Record new claims asserted this session, de-duplicating.

        Args:
            claims: Story points the agent has asserted.

        """
        for claim in claims:
            if claim and claim not in self.claims:
                self.claims.append(claim)

    def transcript(self, limit: int = 20) -> str:
        """Render recent thread entries as a readable transcript.

        Args:
            limit: Maximum number of trailing entries to include.

        Returns:
            A readable transcript of recent moves and events.

        """
        out: list[str] = []
        for item in self.thread[-limit:]:
            if item["kind"] == "move":
                plan = item["plan"]
                rendered = item["rendered"]
                head = f"[US -> {self.target_id} via {plan['channel']}]"
                if rendered.get("subject"):
                    head += f" subj: {rendered['subject']}"
                out.append(head + "\n" + rendered.get("body", rendered.get("say", "")))
            else:
                event = item["event"]
                etype = event.get("type", "?")
                if etype == "reply":
                    out.append(f"[TARGET reply via {event.get('channel')}] {event.get('body', '')}")
                else:
                    payload = {key: value for key, value in event.items() if key != "type"}
                    out.append(f"[SIGNAL {etype}] {json.dumps(payload)}")
        return "\n\n".join(out)

    def claims_block(self) -> str:
        """Render the asserted claims as a bulleted block for prompting.

        Returns:
            A newline-joined bullet list, or a placeholder when empty.

        """
        if not self.claims:
            return "- (none yet)"
        return "\n".join(f"- {claim}" for claim in self.claims)
