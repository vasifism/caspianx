"""Define structured outputs for AI-powered simulation analysis."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class EventAnalysis(BaseModel):
    """Represent an evidence-based analysis of simulation events.

    Attributes:
        summary: Concise description of observed events.
        event_types: Event types explicitly present in the input.
        has_reply: Whether an actual reply event was observed.
        uncertainties: Important facts not established by the events.
        requires_review: Whether the observations require manual review.

    """

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="A factual summary without unsupported inferences.")
    event_types: list[str] = Field(description="Types of events explicitly observed.")
    has_reply: bool = Field(description="True only if an actual reply event exists.")
    uncertainties: list[str] = Field(
        description="Questions that cannot be answered from the events."
    )
    requires_review: bool = Field(description="Whether unexpected behavior needs further review.")
