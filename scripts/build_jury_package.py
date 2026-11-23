"""Create a deterministic jury materials archive from a strict file allowlist."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ALLOWED_FILES: tuple[str, ...] = (
    "ARCHITECTURE.md",
    "docs/ARCHITECTURE_ONE_PAGE.pdf",
    "docs/CaspianX_Pitch.pdf",
    "docs/CaspianX_Pitch.pptx",
    "docs/DEMO_RUNBOOK.md",
    "docs/PITCH_SCRIPT.md",
    "docs/SCORING_ALIGNMENT.md",
    "docs/HANDOFF_README.md",
)


def hash_bytes(data: bytes) -> str:
    """Compute the SHA-256 digest of a document's bytes."""
    return hashlib.sha256(data).hexdigest()


def collect_materials(root: Path) -> dict[str, bytes]:
    """Collect only known presentation files from an existing project.

    Args:
        root: CaspianX repository root.

    Returns:
        Mapping of safe archive member names to document bytes.

    Raises:
        FileNotFoundError: If required architecture materials are missing.
        ValueError: If a material resolves outside the project root.

    """
    resolved_root = root.resolve()
    collected: dict[str, bytes] = {}
    for name in ALLOWED_FILES:
        source = root / name
        resolved = source.resolve()
        if not resolved.is_relative_to(resolved_root):
            raise ValueError("Architecture material resolves outside the project.")
        if not source.is_file():
            raise FileNotFoundError(f"Missing required document: {name}")
        collected[name] = source.read_bytes()
    return collected


def build_package(root: Path, destination: Path) -> dict[str, Any]:
    """Build a shareable archive without source secrets or local event data.

    Args:
        root: CaspianX repository root.
        destination: Zip file to create.

    Returns:
        Deterministic manifest of archived file names and hashes.

    Raises:
        ValueError: If the output file is within the input allowlist.

    """
    materials = collect_materials(root)
    if destination.resolve() in {(root / name).resolve() for name in ALLOWED_FILES}:
        raise ValueError("Output must not overwrite an input document.")

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "archive_purpose": "jury_materials_only",
        "files": {name: hash_bytes(data) for name, data in sorted(materials.items())},
        "excludes": [".env", "database", "event_payloads", "API_keys"],
        "disclaimer": "Synthetic replay is not evidence of a scoring incident.",
    }
    materials["MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode()

    destination.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(destination, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in sorted(materials.items()):
            entry = ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            archive.writestr(entry, data)
    return manifest


def verify_package(path: Path) -> bool:
    """Verify expected members and hashes in an existing jury archive."""
    with ZipFile(path) as archive:
        members = set(archive.namelist())
        if members != set(ALLOWED_FILES) | {"MANIFEST.json"}:
            return False
        manifest = json.loads(archive.read("MANIFEST.json"))
        return all(
            hash_bytes(archive.read(name)) == digest for name, digest in manifest["files"].items()
        ) and set(manifest["files"]) == set(ALLOWED_FILES)


def main() -> int:
    """Build and verify the shareable presentation materials archive."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("CaspianX_Jury_Materials.zip"))
    options = parser.parse_args()
    try:
        manifest = build_package(options.root, options.out)
        verified = verify_package(options.out)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"JURY PACKAGE: FAIL ({type(error).__name__}: {error})")
        return 1
    print(f"Included documents: {len(manifest['files'])}")
    print("Database and .env included: NO (document contents require review)")
    print("JURY PACKAGE: " + ("PASS" if verified else "FAIL"))
    return 0 if verified else 1


if __name__ == "__main__":
    raise SystemExit(main())
