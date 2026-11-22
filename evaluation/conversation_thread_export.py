"""Export documented, non-secret transcripts from the SQLite conversation ledger."""

from __future__ import annotations

import json
from pathlib import Path

from storage.conversation_repository import ConversationRepository


def export_thread(db_path: Path, conversation_id: str) -> dict[str, object]:
    """Produce a transparent transcript without claiming verified incidents."""
    if not conversation_id.strip():
        raise ValueError("conversation_id is required")
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    with ConversationRepository(db_path) as ledger:
        row = ledger.connection.execute(
            """SELECT session_id, target_id, channel, status
            FROM cx_conversations WHERE conversation_id=?""",
            (conversation_id,),
        ).fetchone()
        if row is None:
            raise LookupError("Conversation not found")
        session_id, target_id, channel, status = row
        history = ledger.history(conversation_id)
        pending = len(ledger.pending(session_id))
    return {
        "conversation_id": conversation_id,
        "session_id": session_id,
        "target_id": target_id,
        "channel": channel,
        "status": status,
        "turn_count": sum(line["direction"] == "agent" for line in history),
        "transcript": history,
        "unresolved_operations": pending,
        "incident": "NOT VERIFIED",
        "warning": "Local conversation transcript is not an official scored-run replay.",
    }


def render_markdown(thread: dict[str, object]) -> str:
    """Render a human-readable jury preparation transcript from ledger data."""
    lines = [
        "# CaspianX Conversation Transcript",
        "",
        f"Session: `{thread['session_id']}`",
        f"Conversation: `{thread['conversation_id']}`",
        f"Channel: `{thread['channel']}`",
        f"Status: `{thread['status']}`",
        "",
        "**Incident:** NOT VERIFIED",
        "",
        "> Local record only. Confirm scored outcomes with revel8.",
        "",
    ]
    for index, item in enumerate(thread["transcript"], start=1):
        speaker = "Persona" if item["direction"] == "persona" else "Agent"
        # Preserve visible lines without interpreting a persona's reply as a command.
        message = str(item["body"]).replace("\r", " ").replace("\n", " ")
        lines.append(f"**{index}. {speaker}:** {message}")
        lines.append("")
    return "\n".join(lines)


def render_json(thread: dict[str, object]) -> str:
    """Serialize a local transcript as UTF-8 JSON without extra enrichment."""
    return json.dumps(thread, ensure_ascii=False, indent=2) + "\n"
