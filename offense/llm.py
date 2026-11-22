"""Provide a pluggable asynchronous language-model wrapper for generation.

The backend is chosen by name: ``anthropic``, ``openai``, or ``none``. The
``none`` backend returns ``None`` so callers fall back to deterministic templates.
Within a session these calls are awaited sequentially; concurrency only happens
across independent sessions.
"""

from __future__ import annotations

import json
import os
import re


class LLM:
    """Wrap a chat language model behind a small async generation interface."""

    def __init__(
        self,
        backend: str = "none",
        model: str = "",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Create a language-model wrapper for the selected backend.

        Args:
            backend: One of ``anthropic``, ``openai``, or ``none``.
            model: Model identifier to call.
            api_key: Explicit credential; falls back to the environment.
            base_url: Optional OpenAI-compatible endpoint override.

        """
        self.backend = backend
        self.model = model
        self._client = None
        if backend == "anthropic":
            import anthropic

            self._client = anthropic.AsyncAnthropic(
                api_key=api_key or os.getenv("ANTHROPIC_API_KEY")
            )
        elif backend == "openai":
            import openai

            self._client = openai.AsyncOpenAI(
                api_key=api_key or os.getenv("OPENAI_API_KEY"),
                base_url=base_url or os.getenv("OPENAI_BASE_URL") or None,
            )

    async def complete(
        self, system: str, user: str, *, max_tokens: int = 1500, temperature: float = 0.7
    ) -> str | None:
        """Generate a completion for a system and user prompt.

        Args:
            system: System instructions.
            user: User message.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Returns:
            The generated text, or ``None`` for the ``none`` backend.

        """
        if self.backend == "anthropic":
            message = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return "".join(block.text for block in message.content if block.type == "text")
        if self.backend == "openai":
            return await self._openai(system, user, max_tokens, temperature)
        return None

    async def complete_json(self, system: str, user: str, **kwargs: object) -> dict | None:
        """Generate a completion and parse it as a single JSON object.

        Args:
            system: System instructions.
            user: User message.
            **kwargs: Forwarded to :meth:`complete`.

        Returns:
            The parsed object, or ``None`` when generation or parsing fails.

        """
        raw = await self.complete(
            system + "\n\nRespond with a single JSON object only.", user, **kwargs
        )
        if raw is None:
            return None
        return _extract_json(raw)

    async def _openai(
        self, system: str, user: str, max_tokens: int, temperature: float
    ) -> str | None:
        """Call the OpenAI chat API, tolerating parameter drift across models.

        Newer models expect ``max_completion_tokens`` and reject a non-default
        ``temperature``; older ones use ``max_tokens``. Each shape is tried until
        one is accepted.

        Args:
            system: System instructions.
            user: User message.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Returns:
            The generated text.

        Raises:
            Exception: The last error when every parameter shape is rejected.

        """
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        attempts = [
            {"max_completion_tokens": max_tokens, "temperature": temperature},
            {"max_completion_tokens": max_tokens},
            {"max_tokens": max_tokens, "temperature": temperature},
            {"max_tokens": max_tokens},
        ]
        last_error: Exception | None = None
        for extra in attempts:
            try:
                response = await self._client.chat.completions.create(
                    model=self.model, messages=messages, **extra
                )
                return response.choices[0].message.content
            except Exception as error:  # noqa: BLE001 - retried on parameter errors
                last_error = error
                text = str(error).lower()
                if any(
                    token in text
                    for token in (
                        "temperature",
                        "max_tokens",
                        "max_completion_tokens",
                        "unsupported",
                        "unknown parameter",
                        "not supported",
                    )
                ):
                    continue
                raise
        raise last_error


def _extract_json(raw: str) -> dict | None:
    """Extract a single JSON object from model output.

    Args:
        raw: Raw model text, possibly fenced or with surrounding prose.

    Returns:
        The parsed object, or ``None`` when no object can be parsed.

    """
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S)
    try:
        return json.loads(raw)
    except ValueError:
        pass
    match = re.search(r"\{.*\}", raw, flags=re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except ValueError:
            return None
    return None
