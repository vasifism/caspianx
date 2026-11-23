"""Module for tests test story clock.py."""

import pytest
from datetime import datetime, timezone

from core.story_clock import StoryClock, parse_story_time


def test_unset_clock_does_not_advance_on_check():
    """Verify unset clock does not advance on check."""
    clock = StoryClock()
    assert clock.check(None) is None
    assert clock.current is None


def test_naive_iso_uses_german_local_time():
    """Verify naive iso uses german local time."""
    assert parse_story_time("2026-11-23T09:14:00").isoformat() == "2026-11-23T09:14:00+01:00"


def test_epoch_and_utc_are_equivalent():
    """Verify epoch and utc are equivalent."""
    timestamp = datetime(2026, 11, 23, 8, 14, tzinfo=timezone.utc).timestamp()
    assert parse_story_time(timestamp) == parse_story_time("2026-11-23T08:14:00Z")


def test_time_cannot_move_backwards():
    """Verify time cannot move backwards."""
    clock = StoryClock()
    clock.confirm("2026-11-23T09:14:00+01:00")
    with pytest.raises(ValueError):
        clock.check("2026-11-23T09:13:59+01:00")


def test_same_timestamp_is_allowed():
    """Verify same timestamp is allowed."""
    clock = StoryClock()
    clock.confirm("2026-11-23T09:14:00+01:00")
    assert clock.check(None) == clock.current
    assert clock.check("2026-11-23T09:14:00+01:00") == clock.current


def test_check_does_not_advance_until_confirmed():
    """Verify check does not advance until confirmed."""
    clock = StoryClock()
    clock.check("2026-11-23T09:14:00+01:00")
    assert clock.current is None
    clock.confirm("2026-11-23T09:14:00+01:00")
    assert clock.serialize() == "2026-11-23T09:14:00+01:00"


def test_server_sync_after_restart():
    """Verify server sync after restart."""
    clock = StoryClock()
    clock.sync_server("2026-11-23T10:14:00+01:00")
    assert clock.serialize() == "2026-11-23T10:14:00+01:00"
    clock.sync_server(None)
    assert clock.current is None
