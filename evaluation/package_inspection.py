"""Inspect ZIP contents for structural and obvious text-secret exposure risks."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


_TEXT_EXTENSIONS = frozenset({".txt", ".md", ".json", ".yaml", ".yml", ".toml", ".py"})
_SECRET_LINE = re.compile(
    r"(?im)^\s*(?:export\s+)?(?:OPENAI_API_KEY|CASPIANX_TEAM_KEY|"
    r"CASPIANX_OPENAI_API_KEY|TARGET_API_KEY|SECRET_KEY)\s*[:=]\s*[\"']?"
    r"(?!\s*(?:$|<|\$\{|example|placeholder|changeme|your[_-]))[^\s\"']{12,}"
)
_MAX_TEXT_BYTES = 2_000_000
_MAX_ENTRIES = 500


@dataclass(frozen=True, slots=True)
class PackageInspection:
    """Describe ZIP inspection results without copying file contents."""

    passed: bool
    file_count: int
    findings: tuple[str, ...]
    binary_files_require_manual_review: bool

    def to_dict(self) -> dict[str, object]:
        """Represent inspection status as data suitable for sanitized JSON."""
        return {
            "passed": self.passed,
            "file_count": self.file_count,
            "findings": list(self.findings),
            "binary_files_require_manual_review": self.binary_files_require_manual_review,
        }


def inspect_package(path: str | Path) -> PackageInspection:
    """Check ZIP entry names and bounded text for common credential mistakes.

    This scanner is deliberately conservative and does not claim to inspect
    secrets embedded in PDFs, images or presentation binary metadata.

    Args:
        path: Existing ZIP archive to inspect.

    Returns:
        Structural and text-secret findings without raw contents.

    Raises:
        FileNotFoundError: If the archive does not exist.
        zipfile.BadZipFile: If the archive is malformed.

    """
    path = Path(path)
    findings: set[str] = set()
    has_binary = False
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > _MAX_ENTRIES:
            findings.add("TOO_MANY_ENTRIES")
        for info in entries[:_MAX_ENTRIES]:
            name = info.filename.replace("\\", "/")
            parts = PurePosixPath(name).parts
            if name.startswith("/") or ".." in parts or (parts and ":" in parts[0]):
                findings.add("UNSAFE_ZIP_PATH")
            normalized = {part.casefold() for part in parts}
            basename = parts[-1].casefold() if parts else ""
            if basename == ".env" or basename.startswith(".env.") and basename != ".env.example":
                findings.add("ENV_FILE_INCLUDED")
            if basename.endswith((".sqlite3", ".sqlite", ".db", ".sqlite3-wal")):
                findings.add("DATABASE_INCLUDED")
            if ".git" in normalized or ".venv" in normalized:
                findings.add("DEVELOPMENT_DIRECTORY_INCLUDED")
            if info.is_dir():
                continue
            if (
                info.file_size > _MAX_TEXT_BYTES
                and PurePosixPath(name).suffix.lower() in _TEXT_EXTENSIONS
            ):
                findings.add("TEXT_TOO_LARGE_TO_SCAN")
                continue
            if PurePosixPath(name).suffix.lower() in _TEXT_EXTENSIONS:
                with archive.open(info) as stream:
                    data = stream.read(_MAX_TEXT_BYTES + 1)
                if len(data) > _MAX_TEXT_BYTES:
                    findings.add("TEXT_TOO_LARGE_TO_SCAN")
                    continue
                try:
                    content = data.decode("utf-8")
                except UnicodeDecodeError:
                    findings.add("UNREADABLE_TEXT_FILE")
                    continue
                if _SECRET_LINE.search(content):
                    findings.add("POSSIBLE_PLAINTEXT_SECRET")
            else:
                has_binary = True
    return PackageInspection(
        passed=not findings,
        file_count=len(entries),
        findings=tuple(sorted(findings)),
        binary_files_require_manual_review=has_binary,
    )
