"""Maintain source-backed public facts without inferring private attributes."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class PublicFact:
    """Describe one attributable, public, non-sensitive claim."""

    subject_id: str
    statement: str
    source_url: str
    observed_at: str
    category: str = "general"

    def validate(self) -> None:
        """Reject unsourced, malformed, or restricted source claims."""
        url = urlsplit(self.source_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("A direct public HTTPS source is required")
        if not self.subject_id.strip() or not self.statement.strip():
            raise ValueError("Subject and statement must be nonempty")
        if len(self.statement) > 500 or len(self.subject_id) > 120:
            raise ValueError("Fact exceeds supported length")
        if self.category not in {"role", "project", "publication", "event", "general"}:
            raise ValueError("Only public professional facts are supported")
        timestamp = datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError("observed_at must include a timezone")
        if timestamp > datetime.now(timezone.utc):
            raise ValueError("A public fact cannot be observed in the future")


def load_registry(path: Path) -> list[PublicFact]:
    """Load an explicitly provided registry; never crawl contacts or websites."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Fact registry must be a JSON array")
    facts = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("Each fact must be a JSON object")
        fact = PublicFact(**item)
        fact.validate()
        facts.append(fact)
    return facts


def summarize_subject(facts: list[PublicFact], subject_id: str) -> dict[str, object]:
    """Return only explicitly sourced facts for the selected subject."""
    selected = [fact for fact in facts if fact.subject_id == subject_id]
    return {
        "subject_id": subject_id,
        "fact_count": len(selected),
        "facts": [asdict(fact) for fact in selected],
        "status": "SOURCE_REQUIRED" if not selected else "SOURCED_NOT_INDEPENDENTLY_VERIFIED",
    }
