"""Check a jury ZIP for risky paths and obvious text secrets."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

from evaluation.package_inspection import inspect_package


def main() -> int:
    """Inspect an existing ZIP and report only safe diagnostic codes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, default=Path("build/CaspianX_Jury_Materials.zip"))
    args = parser.parse_args()
    try:
        report = inspect_package(args.zip)
    except (OSError, zipfile.BadZipFile) as error:
        print(f"PACKAGE INSPECTION: FAIL ({type(error).__name__})", file=sys.stderr)
        return 1
    print(f"Files checked: {report.file_count}")
    for code in report.findings:
        print(f"WARNING | {code}")
    if report.binary_files_require_manual_review:
        print("NOTICE | Binary documents and metadata still require manual review")
    print("PACKAGE INSPECTION: " + ("PASS" if report.passed else "FAIL"))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
