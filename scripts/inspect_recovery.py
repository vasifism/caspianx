"""Display read-only recovery diagnostics for a practice session."""

from __future__ import annotations

import sys
from datetime import timedelta

from config.settings import Settings
from core.recovery_diagnostics import RecoveryDiagnostics
from storage.event_store import EventStore


SESSION_ID = "s_678d0c7e74"


def main() -> int:
    """Inspect local execution state without accessing external APIs.

    Returns:
        Zero on successful inspection, otherwise one.

    """
    settings = Settings()

    print("CaspianX Recovery Diagnostics")
    print(f"Session: {SESSION_ID}")
    print("Mode: local read-only")
    print("External API calls: 0")

    try:
        with EventStore(settings.sqlite_path) as store:
            diagnostics = RecoveryDiagnostics(store)

            report = diagnostics.inspect(
                SESSION_ID,
                older_than=timedelta(minutes=5),
            )

            print(f"Active lease record: {'PRESENT' if report.lease_present else 'ABSENT'}")

            if report.lease_acquired_at is not None:
                print(f"Lease acquired at: {report.lease_acquired_at}")

            print(f"Potentially stale cycles: {len(report.stale_cycles)}")

            for cycle in report.stale_cycles:
                print(f"Cycle: {cycle.cycle_id} | Age: {cycle.age_seconds:.1f}s")

        if report.lease_present:
            print(
                "A lease exists. Its owner's liveness has not been "
                "verified. Do not remove it automatically."
            )

        if report.stale_cycles:
            print(
                "Old running cycles require investigation; "
                "age alone does not establish process failure."
            )

        print("Recovery inspection: OK")
        return 0

    except Exception as error:
        print(
            f"Recovery inspection failed: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
