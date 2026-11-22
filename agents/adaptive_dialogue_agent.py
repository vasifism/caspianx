"""Provide bounded adaptive, transparent simulation conversations."""

from __future__ import annotations

from agents.conversation_agent import validate_neutral_line


class AdaptiveDialogueAgent:
    """Adapt a technical conversation to a persona's latest visible question.

    The agent is intentionally transparent and requests no secrets, access,
    or privileged action. This is a technical integration agent, not an attack
    generator or a scoring-incident optimizer.
    """

    def __init__(self, max_agent_lines: int = 3) -> None:
        """Initialize a deterministic, finite conversation policy."""
        if not 1 <= max_agent_lines <= 10:
            raise ValueError("max_agent_lines must be between 1 and 10")
        self.max_agent_lines = max_agent_lines

    async def next_line(self, history: list[dict[str, str]]) -> str | None:
        """Select a response from visible dialogue while enforcing a turn cap."""
        sent = sum(item.get("direction") == "agent" for item in history)
        if sent >= self.max_agent_lines:
            return None
        last = next(
            (
                item.get("body", "")
                for item in reversed(history)
                if item.get("direction") == "persona"
            ),
            "",
        ).lower()
        if sent == 0:
            line = (
                "Hello, this is a transparent technical test in the authorized "
                "simulation. I am checking whether our chat integration handles "
                "a reply correctly. No private information or action is needed."
            )
        elif any(word in last for word in ("who", "why", "what", "about", "purpose")):
            line = (
                "This is only an API conversation integration check. "
                "I am testing how the chat handles a clarification; "
                "you do not need to provide any information."
            )
        elif any(word in last for word in ("stop", "leave", "not interested", "busy")):
            return None
        else:
            line = "Thanks for confirming the connection. I will close the test now."
        return validate_neutral_line(line)
