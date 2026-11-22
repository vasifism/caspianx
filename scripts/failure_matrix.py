"""Run an isolated, offline SQLite fault-injection matrix."""

from __future__ import annotations

from evaluation.failure_matrix import run_failure_matrix


def main() -> int:
    """Print deterministic fault-injection results and return a status code."""
    result = run_failure_matrix()
    for name, success in result.to_dict().items():
        print(f"{'PASS' if success else 'FAIL'} | {name}")
    print("FAILURE MATRIX: " + ("PASS" if result.passed else "FAIL"))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
