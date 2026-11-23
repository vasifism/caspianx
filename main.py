"""Local diagnostic entry point for CaspianX.

No outbound API calls are made by this command-line interface.
"""

from __future__ import annotations

import argparse
import json

from config.settings import Settings


def main() -> int:
    """Display validated, non-secret configuration diagnostics.

    Returns:
        Process status code (zero on success).

    """
    parser = argparse.ArgumentParser(description="CaspianX local diagnostics")
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate local configuration without connecting to services.",
    )
    args = parser.parse_args()
    if args.check_config:
        settings = Settings()
        print(json.dumps(settings.public_diagnostics(), indent=2))
        print("Configuration OK (no network requests performed).")
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
