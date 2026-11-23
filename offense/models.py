"""Define the shared data structures used across the offensive pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Hook:
    """Describe one candidate angle the target may be open to right now."""

    topic: str
    rationale: str
    objective: str = "credentials"
    channel: str = "email"
    sender_name: str = ""
    sender_address: str = ""
    pretext: str = ""


@dataclass
class Dossier:
    """Hold what is known about a target and the angles proposed for them."""

    target_id: str
    name: str
    role: str
    language: str = "en"
    projects: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    hooks: list[Hook] = field(default_factory=list)

    def fact_block(self) -> str:
        """Render the gathered facts as a bulleted block for prompting.

        Returns:
            A newline-joined bullet list, or a placeholder when empty.

        """
        lines = [f"- {item}" for item in self.facts]
        return "\n".join(lines) if lines else "- (none gathered yet)"


@dataclass
class PageSpec:
    """Describe a landing page to register before a linking message is sent."""

    url: str
    title: str
    fields: list[str] = field(default_factory=list)
    html: str | None = None
    text: str | None = None


@dataclass
class Attachment:
    """Describe a declared attachment (a file name, optionally a transcript)."""

    filename: str
    transcript: str | None = None

    def to_api(self) -> dict[str, Any]:
        """Convert this attachment into its API request representation.

        Returns:
            A mapping with ``filename`` and, for audio, ``transcript``.

        """
        payload: dict[str, Any] = {"filename": self.filename}
        if self.transcript is not None:
            payload["transcript"] = self.transcript
        return payload


@dataclass
class Plan:
    """Capture a single decided move for the next contact."""

    mode: str
    objective: str
    channel: str
    topic: str
    intent: str
    sender_name: str = ""
    sender_address: str = ""
    subject: str | None = None
    include_link: bool = False
    include_attachment: bool = False
    reasoning: str = ""


@dataclass
class Belief:
    """Track the agent's inferred read of the target within a session."""

    engaged: bool = False
    suspicion: float = 0.0
    tried_topics: list[str] = field(default_factory=list)
    tried_channels: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    last_event_summary: str = "no contact yet"

    def summary(self) -> str:
        """Render the current belief as a compact block for prompting.

        Returns:
            A human-readable summary of engagement, suspicion, and notes.

        """
        header = (
            f"engaged={self.engaged} suspicion={self.suspicion:.2f} "
            f"tried_topics={self.tried_topics} tried_channels={self.tried_channels}\n"
            f"last: {self.last_event_summary}\n"
        )
        notes = "\n".join(f"- {note}" for note in self.notes[-6:]) if self.notes else ""
        return header + notes


@dataclass
class Incident:
    """Record whether a scored incident was reached and its evidence."""

    reached: bool = False
    objective: str = ""
    evidence: str = ""
