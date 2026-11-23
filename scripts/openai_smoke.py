"""Verify real OpenAI connectivity with synthetic simulation events."""

from __future__ import annotations

import asyncio
import sys

from openai import AsyncOpenAI

from config.settings import Settings
from llm.openai_client import OpenAIClient


async def main() -> int:
    """Validate model access and run one structured analysis.

    Returns:
        Zero on successful validation, otherwise one.

    """
    settings = Settings()

    if not settings.openai_api_key:
        print("CASPIANX_OPENAI_API_KEY is missing.")
        return 1

    key = settings.openai_api_key.get_secret_value()
    model = settings.openai_model

    if not key or not model:
        print("OpenAI API key or model is empty.")
        return 1

    print("CaspianX OpenAI Smoke Test")
    print(f"Configured model: {model}")
    print("Input: synthetic event metadata")
    print("Target API contacts: none")

    try:
        async with AsyncOpenAI(
            api_key=key,
            timeout=60.0,
            max_retries=0,
        ) as sdk:
            model_info = await sdk.models.retrieve(model)
            print(f"Accessible model: {model_info.id}")

        async with OpenAIClient(
            api_key=key,
            model=model,
            allow_live_calls=True,
        ) as client:
            analysis = await client.analyze_events(
                [
                    {
                        "id": "synthetic_event_001",
                        "type": "message.opened",
                    }
                ]
            )

        print("Structured analysis:")
        print(analysis.model_dump_json(indent=2))
        print("OpenAI connectivity: OK")
        return 0

    except Exception as error:
        print(
            f"OpenAI smoke test failed: {type(error).__name__}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
