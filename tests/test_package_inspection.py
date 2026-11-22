"""Test ZIP safety and lightweight text-secret detection."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from evaluation.package_inspection import inspect_package
from scripts.inspect_jury_package import main


def make_zip(path: Path, entries: dict[str, str | bytes]) -> Path:
    """Write a deterministic temporary ZIP containing selected test entries."""
    with ZipFile(path, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return path


def test_ordinary_document_zip_passes(tmp_path: Path) -> None:
    """Accept a safe, plaintext documentation archive."""
    report = inspect_package(make_zip(tmp_path / "a.zip", {"docs/README.md": "Hello"}))
    assert report.passed
    assert report.file_count == 1


def test_dotenv_is_rejected(tmp_path: Path) -> None:
    """Reject a shipped environment configuration."""
    report = inspect_package(make_zip(tmp_path / "a.zip", {".env": "PASSWORD=not-real"}))
    assert "ENV_FILE_INCLUDED" in report.findings


def test_database_is_rejected(tmp_path: Path) -> None:
    """Reject a local SQLite file included in a jury package."""
    report = inspect_package(make_zip(tmp_path / "a.zip", {"data/state.sqlite3": b"db"}))
    assert "DATABASE_INCLUDED" in report.findings


def test_path_traversal_is_rejected(tmp_path: Path) -> None:
    """Reject a ZIP entry escaping its extraction root."""
    report = inspect_package(make_zip(tmp_path / "a.zip", {"../secrets.txt": "text"}))
    assert "UNSAFE_ZIP_PATH" in report.findings


def test_git_directory_is_rejected(tmp_path: Path) -> None:
    """Exclude accidental Git repository contents."""
    report = inspect_package(make_zip(tmp_path / "a.zip", {".git/config": "text"}))
    assert "DEVELOPMENT_DIRECTORY_INCLUDED" in report.findings


def test_obvious_token_assignment_is_detected(tmp_path: Path) -> None:
    """Catch an explicitly assigned API key without printing the value."""
    report = inspect_package(
        make_zip(tmp_path / "a.zip", {"notes.md": "OPENAI_API_KEY=sk-examplekey1234567890"})
    )
    assert "POSSIBLE_PLAINTEXT_SECRET" in report.findings
    assert "sk-examplekey1234567890" not in str(report.to_dict())


def test_binary_documents_require_review(tmp_path: Path) -> None:
    """Warn that the ZIP scanner cannot inspect PDF binary metadata."""
    report = inspect_package(make_zip(tmp_path / "a.zip", {"docs/slide.pdf": b"%PDF"}))
    assert report.passed
    assert report.binary_files_require_manual_review


def test_env_example_is_allowed(tmp_path: Path) -> None:
    """Permit a placeholder-only example environment template."""
    report = inspect_package(
        make_zip(tmp_path / "a.zip", {".env.example": "OPENAI_API_KEY=placeholder"})
    )
    assert report.passed


def test_inspection_cli_passes(tmp_path: Path, monkeypatch, capsys) -> None:
    """Report a successful inspection without exporting file content."""
    archive = make_zip(tmp_path / "a.zip", {"notes.txt": "nothing sensitive"})
    monkeypatch.setattr("sys.argv", ["inspect_jury_package", "--zip", str(archive)])
    assert main() == 0
    assert "PACKAGE INSPECTION: PASS" in capsys.readouterr().out
