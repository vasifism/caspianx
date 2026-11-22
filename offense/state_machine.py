"""Track the high-level phase of one attack session."""

from __future__ import annotations

from enum import StrEnum

from offense.models import Belief, Incident


class Phase(StrEnum):
    """Enumerate the phases an attack session moves through."""

    PROBE = "probe"
    ENGAGE = "engage"
    ESCALATE = "escalate"
    RECOVER = "recover"
    DONE = "done"
    EXHAUSTED = "exhausted"


class SessionStateMachine:
    """Derive the session phase from the current belief and events.

    Persistence is the planner reacting to the phase rather than following a fixed
    script: probe broadly when cold, escalate when warm, and recover when
    suspicion spikes. The phase is re-evaluated before every move.
    """

    def __init__(self) -> None:
        """Initialise the machine in the probing phase."""
        self.phase = Phase.PROBE

    def update(self, belief: Belief, incident: Incident, used: int, budget: int) -> Phase:
        """Re-evaluate and return the current phase.

        Args:
            belief: The agent's current read of the target.
            incident: Whether an incident has been reached.
            used: Touches spent so far this session.
            budget: Total touch budget for the session.

        Returns:
            The newly selected phase.

        """
        if incident.reached:
            self.phase = Phase.DONE
        elif used >= budget:
            self.phase = Phase.EXHAUSTED
        elif belief.suspicion >= 0.6:
            self.phase = Phase.RECOVER
        elif not belief.engaged:
            self.phase = Phase.PROBE
        elif belief.suspicion < 0.3:
            self.phase = Phase.ESCALATE
        else:
            self.phase = Phase.ENGAGE
        return self.phase

    @property
    def active(self) -> bool:
        """Return whether the session is still in progress."""
        return self.phase not in (Phase.DONE, Phase.EXHAUSTED)
