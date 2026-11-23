"""Decide which overall strategy an attack session should run."""

from __future__ import annotations

from enum import StrEnum

from offense.llm import LLM
from offense.models import Belief, Dossier


class Strategy(StrEnum):
    """Enumerate the supported attack strategies."""

    DIRECT = "direct"
    CORROBORATION = "corroboration"
    INBOUND = "inbound"


_DESCRIPTIONS = {
    Strategy.DIRECT: (
        "A single sender runs one pretext to the objective. Fewest moving parts "
        "and usually the fewest contacts; the default."
    ),
    Strategy.CORROBORATION: (
        "Two personas in the same session: persona A (internal-looking) primes the "
        "target and references an upcoming contact; persona B then makes the ask and "
        "arrives pre-trusted. Exploits that the target remembers every contact in a "
        "session regardless of sender. Costs an extra priming contact."
    ),
    Strategy.INBOUND: (
        "Engineer a situation where the target initiates the risky action themselves "
        "(a security alert they want to resolve, a support thread they open). Lowers "
        "suspicion because the action feels self-started."
    ),
}


class DecisionRouter:
    """Choose a strategy at session start and re-choose it under pushback.

    The planner then executes moves within the chosen strategy. Separating "which
    strategy" from "which next move" keeps each decision simple.
    """

    def __init__(self, llm: LLM) -> None:
        """Store the language model used for strategy selection.

        Args:
            llm: The configured language-model wrapper.

        """
        self.llm = llm

    async def choose(
        self,
        dossier: Dossier,
        belief: Belief,
        *,
        touches_used: int,
        touch_budget: int,
        current: Strategy | None = None,
    ) -> Strategy:
        """Select the strategy that best fits the target and current state.

        Args:
            dossier: What is known about the target.
            belief: The agent's current read of the target.
            touches_used: Touches spent so far this session.
            touch_budget: Total touch budget for the session.
            current: The strategy currently in effect, if any.

        Returns:
            The chosen strategy.

        """
        if self.llm.backend == "none":
            return self._fallback(belief, touches_used, touch_budget, current)
        chosen = await self._llm_choose(dossier, belief, touches_used, touch_budget, current)
        return chosen or self._fallback(belief, touches_used, touch_budget, current)

    async def _llm_choose(
        self,
        dossier: Dossier,
        belief: Belief,
        used: int,
        budget: int,
        current: Strategy | None,
    ) -> Strategy | None:
        """Ask the model to choose a strategy.

        Args:
            dossier: What is known about the target.
            belief: The agent's current read of the target.
            used: Touches spent so far this session.
            budget: Total touch budget for the session.
            current: The strategy currently in effect, if any.

        Returns:
            The model's chosen strategy, or ``None`` when unavailable or invalid.

        """
        options = "\n".join(f"- {item.value}: {text}" for item, text in _DESCRIPTIONS.items())
        system = (
            "You are the strategy router of a red-team agent in the revel8 sandbox. "
            "Pick the ONE strategy that best fits the target and the current state. "
            "Strongly prefer DIRECT and STAY on it: depth with one persona beats "
            "churning strangers, and the fastest wins come from sustaining a single "
            "credible line until the payload feels expected. A single refusal is NOT "
            "a reason to switch — deepen the same persona first. Switch to "
            "CORROBORATION or INBOUND only when DIRECT has genuinely failed over "
            "several touches (not one), and remember those spawn a NEW sender that "
            "resets trust and costs touches, so weigh the remaining budget."
        )
        user = (
            f"TARGET: {dossier.name} - {dossier.role}\nStrategies:\n{options}\n\n"
            f"Belief:\n{belief.summary()}\n"
            f"Touches used: {used}, remaining: {budget - used}. "
            f"Current strategy: {current.value if current else 'none'}.\n\n"
            'Return JSON: {"strategy":"direct|corroboration|inbound","why":""}'
        )
        data = await self.llm.complete_json(system, user, max_tokens=300, temperature=0.3)
        if not data:
            return None
        try:
            return Strategy(data.get("strategy", "direct"))
        except ValueError:
            return None

    def _fallback(
        self, belief: Belief, used: int, budget: int, current: Strategy | None
    ) -> Strategy:
        """Choose a strategy deterministically when no model is configured.

        Args:
            belief: The agent's current read of the target.
            used: Touches spent so far this session.
            budget: Total touch budget for the session.
            current: The strategy currently in effect, if any.

        Returns:
            The chosen strategy.

        """
        remaining = budget - used
        if current is None:
            return Strategy.DIRECT
        if belief.suspicion >= 0.6 and remaining >= 3:
            if current == Strategy.DIRECT:
                return Strategy.CORROBORATION
            if current == Strategy.CORROBORATION:
                return Strategy.INBOUND
        return current
