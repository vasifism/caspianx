"""Test structured OpenAI analysis without making network requests."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from llm.openai_client import OpenAIAnalysisError, OpenAIClient
from llm.schemas import EventAnalysis


def make_mock_client(
    result: EventAnalysis | None,
) -> SimpleNamespace:
    """Create an SDK-compatible mock for structured responses.

    Args:
        result: Parsed result returned by the mock response.

    Returns:
        Mock client with an asynchronous responses.parse method.

    """
    parse = AsyncMock(return_value=SimpleNamespace(output_parsed=result))
    return SimpleNamespace(responses=SimpleNamespace(parse=parse))


def test_model_is_required() -> None:
    """Reject an empty model identifier."""
    with pytest.raises(ValueError):
        OpenAIClient(api_key=None, model="")


def test_live_calls_are_disabled_by_default() -> None:
    """Prevent API operations without explicit authorization."""

    async def run() -> None:
        """Attempt an operation with network access disabled."""
        client = OpenAIClient(
            api_key=None,
            model="test-model",
        )

        with pytest.raises(OpenAIAnalysisError):
            await client.analyze_events([])

        await client.aclose()

    asyncio.run(run())


def test_structured_analysis() -> None:
    """Return validated structured analysis from a mock SDK."""

    async def run() -> None:
        """Analyze a mock reply event."""
        expected = EventAnalysis(
            summary="A reply was observed.",
            event_types=["reply"],
            has_reply=True,
            uncertainties=[],
            requires_review=False,
        )

        mock_client = make_mock_client(expected)

        async with OpenAIClient(
            api_key=None,
            model="test-model",
            allow_live_calls=True,
            client=mock_client,
        ) as client:
            result = await client.analyze_events([{"id": "e_1", "type": "reply"}])

        assert result == expected
        mock_client.responses.parse.assert_awaited_once()

    asyncio.run(run())


def test_sensitive_fields_are_not_forwarded() -> None:
    """Exclude message content and submitted values from model input."""

    async def run() -> None:
        """Inspect the sanitized input sent to the mock SDK."""
        expected = EventAnalysis(
            summary="A form submission occurred.",
            event_types=["page.submitted"],
            has_reply=False,
            uncertainties=["Submission context is unknown."],
            requires_review=False,
        )

        mock_client = make_mock_client(expected)

        async with OpenAIClient(
            api_key=None,
            model="test-model",
            allow_live_calls=True,
            client=mock_client,
        ) as client:
            await client.analyze_events(
                [
                    {
                        "id": "e_2",
                        "type": "page.submitted",
                        "fields": ["email", "password"],
                        "values": {"password": "highly-sensitive-value"},
                        "body": "confidential-content",
                    }
                ]
            )

        arguments = mock_client.responses.parse.call_args.kwargs
        serialized_input = arguments["input"]

        assert "highly-sensitive-value" not in serialized_input
        assert "confidential-content" not in serialized_input
        assert "page.submitted" in serialized_input
        assert arguments["store"] is False

    asyncio.run(run())


def test_missing_structured_response_raises() -> None:
    """Reject responses without a validated structured result."""

    async def run() -> None:
        """Simulate a model response with no parsed content."""
        mock_client = make_mock_client(None)

        async with OpenAIClient(
            api_key=None,
            model="test-model",
            allow_live_calls=True,
            client=mock_client,
        ) as client:
            with pytest.raises(
                OpenAIAnalysisError,
                match="no structured analysis",
            ):
                await client.analyze_events([])

    asyncio.run(run())
