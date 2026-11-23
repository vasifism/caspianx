"""Configure SQLite database connections for CaspianX."""

from __future__ import annotations

from pathlib import Path

from peewee import SqliteDatabase


def create_database(path: str | Path) -> SqliteDatabase:
    """Create a configured SQLite database instance.

    Args:
        path: Filesystem path to the SQLite database.

    Returns:
        An unopened Peewee database instance configured for
        transactional persistence.

    """
    database_path = Path(path).expanduser()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    return SqliteDatabase(
        str(database_path),
        pragmas={
            "journal_mode": "wal",
            "foreign_keys": 1,
            "busy_timeout": 30000,
            "synchronous": "normal",
        },
        timeout=30,
        check_same_thread=False,
    )
