"""Define database-bound Peewee models for persistent state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from peewee import (
    AutoField,
    CharField,
    DateTimeField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
)


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp.

    Returns:
        Current datetime in UTC.

    """
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ModelRegistry:
    """Group ORM models associated with one database instance.

    Attributes:
        session: Model used to persist simulation sessions.
        event: Model used to persist simulation events.
        agent_state: Model used to persist agent state snapshots.

    """

    session: type[Model]
    event: type[Model]
    agent_state: type[Model]


def create_models(database: SqliteDatabase) -> ModelRegistry:
    """Create ORM models bound to the provided database.

    Args:
        database: Peewee database instance.

    Returns:
        Registry containing all application models.

    """
    bound_database = database

    class BaseModel(Model):
        """Provide a shared database binding for ORM models."""

        class Meta:
            """Configure the database for derived models."""

            database = bound_database

    class SessionRecord(BaseModel):
        """Persist simulation session metadata."""

        session_id = CharField(primary_key=True)
        scenario_id = CharField()
        status = CharField(default="active")
        touch_budget = IntegerField(default=0)
        touches_used = IntegerField(default=0)
        story_time = TextField(null=True)
        updated_at = DateTimeField(default=utc_now)

        class Meta:
            """Configure the session table."""

            table_name = "sessions"

    class EventRecord(BaseModel):
        """Persist sanitized events in insertion order."""

        sequence = AutoField()
        session_id = CharField(index=True)
        event_id = CharField()
        event_type = CharField(index=True)
        payload = TextField()
        created_at = DateTimeField(default=utc_now)

        class Meta:
            """Configure the event table and uniqueness constraint."""

            table_name = "events"
            indexes = ((("session_id", "event_id"), True),)

    class AgentStateRecord(BaseModel):
        """Persist an agent state snapshot for session recovery."""

        session_id = CharField(primary_key=True)
        state_json = TextField(default="{}")
        updated_at = DateTimeField(default=utc_now)

        class Meta:
            """Configure the agent state table."""

            table_name = "agent_states"

    return ModelRegistry(
        session=SessionRecord,
        event=EventRecord,
        agent_state=AgentStateRecord,
    )
