"""Evaluate scoring-window readiness without sending any contact."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SessionAssessment:
    """Describe one known session's scoring-window constraints."""

    session_id: str
    scenario_id: str
    status: str
    used: int
    budget: int
    remaining: int
    concerns: tuple[str, ...]


def assess_session(session: dict[str, Any]) -> SessionAssessment:
    """Validate and summarize server-observed session metadata."""
    sid = str(session.get("session_id", ""))
    scenario = str(session.get("scenario_id", ""))
    status = str(session.get("status", ""))
    used = int(session.get("touches_used", -1))
    budget = int(session.get("touch_budget", -1))
    if not sid or scenario not in {"practice", "eval"}:
        raise ValueError("Invalid session identity")
    if used < 0 or budget < 0 or used > budget:
        raise ValueError("Invalid contact budget")
    concerns: list[str] = []
    if status != "active":
        concerns.append("session_not_active")
    if budget - used == 0:
        concerns.append("budget_exhausted")
    if scenario == "eval" and budget != 10:
        concerns.append("unexpected_eval_budget")
    return SessionAssessment(sid, scenario, status, used, budget, budget - used, tuple(concerns))


def assess_scenarios(scenarios: list[dict[str, Any]]) -> dict[str, object]:
    """Identify revealed target IDs without inventing unreleased personas."""
    results: list[dict[str, object]] = []
    for item in scenarios:
        if not isinstance(item, dict):
            raise ValueError("Each scenario must be an object")
        targets = item.get("targets", [])
        if not isinstance(targets, list):
            raise ValueError("Targets must be a list")
        results.append(
            {
                "id": str(item.get("id", "")),
                "open": bool(item.get("open", False)),
                "kind": str(item.get("kind", "")),
                "target_ids": [str(t["id"]) for t in targets if isinstance(t, dict) and "id" in t],
                "targets_revealed": bool(targets),
                "touch_budget": item.get("touch_budget"),
            }
        )
    return {"scenarios": results, "contacts_sent": 0}
