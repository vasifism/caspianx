"""Test secure, deterministic packaging of presentation materials."""

from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.build_jury_package import (
    ALLOWED_FILES,
    build_package,
    collect_materials,
    verify_package,
)


def make_documents(root: Path) -> None:
    """Create synthetic stand-ins for every required jury document."""
    for name in ALLOWED_FILES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"Example document: {name}".encode())


def test_package_contains_only_allowlisted_documents(tmp_path: Path) -> None:
    """Exclude .env and database files from the archive."""
    make_documents(tmp_path)
    (tmp_path / ".env").write_text("SECRET_TOKEN=example", encoding="utf-8")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "caspianx.sqlite3").write_bytes(b"private")
    output = tmp_path / "jury.zip"
    build_package(tmp_path, output)
    with ZipFile(output) as archive:
        names = set(archive.namelist())
        assert names == set(ALLOWED_FILES) | {"MANIFEST.json"}
        assert "SECRET_TOKEN" not in repr(names)
        assert json.loads(archive.read("MANIFEST.json"))["schema_version"] == 1
    assert verify_package(output)


def test_package_is_byte_reproducible(tmp_path: Path) -> None:
    """Produce identical archives for identical source documents."""
    make_documents(tmp_path)
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    build_package(tmp_path, first)
    build_package(tmp_path, second)
    assert first.read_bytes() == second.read_bytes()


def test_missing_document_is_rejected(tmp_path: Path) -> None:
    """Fail rather than produce a deceptively complete submission."""
    with pytest.raises(FileNotFoundError):
        collect_materials(tmp_path)


def test_modified_archive_fails_verification(tmp_path: Path) -> None:
    """Reject archives where content no longer matches the manifest."""
    make_documents(tmp_path)
    output = tmp_path / "jury.zip"
    build_package(tmp_path, output)
    with ZipFile(output, "a") as archive:
        archive.writestr("unexpected_secret.txt", "bad")
    assert verify_package(output) is False


def test_output_cannot_overwrite_source(tmp_path: Path) -> None:
    """Protect original presentation documents from output replacement."""
    make_documents(tmp_path)
    with pytest.raises(ValueError):
        build_package(tmp_path, tmp_path / ALLOWED_FILES[0])


def test_external_symlink_is_rejected(tmp_path: Path) -> None:
    """Refuse to package a document linked outside the project directory."""
    make_documents(tmp_path)
    outside = tmp_path.parent / f"external-{tmp_path.name}.pdf"
    outside.write_bytes(b"do not include")
    linked = tmp_path / "docs" / "CaspianX_Pitch.pdf"
    linked.unlink()
    linked.symlink_to(outside)
    with pytest.raises(ValueError):
        collect_materials(tmp_path)
