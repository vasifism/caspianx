"""Load editable attack prompts from ``llm/prompts/*.md``.

Keeping the planner and composer system prompts in Markdown files lets the team
tune attack behaviour between runs without touching code. When a file is missing
or empty, the caller's inline default is used.
"""

from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parent.parent / "llm" / "prompts"


def load_prompt(name: str, default: str = "") -> str:
    """Load a named prompt file, falling back to a default when unavailable.

    Args:
        name: Prompt stem, resolved to ``llm/prompts/<name>.md``.
        default: Text returned when the file is missing or empty.

    Returns:
        The file's stripped contents, or ``default``.

    """
    try:
        text = (_DIR / f"{name}.md").read_text(encoding="utf-8").strip()
        return text or default
    except OSError:
        return default
