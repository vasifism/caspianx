"""Record, read, and replay attack sessions between the API and the engine.

The engine talks to a client with the sandbox API surface. This module provides
three interchangeable asynchronous clients: ``RecordingClient`` wraps a real
client and records each contact to a JSON file; ``RecordingSessionReader`` loads a
saved recording for analysis or the pitch; and ``ReplayClient`` serves a
recording's reactions back offline.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any


class RecordingClient:
    """Delegate to a backend client while recording the whole session."""

    _CONTACTS = {"message", "conversation", "turn"}

    def __init__(self, backend, out_dir: str = "recordings") -> None:
        """Wrap a backend client and prepare the recording buffer.

        Args:
            backend: The client to delegate to (typically ``AttackClient``).
            out_dir: Directory the recording JSON is written to.

        """
        self.backend = backend
        self.out_dir = out_dir
        self.rec: dict[str, Any] = {"session_id": None, "scenario": None, "entries": []}
        self._path: str | None = None

    def _log(self, kind: str, request: dict, response: Any) -> None:
        """Append one recorded entry.

        Args:
            kind: Entry kind (``message``, ``page``, ``conversation``, ``turn``).
            request: The request that was sent.
            response: The response that came back.

        """
        events = response.get("events", []) if isinstance(response, dict) else []
        self.rec["entries"].append(
            {
                "ts": time.time(),
                "kind": kind,
                "request": request,
                "response": response,
                "events": events,
            }
        )

    def _flush(self) -> None:
        """Write the recording buffer to disk."""
        if self._path:
            with open(self._path, "w", encoding="utf-8") as handle:
                json.dump(self.rec, handle, indent=2, default=str)

    async def start_session(self, scenario_id):
        """Start a session and open a recording file.

        Args:
            scenario_id: The scenario to open a session in.

        Returns:
            The created session record.

        """
        record = await self.backend.start_session(scenario_id)
        self.rec["session_id"] = record.get("session_id")
        self.rec["scenario"] = scenario_id
        os.makedirs(self.out_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self._path = os.path.join(self.out_dir, f"{self.rec['session_id']}-{stamp}.json")
        return record

    async def get_session(self, sid):
        """Delegate to the backend ``get_session``."""
        return await self.backend.get_session(sid)

    async def get_events(self, sid):
        """Delegate to the backend ``get_events``."""
        return await self.backend.get_events(sid)

    async def end_session(self, sid):
        """End the session and flush the recording."""
        record = await self.backend.end_session(sid)
        self._flush()
        return record

    async def register_page(self, sid, **kwargs):
        """Register a page and record it."""
        record = await self.backend.register_page(sid, **kwargs)
        self._log("page", {"sid": sid, **kwargs}, record)
        return record

    async def send_message(self, sid, **kwargs):
        """Send a message, record it, and flush."""
        record = await self.backend.send_message(sid, **kwargs)
        self._log("message", {"sid": sid, **kwargs}, record)
        self._flush()
        return record

    async def start_conversation(self, sid, **kwargs):
        """Start a conversation, record it, and flush."""
        record = await self.backend.start_conversation(sid, **kwargs)
        self._log("conversation", {"sid": sid, **kwargs}, record)
        self._flush()
        return record

    async def send_turn(self, cid, say, **kwargs):
        """Send a turn, record it, and flush."""
        record = await self.backend.send_turn(cid, say, **kwargs)
        self._log("turn", {"cid": cid, "say": say, **kwargs}, record)
        self._flush()
        return record

    async def end_conversation(self, cid):
        """Delegate to the backend ``end_conversation``."""
        return await self.backend.end_conversation(cid)

    async def upload_asset(self, path):
        """Delegate to the backend ``upload_asset``."""
        return await self.backend.upload_asset(path)

    async def close(self):
        """Flush the recording and close the backend."""
        self._flush()
        await self.backend.close()

    @property
    def recording_path(self) -> str | None:
        """Return the path of the recording file, if started."""
        return self._path


class RecordingSessionReader:
    """Load a saved recording for analysis, replay, or the pitch."""

    def __init__(self, path: str) -> None:
        """Load a recording from disk.

        Args:
            path: Path to the recording JSON file.

        """
        self.path = path
        with open(path, encoding="utf-8") as handle:
            self.data = json.load(handle)
        self.entries: list[dict] = self.data.get("entries", [])

    @property
    def session_id(self) -> str | None:
        """Return the recorded session id."""
        return self.data.get("session_id")

    def contacts(self) -> list[dict]:
        """Return the contact entries (messages, conversations, turns)."""
        return [item for item in self.entries if item.get("kind") in RecordingClient._CONTACTS]

    def event_sequence(self) -> list[list[dict]]:
        """Return the recorded events for each contact, in order.

        Returns:
            One event list per contact, for replay.

        """
        return [item.get("events", []) for item in self.contacts()]

    def transcript(self) -> str:
        """Render the recording as a readable transcript.

        Returns:
            A readable transcript of contacts and reactions.

        """
        out = [f"Recording {self.session_id} ({self.data.get('scenario')})", "=" * 60]
        for entry in self.entries:
            kind, request = entry.get("kind"), entry.get("request", {})
            if kind == "message":
                out.append(
                    f"[MSG {request.get('channel')}] subj: {request.get('subject', '')}\n"
                    f"{request.get('body', '')}"
                )
            elif kind == "page":
                out.append(f"[PAGE] {request.get('url')} fields={request.get('fields')}")
            elif kind == "conversation":
                out.append(f"[CALL {request.get('channel')}] from {request.get('from_')}")
            elif kind == "turn":
                out.append(f"[SAY] {request.get('say', '')}")
            for event in entry.get("events", []):
                etype = event.get("type")
                if etype == "reply":
                    out.append(f"   <- reply: {event.get('body', '')}")
                else:
                    payload = {key: value for key, value in event.items() if key != "type"}
                    out.append(f"   <- {etype}: {json.dumps(payload)}")
        return "\n".join(out)


def _first_reply(events: list[dict]) -> str:
    """Return the first reply body in a list of events.

    Args:
        events: Events to scan.

    Returns:
        The first reply body, or a default greeting.

    """
    for event in events:
        if event.get("type") == "reply":
            return event.get("body", "")
    return "Hello?"


class ReplayClient:
    """Serve a recording's reactions back in order, offline."""

    def __init__(self, reader: RecordingSessionReader) -> None:
        """Prepare replay state from a reader.

        Args:
            reader: The loaded recording to replay.

        """
        self._seq = reader.event_sequence()
        self._i = 0
        self._t = 0

    async def start_session(self, scenario_id):
        """Reset replay state and return a synthetic session."""
        self._i, self._t = 0, 0
        return {
            "session_id": "replay",
            "scenario_id": scenario_id,
            "touch_budget": 10,
            "touches_used": 0,
            "status": "active",
        }

    async def get_session(self, sid):
        """Return a synthetic session with the current touch count."""
        return {"session_id": sid, "touches_used": self._t, "status": "active"}

    async def get_events(self, sid):
        """Return no extra events (replay serves events per contact)."""
        return []

    async def end_session(self, sid):
        """Return a synthetic end acknowledgement."""
        return {"status": "ended"}

    async def register_page(self, sid, **kwargs):
        """Return a synthetic page id."""
        return {"page_id": "replay_p"}

    def _next(self) -> list[dict]:
        """Return the next recorded event list.

        Returns:
            The next contact's events, or an empty list past the end.

        """
        events = self._seq[self._i] if self._i < len(self._seq) else []
        self._i += 1
        return events

    async def send_message(self, sid, **kwargs):
        """Serve the next recorded reaction as a message response."""
        self._t += 1
        return {"message_id": f"replay_m{self._t}", "touches_used": self._t, "events": self._next()}

    async def start_conversation(self, sid, **kwargs):
        """Serve the next recorded reaction as a conversation start."""
        self._t += 1
        events = self._next()
        return {
            "conversation_id": "replay_c",
            "status": "answered",
            "persona_says": _first_reply(events),
            "touches_used": self._t,
        }

    async def send_turn(self, cid, say, **kwargs):
        """Serve the next recorded reaction as a turn response."""
        events = self._next()
        return {
            "persona_says": _first_reply(events),
            "ended": not events,
            "events": events,
            "turns_used": 1,
        }

    async def end_conversation(self, cid):
        """Return a synthetic end acknowledgement."""
        return {"status": "ended"}

    async def close(self):
        """No-op close for interface parity."""
