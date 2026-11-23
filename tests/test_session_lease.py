"""Test exclusive session ownership across SQLite connections."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from storage.event_store import EventStore
from storage.session_lease import SessionLeaseRepository


def test_first_owner_acquires_lease(tmp_path: Path) -> None:
    """Acquire a session lease and inspect its persisted metadata."""
    with EventStore(tmp_path / "lease.sqlite3") as store:
        repository = SessionLeaseRepository(store)

        token = repository.acquire("practice_001")
        lease = repository.get("practice_001")

        assert isinstance(token, str)
        assert len(token) == 32
        assert lease is not None
        assert lease.session_id == "practice_001"
        assert lease.owner_token == token
        assert lease.acquired_at


def test_second_owner_is_rejected(tmp_path: Path) -> None:
    """Reject another acquisition while ownership is active."""
    with EventStore(tmp_path / "lease.sqlite3") as store:
        repository = SessionLeaseRepository(store)

        first_token = repository.acquire("practice_001")
        second_token = repository.acquire("practice_001")

        assert first_token is not None
        assert second_token is None


def test_ownership_is_shared_across_connections(
    tmp_path: Path,
) -> None:
    """Enforce ownership between separate SQLite connections."""
    database_path = tmp_path / "shared.sqlite3"

    with EventStore(database_path) as first_store:
        first = SessionLeaseRepository(first_store)
        token = first.acquire("practice_001")

        assert token is not None

        with EventStore(database_path) as second_store:
            second = SessionLeaseRepository(second_store)

            assert second.acquire("practice_001") is None

            lease = second.get("practice_001")
            assert lease is not None
            assert lease.owner_token == token


def test_wrong_owner_cannot_release_lease(tmp_path: Path) -> None:
    """Prevent a different owner from releasing an active lease."""
    with EventStore(tmp_path / "lease.sqlite3") as store:
        repository = SessionLeaseRepository(store)

        token = repository.acquire("practice_001")

        assert token is not None
        assert (
            repository.release(
                "practice_001",
                "incorrect-owner",
            )
            is False
        )

        assert repository.get("practice_001") is not None


def test_owner_can_release_and_reacquire(tmp_path: Path) -> None:
    """Permit a new owner after the previous owner releases."""
    with EventStore(tmp_path / "lease.sqlite3") as store:
        repository = SessionLeaseRepository(store)

        first_token = repository.acquire("practice_001")
        assert first_token is not None

        assert repository.release("practice_001", first_token)
        assert repository.get("practice_001") is None

        second_token = repository.acquire("practice_001")

        assert second_token is not None
        assert second_token != first_token


def test_independent_sessions_can_be_locked(
    tmp_path: Path,
) -> None:
    """Allow separate sessions to have different owners."""
    with EventStore(tmp_path / "lease.sqlite3") as store:
        repository = SessionLeaseRepository(store)

        first = repository.acquire("practice_001")
        second = repository.acquire("practice_002")

        assert first is not None
        assert second is not None
        assert first != second


def test_lease_survives_database_reopen(tmp_path: Path) -> None:
    """Preserve an unreleased lease across database restarts."""
    database_path = tmp_path / "durable.sqlite3"

    with EventStore(database_path) as store:
        repository = SessionLeaseRepository(store)
        token = repository.acquire("practice_001")

        assert token is not None

    with EventStore(database_path) as store:
        repository = SessionLeaseRepository(store)

        assert repository.acquire("practice_001") is None

        lease = repository.get("practice_001")
        assert lease is not None
        assert lease.owner_token == token


def test_invalid_lease_identifiers(tmp_path: Path) -> None:
    """Reject invalid session identifiers and owner tokens."""
    with EventStore(tmp_path / "lease.sqlite3") as store:
        repository = SessionLeaseRepository(store)

        with pytest.raises(ValueError):
            repository.acquire("")

        with pytest.raises(ValueError):
            repository.get(" ")

        with pytest.raises(ValueError):
            repository.release("practice_001", "")


def test_concurrent_acquisition_has_one_winner(
    tmp_path: Path,
) -> None:
    """Allow exactly one concurrent claimant to acquire ownership."""
    database_path = tmp_path / "concurrent.sqlite3"

    # Initialize the schema before concurrent connections open.
    with EventStore(database_path) as store:
        SessionLeaseRepository(store)

    barrier = Barrier(2)

    def attempt_acquisition() -> str | None:
        """Attempt to acquire the same lease from another thread."""
        with EventStore(database_path) as store:
            repository = SessionLeaseRepository(store)
            barrier.wait(timeout=5)
            return repository.acquire("practice_001")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(attempt_acquisition) for _ in range(2)]
        results = [future.result(timeout=10) for future in futures]

    winners = [token for token in results if token is not None]

    assert len(winners) == 1
