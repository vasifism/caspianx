"""Test SQLite session leases across independent Python processes."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from storage.event_store import EventStore
from storage.session_lease import SessionLeaseRepository


SESSION_ID = "multiprocess_test_session"

CHILD_PROGRAM = """
import sys
from pathlib import Path

from storage.event_store import EventStore
from storage.session_lease import SessionLeaseRepository

database_path = Path(sys.argv[1])
ready_path = Path(sys.argv[2])
session_id = sys.argv[3]

with EventStore(database_path) as store:
    leases = SessionLeaseRepository(store)
    token = leases.acquire(session_id)

    if token is None:
        sys.exit(2)

    ready_path.write_text("acquired", encoding="utf-8")
    sys.stdin.readline()
    leases.release(session_id, token)
"""


def start_child(
    database_path: Path,
    ready_path: Path,
) -> subprocess.Popen[str]:
    """Start a process that holds exclusive session ownership.

    Args:
        database_path: SQLite file shared with the parent process.
        ready_path: File used to signal successful acquisition.

    Returns:
        Running child process holding the session lease.

    Raises:
        RuntimeError: If the child fails to acquire ownership.
        TimeoutError: If the child does not become ready.

    """
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            CHILD_PROGRAM,
            str(database_path),
            str(ready_path),
            SESSION_ID,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )

    deadline = time.monotonic() + 10.0

    try:
        while time.monotonic() < deadline:
            if ready_path.exists():
                return process

            if process.poll() is not None:
                _, errors = process.communicate()
                raise RuntimeError(f"Child process exited unexpectedly: {errors}")

            time.sleep(0.02)

        raise TimeoutError("Child did not acquire the lease within the deadline.")

    except BaseException:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)
        raise


def test_second_process_cannot_acquire_active_lease(
    tmp_path: Path,
) -> None:
    """Block another process while the first one owns the session."""
    database_path = tmp_path / "shared.sqlite3"
    ready_path = tmp_path / "ready.txt"

    with EventStore(database_path) as store:
        SessionLeaseRepository(store)

    process = start_child(database_path, ready_path)

    try:
        with EventStore(database_path) as store:
            leases = SessionLeaseRepository(store)

            assert leases.get(SESSION_ID) is not None
            assert leases.acquire(SESSION_ID) is None

        assert process.stdin is not None
        process.stdin.write("\n")
        process.stdin.flush()

        assert process.wait(timeout=5) == 0

        with EventStore(database_path) as store:
            leases = SessionLeaseRepository(store)

            assert leases.get(SESSION_ID) is None

            new_token = leases.acquire(SESSION_ID)
            assert new_token is not None
            assert leases.release(SESSION_ID, new_token)

    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)

        if process.stdin is not None:
            process.stdin.close()


def test_killed_process_does_not_silently_release_lease(
    tmp_path: Path,
) -> None:
    """Preserve lease ownership after an abrupt process termination."""
    database_path = tmp_path / "interrupted.sqlite3"
    ready_path = tmp_path / "ready.txt"

    with EventStore(database_path) as store:
        SessionLeaseRepository(store)

    process = start_child(database_path, ready_path)

    try:
        with EventStore(database_path) as store:
            leases = SessionLeaseRepository(store)
            assert leases.get(SESSION_ID) is not None

        process.kill()
        process.wait(timeout=5)

        with EventStore(database_path) as store:
            leases = SessionLeaseRepository(store)

            abandoned = leases.get(SESSION_ID)

            assert abandoned is not None
            assert leases.acquire(SESSION_ID) is None

            # Do not automatically remove this lease. Recovery must
            # independently establish that the owner has stopped.

    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)

        if process.stdin is not None:
            process.stdin.close()
