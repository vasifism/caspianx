"""Produce plausible ``sent_at`` timestamps for an attack session.

Story time (what the target believes about when each contact arrived) only moves
forward: a ``sent_at`` earlier than the last contact returns 409 and spends no
touch. Contacts bunched seconds apart read as "being chased", and sends at night
or on a weekend read as off. This clock keeps time moving forward in human-sized
gaps inside business hours, so pacing never raises suspicion on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

# German time (CET, UTC+1 in November); the API reads an offset-less sent_at as
# German time, so an explicit offset is sent for clarity.
_TZ = timezone(timedelta(hours=1))

# Pace -> how far story time jumps before the next contact.
_GAPS = {
    "open": timedelta(0),
    "same_thread": timedelta(minutes=18),
    "follow_up": timedelta(hours=5),
    "next_day": timedelta(days=1),
}


@dataclass
class StoryClock:
    """Advance a monotonic, business-hours story clock for one session."""

    now: datetime = field(default=None)
    day_start: int = 8
    day_end: int = 19

    def __post_init__(self) -> None:
        """Initialise the clock at the next plausible business morning."""
        if self.now is None:
            start = datetime.now(_TZ).replace(hour=9, minute=11, second=0, microsecond=0)
            self.now = self._clamp(start)

    def _clamp(self, value: datetime) -> datetime:
        """Roll a timestamp out of nights and weekends into business hours.

        Args:
            value: A candidate story time.

        Returns:
            The next time at or after ``value`` that falls on a weekday within
            the configured business window.

        """
        for _ in range(10):
            if value.weekday() >= 5:
                value = (value + timedelta(days=1)).replace(
                    hour=9, minute=11, second=0, microsecond=0
                )
            elif value.hour < self.day_start:
                value = value.replace(hour=9, minute=11, second=0, microsecond=0)
            elif value.hour >= self.day_end:
                value = (value + timedelta(days=1)).replace(
                    hour=9, minute=11, second=0, microsecond=0
                )
            else:
                break
        return value

    def advance(self, pace: str = "follow_up") -> str:
        """Advance the clock by the given pace and return the new timestamp.

        Args:
            pace: One of ``open``, ``same_thread``, ``follow_up``, ``next_day``.

        Returns:
            The new story time as an ISO 8601 string with a UTC offset.

        """
        self.now = self._clamp(self.now + _GAPS.get(pace, _GAPS["follow_up"]))
        return self.now.isoformat()

    def current(self) -> str:
        """Return the current story time as an ISO 8601 string."""
        return self.now.isoformat()


def pace_for(phase: str, first_contact: bool) -> str:
    """Map an agent phase to a story-time pace.

    Args:
        phase: The current session phase value.
        first_contact: Whether this is the first contact of the session.

    Returns:
        A pace key understood by :meth:`StoryClock.advance`.

    """
    if first_contact:
        return "open"
    return {
        "probe": "follow_up",
        "engage": "same_thread",
        "escalate": "same_thread",
        "recover": "next_day",
    }.get(phase, "follow_up")
