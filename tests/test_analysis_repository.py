"""Test persistent structured analysis without external API calls."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm.schemas import EventAnalysis
from storage.analysis_repository import AnalysisRepository
from storage.event_store import EventStore


def make_analysis() -> EventAnalysis:
    """Create a deterministic sanitized analysis for testing."""
    return EventAnalysis(
        summary="No events were observed.",
        event_types=[],
        has_reply=False,
        uncertainties=["No interaction has occurred."],
        requires_review=False,
    )


def test_analysis_is_persisted(tmp_path: Path) -> None:
    """Store and count a validated analysis."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        repository = AnalysisRepository(store)
        analysis_id = repository.save("practice_001", make_analysis())

        assert len(analysis_id) == 64
        assert repository.count("practice_001") == 1


def test_duplicate_analysis_is_idempotent(tmp_path: Path) -> None:
    """Prevent identical analyses from creating duplicate records."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        repository = AnalysisRepository(store)

        first = repository.save("practice_001", make_analysis())
        second = repository.save("practice_001", make_analysis())

        assert first == second
        assert repository.count("practice_001") == 1


def test_analysis_survives_restart(tmp_path: Path) -> None:
    """Recover the saved analysis count after reopening the database."""
    path = tmp_path / "durable.sqlite3"

    with EventStore(path) as store:
        repository = AnalysisRepository(store)
        repository.save("practice_001", make_analysis())

    with EventStore(path) as store:
        repository = AnalysisRepository(store)

        assert repository.count("practice_001") == 1
        assert repository.count("another_session") == 0


def test_empty_session_id_is_rejected(tmp_path: Path) -> None:
    """Reject an analysis without an owning session."""
    with EventStore(tmp_path / "test.sqlite3") as store:
        repository = AnalysisRepository(store)

        with pytest.raises(ValueError):
            repository.save("", make_analysis())
