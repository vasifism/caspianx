"""Test persistent event-analysis caching and fingerprint isolation."""

from __future__ import annotations

from pathlib import Path

import pytest

from llm.schemas import EventAnalysis
from storage.event_store import EventStore
from storage.observation_cache import ObservationCache


def make_analysis() -> EventAnalysis:
    """Create a deterministic structured analysis for cache tests.

    Returns:
        Valid event analysis with no observed events.

    """
    return EventAnalysis(
        summary="No events were observed.",
        event_types=[],
        has_reply=False,
        uncertainties=["No reaction was recorded."],
        requires_review=False,
    )


def test_cache_miss_and_hit(tmp_path: Path) -> None:
    """Retrieve a saved analysis after an initial cache miss."""
    with EventStore(tmp_path / "cache.sqlite3") as store:
        cache = ObservationCache(store)

        fingerprint = cache.fingerprint(
            "practice_001",
            "test-model",
            [],
        )

        assert cache.get(fingerprint) is None

        expected = make_analysis()
        cache.save(fingerprint, expected)

        assert cache.get(fingerprint) == expected


def test_cache_survives_restart(tmp_path: Path) -> None:
    """Recover cached analyses after reopening SQLite."""
    path = tmp_path / "durable.sqlite3"

    with EventStore(path) as store:
        cache = ObservationCache(store)
        fingerprint = cache.fingerprint(
            "practice_001",
            "test-model",
            [],
        )
        cache.save(fingerprint, make_analysis())

    with EventStore(path) as store:
        cache = ObservationCache(store)

        assert cache.get(fingerprint) == make_analysis()


def test_fingerprint_changes_with_events() -> None:
    """Invalidate cached results when observable events change."""
    empty = ObservationCache.fingerprint(
        "practice_001",
        "test-model",
        [],
    )

    updated = ObservationCache.fingerprint(
        "practice_001",
        "test-model",
        [{"id": "event_001", "type": "message.opened"}],
    )

    assert empty != updated


def test_fingerprint_isolates_models_and_sessions() -> None:
    """Avoid sharing results across model or session boundaries."""
    baseline = ObservationCache.fingerprint(
        "practice_001",
        "model-a",
        [],
    )

    other_model = ObservationCache.fingerprint(
        "practice_001",
        "model-b",
        [],
    )

    other_session = ObservationCache.fingerprint(
        "practice_002",
        "model-a",
        [],
    )

    assert len({baseline, other_model, other_session}) == 3


def test_fingerprint_changes_with_analysis_version() -> None:
    """Invalidate cached analyses when analysis instructions change."""
    old_version = ObservationCache.fingerprint(
        "practice_001",
        "test-model",
        [],
        analysis_version="v1",
    )

    new_version = ObservationCache.fingerprint(
        "practice_001",
        "test-model",
        [],
        analysis_version="v2",
    )

    assert old_version != new_version


def test_duplicate_cache_writes_preserve_first_result(
    tmp_path: Path,
) -> None:
    """Prevent duplicate inserts from overwriting established analyses."""
    with EventStore(tmp_path / "cache.sqlite3") as store:
        cache = ObservationCache(store)

        fingerprint = cache.fingerprint(
            "practice_001",
            "test-model",
            [],
        )

        original = make_analysis()
        replacement = original.model_copy(update={"summary": "A different analysis."})

        cache.save(fingerprint, original)
        cache.save(fingerprint, replacement)

        assert cache.get(fingerprint) == original


def test_invalid_fingerprint_inputs() -> None:
    """Reject missing session and model identifiers."""
    with pytest.raises(ValueError):
        ObservationCache.fingerprint("", "test-model", [])

    with pytest.raises(ValueError):
        ObservationCache.fingerprint("practice_001", "", [])
