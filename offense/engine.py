"""Coordinate the research -> contact -> read -> adapt attack loop.

One run is one session against one target. It stops at the first incident or when
the touch budget is spent. Within a session everything is awaited sequentially
(the API serializes per session). A turn-by-turn thread is written for the pitch,
and the outcome is recorded to the SQLite store off the event loop.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import asdict

from offense.attack_client import APIError, AttackClient
from offense.composer import Composer
from offense.decision_router import DecisionRouter
from offense.llm import LLM
from offense.memory import SessionMemory
from offense.models import Belief, Dossier, Incident
from offense.observation_runner import ObservationRunner
from offense.perception import Perception
from offense.planner import Planner
from offense.research import Researcher
from offense.state_machine import Phase, SessionStateMachine
from offense.store import SQLiteStore
from offense.story_clock import StoryClock, pace_for

_LIVE_CHANNELS = {"phone_call", "video_call", "teams_call", "live_chat"}


class AttackEngine:
    """Run the full attack loop for a single session."""

    def __init__(self, client: AttackClient, llm: LLM) -> None:
        """Wire the engine's collaborators.

        Args:
            client: The send-capable sandbox client.
            llm: The configured language-model wrapper.

        """
        self.client = client
        self.researcher = Researcher(llm)
        self.router = DecisionRouter(llm)
        self.planner = Planner(llm)
        self.composer = Composer(llm)
        self.perception = Perception(llm)
        self.store = SQLiteStore()

    async def run_session(
        self,
        *,
        scenario_id: str,
        target_id: str,
        objective_pref: str | None = None,
        target_name: str = "",
        target_role: str = "",
        language: str = "",
        facts: list[str] | None = None,
        max_touches: int | None = None,
        first_channel: str | None = None,
    ) -> dict:
        """Run one attack session against a target.

        Args:
            scenario_id: The scenario to run in.
            target_id: The target identifier.
            objective_pref: An objective to prefer, if any.
            target_name: Revealed display name, if any.
            target_role: Revealed role or title, if any.
            language: Language to write in, if known.
            facts: Verified facts gathered about the target.
            max_touches: Optional override of the session touch budget.
            first_channel: Optional channel to force on the opening contact.

        Returns:
            The run result summary.

        """
        dossier = await self.researcher.build_dossier(
            target_id, name=target_name, role=target_role, language=language, facts=facts
        )
        mem = SessionMemory(target_id)
        belief = Belief()
        state = SessionStateMachine()
        clock = StoryClock()
        observer = ObservationRunner(self.perception)

        session = await self.client.start_session(scenario_id)
        sid = session["session_id"]
        budget = max_touches or session.get("touch_budget", 10)
        incident = Incident()
        first = True
        prev_used = -1
        stall = 0
        silent = 0
        strategy = await self.router.choose(
            dossier, belief, touches_used=0, touch_budget=budget
        )
        log(f"session {sid} vs {dossier.name} | budget {budget} | strategy {strategy.value}")

        try:
            while not incident.reached:
                used = await session_touches(self.client, sid)
                if used >= budget:
                    break
                # No touch was spent since the last loop (e.g. a rejected send);
                # stop after a few stalls so a bad plan cannot spin forever.
                stall = stall + 1 if used == prev_used else 0
                if stall >= 3:
                    log("       stopping: no progress after repeated failed contacts")
                    break
                prev_used = used
                phase = state.update(belief, incident, used, budget)
                if phase == Phase.RECOVER:
                    strategy = await self.router.choose(
                        dossier, belief, touches_used=used, touch_budget=budget, current=strategy
                    )
                plan = await self.planner.plan(
                    dossier,
                    belief,
                    mem.transcript(),
                    touches_used=used,
                    touch_budget=budget,
                    objective_pref=objective_pref,
                    phase=phase.value,
                    strategy=strategy.value,
                )
                if used == 0 and first_channel:
                    plan.channel = first_channel
                    plan.mode = "conversation" if first_channel in _LIVE_CHANNELS else "message"
                sent_at = clock.advance(pace_for(phase.value, first))
                first = False
                log(
                    f"[t{used}] {phase.value}/{strategy.value} | plan: {plan.channel}/"
                    f"{plan.objective}/{plan.topic} link={plan.include_link} :: {plan.reasoning}"
                )

                if plan.mode == "conversation":
                    events = await self._run_conversation(sid, dossier, plan, mem, sent_at)
                else:
                    events = await self._run_message(sid, dossier, plan, mem, sent_at)

                observation = await observer.observe(
                    events, plan, belief, client=self.client, sid=sid
                )
                mem.record_events(observation.events)
                belief, incident = observation.belief, observation.incident
                if observation.question:
                    belief.notes.append(f"Must answer next: {observation.question}")
                log(f"       -> {belief.last_event_summary} | suspicion {belief.suspicion:.2f}")

                # A disengaged target is pure budget waste: stop after repeated
                # silence instead of emailing into the void (the speed metric).
                silent = silent + 1 if not observation.events else 0
                if silent >= 3:
                    log("       stopping: target disengaged (repeated silence)")
                    break

                # A burned target is also budget waste: once suspicion saturates
                # and nothing has landed, more contacts only push it higher and
                # read as desperate (the craft metric). Stop instead of flailing.
                if not incident.reached and belief.suspicion >= 0.9:
                    log("       stopping: target burned (suspicion saturated, no incident)")
                    break

            result = await self._finish(sid, scenario_id, dossier, mem, belief, incident, budget)
        finally:
            try:
                await self.client.end_session(sid)
            except APIError:
                pass
        return result

    async def _run_message(
        self,
        sid: str,
        dossier: Dossier,
        plan,
        mem: SessionMemory,
        sent_at: str | None = None,
    ) -> list[dict]:
        """Compose and send one message, returning its events.

        Args:
            sid: The session id.
            dossier: What is known about the target.
            plan: The decided move.
            mem: The session memory to update.
            sent_at: Optional story-time timestamp.

        Returns:
            The reaction events.

        """
        composed = await self.composer.compose(
            plan, dossier, mem.transcript(), mem.claims_block()
        )
        if composed.page:
            try:
                await self.client.register_page(
                    sid,
                    url=composed.page.url,
                    title=composed.page.title,
                    fields=composed.page.fields,
                    html=composed.page.html,
                    text=composed.page.text,
                )
                log(f"       page registered: {composed.page.url}")
            except APIError as error:
                log(f"       page register failed: {error}")
        attachments = [composed.attachment.to_api()] if composed.attachment else None
        try:
            response = await self.client.send_message(
                sid,
                to=dossier.target_id,
                channel=plan.channel,
                body=composed.body,
                from_=composed.from_ or None,
                subject=composed.subject,
                attachments=attachments,
                sent_at=sent_at,
            )
        except APIError as error:
            log(f"       send failed: {error}")
            return []
        mem.record_move(
            plan, {"subject": composed.subject, "body": composed.body, "from": composed.from_}
        )
        mem.add_claims(composed.claims)
        return response.get("events", [])

    async def _run_conversation(
        self,
        sid: str,
        dossier: Dossier,
        plan,
        mem: SessionMemory,
        sent_at: str | None = None,
        max_turns: int = 6,
    ) -> list[dict]:
        """Run one live conversation, returning its collected events.

        Args:
            sid: The session id.
            dossier: What is known about the target.
            plan: The decided move.
            mem: The session memory to update.
            sent_at: Optional story-time timestamp.
            max_turns: Maximum turns before ending the call.

        Returns:
            The collected events and persona replies.

        """
        collected: list[dict] = []
        try:
            conversation = await self.client.start_conversation(
                sid,
                to=dossier.target_id,
                channel=plan.channel,
                from_={"name": plan.sender_name, "address": plan.sender_address} or None,
                sent_at=sent_at,
            )
        except APIError as error:
            log(f"       conversation start failed: {error}")
            return []
        cid = conversation["conversation_id"]
        persona = conversation.get("persona_says", "")
        mem.record_move(
            plan,
            {
                "say": f"[call opens] {persona}",
                "from": {"name": plan.sender_name, "address": plan.sender_address},
            },
        )
        log(f"       call opened; persona: {persona!r}")

        for index in range(max_turns):
            composed = await self.composer.compose(
                plan,
                dossier,
                mem.transcript() + f"\n[PERSONA SAID] {persona}",
                mem.claims_block(),
            )
            say = _strip_html(composed.body)[:4000]
            try:
                turn = await self.client.send_turn(cid, say)
            except APIError as error:
                log(f"       turn failed: {error}")
                break
            mem.add_claims(composed.claims)
            mem.thread.append(
                {"t": time.time(), "kind": "move", "plan": asdict(plan), "rendered": {"say": say}}
            )
            persona = turn.get("persona_says", "")
            events = turn.get("events", [])
            collected.extend(events)
            if persona:
                collected.append(
                    {
                        "type": "reply",
                        "channel": plan.channel,
                        "body": persona,
                        "id": f"conv_{cid}_{index}",
                    }
                )
            log(f"       turn {index + 1}; persona: {persona!r}")
            if turn.get("ended") or events:
                break
        try:
            await self.client.end_conversation(cid)
        except APIError:
            pass
        return collected

    async def _finish(
        self,
        sid: str,
        scenario_id: str,
        dossier: Dossier,
        mem: SessionMemory,
        belief: Belief,
        incident: Incident,
        budget: int,
    ) -> dict:
        """Persist artefacts and return the run result.

        Args:
            sid: The session id.
            scenario_id: The scenario run in.
            dossier: What is known about the target.
            mem: The session memory.
            belief: The final belief.
            incident: The final incident status.
            budget: The session touch budget.

        Returns:
            The run result summary.

        """
        touches = await session_touches(self.client, sid)
        result = {
            "session_id": sid,
            "scenario": scenario_id,
            "target": dossier.target_id,
            "incident": incident.reached,
            "objective": incident.objective,
            "evidence": incident.evidence,
            "touches": touches,
            "final_suspicion": round(belief.suspicion, 2),
            "tried_topics": belief.tried_topics,
        }
        os.makedirs("runs", exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        base = f"runs/{dossier.target_id}-{stamp}"
        with open(base + ".json", "w", encoding="utf-8") as handle:
            json.dump(
                {"result": result, "thread": mem.thread, "claims": mem.claims}, handle, indent=2
            )
        with open(base + ".txt", "w", encoding="utf-8") as handle:
            handle.write(f"RUN vs {dossier.name} ({dossier.target_id})\n")
            handle.write(
                f"Incident: {incident.reached} ({incident.objective}) in {touches} touches\n"
            )
            handle.write("=" * 60 + "\n")
            handle.write(mem.transcript(limit=100))
        await asyncio.to_thread(self.store.record_run, result, mem.thread, mem.claims)
        log(
            f"DONE: incident={incident.reached} ({incident.objective}) "
            f"in {touches} touches -> {base}.txt"
        )
        return result


async def session_touches(client: AttackClient, sid: str) -> int:
    """Return the touches used in a session, defaulting to zero on error.

    Args:
        client: The sandbox client.
        sid: The session id.

    Returns:
        The number of touches used.

    """
    try:
        return (await client.get_session(sid)).get("touches_used", 0)
    except APIError:
        return 0


def _strip_html(value: str) -> str:
    """Strip HTML tags and entities for plain-text conversation lines.

    Args:
        value: HTML or plain text.

    Returns:
        A plain-text approximation.

    """
    return re.sub(r"<[^>]+>", " ", value).replace("&nbsp;", " ").strip()


def log(message: str) -> None:
    """Print a progress line for one engine step.

    Args:
        message: The line to print.

    """
    print(f"  {message}", flush=True)
