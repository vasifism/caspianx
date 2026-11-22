"""Run CaspianX quality checks and the offline replay demonstration."""

from __future__ import annotations

import argparse
import subprocess
import sys


CHECKS: tuple[tuple[str, ...], ...] = (
    ("-m", "ruff", "check", "."),
    ("-m", "ruff", "format", "--check", "."),
    ("-m", "pytest", "-q"),
    ("-m", "scripts.demo_replay"),
)


def run_checks(*, skip_demo: bool = False) -> int:
    """Run sequential checks and stop at the first failure.

    Args:
        skip_demo: Skip the offline replay demonstration.

    Returns:
        Zero if every selected check succeeds, otherwise an error code.

    """
    for arguments in CHECKS:
        if skip_demo and arguments[1] == "scripts.demo_replay":
            continue
        command = [sys.executable, *arguments]
        print("Running:", " ".join(command), flush=True)
        outcome = subprocess.run(command, check=False)
        if outcome.returncode:
            print("FAILED:", " ".join(arguments), flush=True)
            return outcome.returncode
    print("CaspianX verification: PASSED", flush=True)
    return 0


def main() -> int:
    """Parse command-line options and execute the verification suite."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-demo", action="store_true")
    args = parser.parse_args()
    return run_checks(skip_demo=args.skip_demo)


if __name__ == "__main__":
    raise SystemExit(main())
