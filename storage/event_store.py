"""Persist and retrieve sanitized simulation events."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from peewee import IntegrityError

from storage.database import create_database
from storage.models import ModelRegistry, create_models


REDACTED = "[REDACTED]"

SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "passcode",
        "pin",
        "otp",
        "token",
        "api_key",
        "access_token",
        "refresh_token",
        "private_key",
        "client_secret",
        "authorization",
        "card_number",
        "iban",
    }
)


@dataclass(frozen=True, slots=True)
class StoredEvent:
    """Represent an immutable event retrieved from the database.

    Attributes:
        session_id: Identifier of the owning session.
        event_id: Event identifier assigned by the API.
        event_type: Classification of the event.
        payload: Sanitized event data.
        created_at: Timestamp of database insertion.

    """

    session_id: str
    event_id: str
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


def sanitize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Sanitize sensitive event data before persistence.

    Args:
        payload: Original event payload.

    Returns:
        A sanitized copy without submitted form values.

    """

    def sanitize_value(value: Any) -> Any:
        """Recursively redact sensitive dictionary entries.

        Args:
            value: JSON-compatible value to sanitize.

        Returns:
            Sanitized representation of the input.

        """
        if isinstance(value, Mapping):
            result = {}

            for key, item in value.items():
                normalized = str(key).casefold().replace("-", "_")

                if normalized in SENSITIVE_KEYS:
                    result[key] = REDACTED
                else:
                    result[key] = sanitize_value(item)

            return result

        if isinstance(value, list):
            return [sanitize_value(item) for item in value]

        return value

    sanitized = sanitize_value(dict(payload))

    if payload.get("type") == "page.submitted":
        if "values" in sanitized:
            sanitized["values"] = REDACTED

    return sanitized


class EventStore:
    """Manage persistent events through Peewee ORM."""

    def __init__(self, database_path: str | Path) -> None:
        """Initialize the event database and ORM models.

        Args:
            database_path: Path to the SQLite database file.

        """
        self.database = create_database(database_path)
        self.models: ModelRegistry = create_models(self.database)

        self.database.connect(reuse_if_open=True)
        self.database.create_tables(
            [
                self.models.session,
                self.models.event,
                self.models.agent_state,
            ],
            safe=True,
        )

    def append(
        self,
        session_id: str,
        event_id: str,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> bool:
        """Insert an event unless its identifier already exists.

        Args:
            session_id: Owning simulation session identifier.
            event_id: Unique event identifier within the session.
            event_type: Classification of the event.
            payload: Event data to sanitize and persist.

        Returns:
            True when inserted, or False when already present.

        Raises:
            ValueError: If a required identifier is empty.
            TypeError: If the payload is not JSON serializable.

        """
        identifiers = (session_id, event_id, event_type)

        if not all(isinstance(value, str) and value.strip() for value in identifiers):
            raise ValueError("Event identifiers cannot be empty.")

        sanitized = sanitize_payload(payload)

        serialized = json.dumps(
            sanitized,
            ensure_ascii=False,
            sort_keys=True,
        )

        with self.database.atomic():
            try:
                self.models.event.create(
                    session_id=session_id,
                    event_id=event_id,
                    event_type=event_type,
                    payload=serialized,
                )
            except IntegrityError:
                return False

        return True

    def list_events(self, session_id: str) -> list[StoredEvent]:
        """Retrieve the events of a session in insertion order.

        Args:
            session_id: Identifier of the requested session.

        Returns:
            A list of sanitized stored events.

        """
        model = self.models.event

        query = model.select().where(model.session_id == session_id).order_by(model.sequence.asc())

        return [
            StoredEvent(
                session_id=record.session_id,
                event_id=record.event_id,
                event_type=record.event_type,
                payload=json.loads(record.payload),
                created_at=record.created_at,
            )
            for record in query
        ]

    def count(self, session_id: str) -> int:
        """Count stored events for the given session.

        Args:
            session_id: Identifier of the requested session.

        Returns:
            Number of stored events.

        """
        model = self.models.event

        return model.select().where(model.session_id == session_id).count()

    def close(self) -> None:
        """Close the database connection."""
        if not self.database.is_closed():
            self.database.close()

    def __enter__(self) -> EventStore:
        """Enter the event store context manager.

        Returns:
            The active event store.

        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        """Close the event store when exiting its context.

        Args:
            exc_type: Exception type, if present.
            exc_value: Exception instance, if present.
            traceback: Exception traceback, if present.

        """
        self.close()
