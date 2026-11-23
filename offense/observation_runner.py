"""Run the full observation step for one contact."""

from __future__ import annotations

from dataclasses import dataclass, field

from offense.models import Belief, Incident, Plan
from offense.perception import Perception


@dataclass
class Observation:
    """Hold the result of observing the reaction to one contact."""

    belief: Belief
    incident: Incident
    question: str = ""
    events: list = field(default_factory=list)


class ObservationRunner:
    """Collect and read the reaction to each contact into a belief update.

    The runner merges the events returned by a send with the session event log
    (a reply can arrive across touches), de-duplicates what has already been seen,
    and reads the fresh events into an updated belief and any incident via
    Perception. It is created per session because it tracks seen event ids.
    """

    def __init__(self, perception: Perception) -> None:
        """Store the perception used to read events.

        Args:
            perception: The perception that interprets events.

        """
        self.perception = perception
        self._seen: set[str] = set()

    async def observe(
        self, events: list[dict], plan: Plan, belief: Belief, *, client=None, sid=None
    ) -> Observation:
        """Observe the reaction to a contact and update the belief.

        Args:
            events: Events returned by the send.
            plan: The plan that produced the contact.
            belief: The belief to update.
            client: Optional client used to poll the session event log.
            sid: Optional session id used with ``client``.

        Returns:
            The observation, including the updated belief and any incident.

        """
        pool = list(events)
        if client is not None and sid is not None:
            try:
                pool += await client.get_events(sid)
            except Exception:  # noqa: BLE001 - polling is best-effort
                pass

        fresh = []
        for event in pool:
            eid = event.get("id")
            if eid and eid in self._seen:
                continue
            if eid:
                self._seen.add(eid)
            fresh.append(event)

        belief, incident, question = await self.perception.interpret(fresh, plan, belief)
        return Observation(belief=belief, incident=incident, question=question, events=fresh)
