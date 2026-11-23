"""Virtual session clock for the API's optional sent_at / story_time fields.

The clock does not generate timestamps or drive actions by itself.
It validates monotonically non-decreasing *simulation* time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


def parse_story_time(
    raw: str | int | float | datetime,
    *,
    timezone: str = "Europe/Berlin",
) -> datetime:
    """Parse ISO 8601 (including Z) or Unix epoch seconds into aware datetime."""
    tz = ZoneInfo(timezone)
    if isinstance(raw, bool):
        raise TypeError("Boolean is not a valid timestamp")
    if isinstance(raw, (int, float)):
        from datetime import timezone as utc_timezone

        return datetime.fromtimestamp(raw, tz=utc_timezone.utc).astimezone(tz)
    if isinstance(raw, str):
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    elif isinstance(raw, datetime):
        parsed = raw
    else:
        raise TypeError("Expected ISO 8601, Unix seconds, or datetime")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


@dataclass(slots=True)
class StoryClock:
    """Holds one session's last server-confirmed story time."""

    timezone: str = "Europe/Berlin"
    current: datetime | None = None

    def __post_init__(self) -> None:
        """Validate the timezone and normalize an initial timestamp."""
        ZoneInfo(self.timezone)
        if self.current is not None:
            self.current = parse_story_time(self.current, timezone=self.timezone)

    def check(self, sent_at: str | int | float | datetime | None) -> datetime | None:
        """Validate without advancing: the server may still reject the request."""
        if sent_at is None:
            return self.current
        candidate = parse_story_time(sent_at, timezone=self.timezone)
        if self.current is not None and candidate < self.current:
            raise ValueError("sent_at precedes the session's last confirmed story_time")
        return candidate

    def sync_server(self, story_time: str | int | float | datetime | None) -> None:
        """Synchronize from GET /sessions/{sid}; null means unset."""
        self.current = (
            None if story_time is None else parse_story_time(story_time, timezone=self.timezone)
        )

    def confirm(self, sent_at: str | int | float | datetime | None) -> None:
        """Advance only after the server confirms a request succeeded."""
        self.current = self.check(sent_at)

    def serialize(self) -> str | None:
        """Return the current story time as an ISO 8601 string, if set."""
        return self.current.isoformat() if self.current is not None else None
