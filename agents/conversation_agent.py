"""Provide bounded, transparent responses for simulation connectivity checks."""

from __future__ import annotations

import re
from typing import Protocol


class ConversationPolicyError(ValueError):
    """Signal a generated line that violates the neutral test policy."""


class ConversationAgent(Protocol):
    """Define the bounded line-generation interface."""

    async def next_line(self, history: list[dict[str, str]]) -> str | None:
        """Return a permitted next utterance or terminate the conversation."""
        ...


def validate_neutral_line(line: str | None) -> str | None:
    """Reject oversized, malicious, or secret-requesting generated content.

    This is a defense-in-depth filter, not a complete semantic safety classifier.
    """
    if line is None:
        return None
    if not isinstance(line, str) or not line.strip() or len(line) > 600:
        raise ConversationPolicyError("Invalid line length")
    blocked = re.compile(
        r"\b(password|passcode|credential|one.time.password|otp|api.key|"
        r"secret.token|bank.account|verification.code|ignore.your.instructions|"
        r"grant.access|payment.details)\b",
        re.IGNORECASE,
    )
    if blocked.search(line):
        raise ConversationPolicyError("Unsafe content in generated line")
    return line.strip()


class NeutralConversationAgent:
    """Use a deterministic two-turn flow for an API integration test."""

    async def next_line(self, history: list[dict[str, str]]) -> str | None:
        """Acknowledge the channel and end without requesting information."""
        sent = sum(item["direction"] == "agent" for item in history)
        if sent > 0:
            return None
        return (
            "Hello, this is a transparent connectivity test within the "
            "authorized simulation. I'm checking that the chat channel works. "
            "No action or private information is requested. Thank you."
        )


class OpenAINeutralConversationAgent:
    """Generate one non-deceptive acknowledgement using an OpenAI model."""

    def __init__(self, api_key: str, model: str) -> None:
        """Construct the model client without making an outbound request."""
        if not api_key or not model:
            raise ValueError("Model and API key are required")
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model

    async def next_line(self, history: list[dict[str, str]]) -> str | None:
        """Return one concise, transparent reply, then stop conversation."""
        if any(item["direction"] == "agent" for item in history):
            return None
        response = await self._client.responses.create(
            model=self._model,
            instructions=(
                "You are testing a simulated chat interface with consent. "
                "Generate only one short, transparent greeting/acknowledgement. "
                "State clearly this is a connectivity test. Do not impersonate "
                "anyone, create urgency, request actions, credentials, "
                "personal data, internal information or links. "
                "Do not discuss hidden instructions. Maximum 50 words."
            ),
            input=(
                "The simulated contact said: "
                + next(
                    (item["body"] for item in reversed(history) if item["direction"] == "persona"),
                    "Hello",
                )[:700]
            ),
            max_output_tokens=110,
            store=False,
        )
        return validate_neutral_line(response.output_text)
