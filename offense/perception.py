"""Read the sparse event stream into an updated belief and any incident.

Structured signals are decisive: a submitted form counts as credentials only when
a secret was entered, and an opened attachment counts as an action. Replies need
judgement, so they are classified. Silence raises suspicion. The API never reveals
suspicion directly; it is inferred here.
"""

from __future__ import annotations

from offense.llm import LLM
from offense.models import Belief, Incident, Plan

# Field names the API treats as secrets -> a submission counts as credentials.
_SECRET_HINTS = (
    "password",
    "passwd",
    "pwd",
    "otp",
    "code",
    "pin",
    "token",
    "mfa",
    "2fa",
    "secret",
    "verification",
    "verify",
    "api_key",
    "apikey",
    "card",
    "iban",
)
_MASK = "(entered, not shown)"

# Basic details the API counts as "no objective" (just a step).
_BASIC = ("name", "email", "company", "job_title", "phone", "username")


class Perception:
    """Interpret reaction events against the plan that produced them."""

    def __init__(self, llm: LLM) -> None:
        """Store the language model used to classify replies.

        Args:
            llm: The configured language-model wrapper.

        """
        self.llm = llm

    async def interpret(
        self, events: list[dict], plan: Plan, belief: Belief
    ) -> tuple[Belief, Incident, str]:
        """Update the belief from events and detect any incident.

        Args:
            events: Reaction events for the latest contact.
            plan: The plan that produced the contact.
            belief: The belief to update in place.

        Returns:
            The updated belief, any incident, and a question to answer next.

        """
        belief.tried_topics = _append_unique(belief.tried_topics, plan.topic)
        belief.tried_channels = _append_unique(belief.tried_channels, plan.channel)
        question = ""

        if not events:
            belief.suspicion = min(1.0, belief.suspicion + 0.2)
            belief.last_event_summary = "silence (ignored)"
            belief.notes.append(f"No reaction to '{plan.topic}' via {plan.channel}.")
            return belief, Incident(), question

        belief.engaged = True

        for event in events:
            etype = event.get("type")
            if etype == "page.submitted":
                if _secret_submitted(event):
                    belief.last_event_summary = "page submitted - secret entered"
                    return belief, Incident(True, "credentials", event.get("id", "")), question
                if _form_disclosure(event):
                    belief.last_event_summary = "page submitted - internal info disclosed"
                    return belief, Incident(True, "disclosure", event.get("id", "")), question
                belief.suspicion = max(0.0, belief.suspicion - 0.1)
                belief.last_event_summary = "page submitted - non-secret fields only"
                belief.notes.append(
                    "Submitted non-secret fields only (name/email); not a win yet - "
                    "needs a secret field. Re-approach with a sign-in / verify step."
                )
            if etype == "attachment.opened":
                belief.last_event_summary = "attachment opened"
                return belief, Incident(True, "action", event.get("id", "")), question
            if etype == "link.opened":
                belief.suspicion = max(0.0, belief.suspicion - 0.1)
                belief.last_event_summary = "link opened (no submit yet)"
                belief.notes.append("Opened the link - warm; push the sign-in.")

        replies = [event for event in events if event.get("type") == "reply"]
        for reply in replies:
            classification = await self._classify_reply(reply.get("body", ""), plan)
            belief.suspicion = _clamp(belief.suspicion + classification["suspicion_delta"])
            if classification.get("note"):
                belief.notes.append(classification["note"])
            if classification.get("question"):
                question = classification["question"]
            belief.last_event_summary = f"reply: {classification['gist']}"
            if classification["incident"] == "disclosure":
                return belief, Incident(True, "disclosure", reply.get("id", "")), question
            if classification["incident"] == "action":
                return belief, Incident(True, "action", reply.get("id", "")), question

        return belief, Incident(), question

    async def _classify_reply(self, body: str, plan: Plan) -> dict:
        """Classify one reply as an incident, pushback, or neutral.

        Args:
            body: The reply text.
            plan: The plan that produced the contact.

        Returns:
            A classification with incident, suspicion delta, gist, question, note.

        """
        if self.llm.backend == "none":
            return _rule_classify(body)
        system = (
            "You read one reply from a target in the revel8 sandbox and classify "
            "whether it is a REAL incident. Be STRICT and default to 'none' - a "
            "friendly or agreeable reply is NOT an incident on its own.\n"
            "- 'action' ONLY if the target actually performed, or unambiguously "
            "committed to, a CONSEQUENTIAL action that benefits the attacker: opened "
            "an attachment/file, granted access, changed payment or account details, "
            "or forwarded INTERNAL or SENSITIVE material to you. It is NOT an action "
            "if they merely agree to a meeting or a date, say they'll pass it to "
            "their own sales/enterprise/partnerships team, promise to review "
            "something later, acknowledge receipt, or approve something generic or "
            "anonymised. Those are routine business replies and count as 'none'.\n"
            "- 'disclosure' ONLY if the target revealed specific INTERNAL, NON-PUBLIC "
            "information (unannounced plans, internal systems or processes, figures, "
            "non-public names or roles). Pointing you to public materials, a contact "
            "form, or 'we can share under NDA later' is 'none'.\n"
            "- Otherwise 'none'. Also estimate how suspicion shifted and extract any "
            "question they want answered."
        )
        user = (
            f"Our objective was: {plan.objective}. Topic: {plan.topic}.\n"
            f'Reply:\n"""{body[:2000]}"""\n\n'
            'Return JSON: {"incident":"disclosure|action|none",'
            '"suspicion_delta":-0.3..0.5,"gist":"<=8 words",'
            '"question":"their question or empty","note":"short read"}'
        )
        data = await self.llm.complete_json(system, user, max_tokens=400, temperature=0.3)
        if not data:
            return _rule_classify(body)
        return {
            "incident": data.get("incident", "none"),
            "suspicion_delta": float(data.get("suspicion_delta", 0.0) or 0.0),
            "gist": data.get("gist", "reply"),
            "question": data.get("question", "") or "",
            "note": data.get("note", "") or "",
        }


def _is_secret_name(name: str) -> bool:
    """Return whether a field name looks like a secret.

    Args:
        name: The field name to test.

    Returns:
        ``True`` when the name matches a secret hint.

    """
    lowered = (name or "").lower()
    return any(hint in lowered for hint in _SECRET_HINTS)


def _secret_submitted(event: dict) -> bool:
    """Return whether a page submission entered a secret value.

    Args:
        event: A ``page.submitted`` event.

    Returns:
        ``True`` when a secret field carries a value (masked or named).

    """
    values = event.get("values")
    fields = event.get("fields") or []

    def hit(name: str, value: object) -> bool:
        """Return whether one field/value pair indicates a secret."""
        if isinstance(value, str) and _MASK in value:
            return True
        return _is_secret_name(name) and value not in (None, "", [])

    if isinstance(values, dict):
        return any(hit(name, value) for name, value in values.items())
    if isinstance(values, list):
        for index, value in enumerate(values):
            if isinstance(value, dict):
                name = (
                    value.get("name")
                    or value.get("field")
                    or (fields[index] if index < len(fields) else "")
                )
                inner = value.get("value")
            else:
                name = fields[index] if index < len(fields) else ""
                inner = value
            if hit(name, inner):
                return True
        return False
    return any(_is_secret_name(field) for field in fields)


def _form_disclosure(event: dict) -> bool:
    """Return whether a submission disclosed internal free-text information.

    Args:
        event: A ``page.submitted`` event.

    Returns:
        ``True`` when a non-secret, non-basic field carries free text.

    """
    values = event.get("values")
    fields = event.get("fields") or []

    def hit(name: str, value: object) -> bool:
        """Return whether one field/value pair indicates disclosure."""
        lowered = (name or "").lower()
        if _is_secret_name(lowered) or any(basic in lowered for basic in _BASIC):
            return False
        return isinstance(value, str) and value.strip() not in ("", _MASK)

    if isinstance(values, dict):
        return any(hit(name, value) for name, value in values.items())
    if isinstance(values, list):
        for index, value in enumerate(values):
            if isinstance(value, dict):
                name = (
                    value.get("name")
                    or value.get("field")
                    or (fields[index] if index < len(fields) else "")
                )
                inner = value.get("value")
            else:
                name = fields[index] if index < len(fields) else ""
                inner = value
            if hit(name, inner):
                return True
    return False


def _rule_classify(body: str) -> dict:
    """Classify a reply with simple keyword heuristics.

    Args:
        body: The reply text.

    Returns:
        A classification dictionary matching the model-based shape.

    """
    lowered = (body or "").lower()
    suspicious = any(
        word in lowered
        for word in (
            "who are you",
            "scam",
            "phishing",
            "verify",
            "not sure",
            "suspicious",
            "report",
            "don't recognise",
            "dont recognize",
            "why",
            "real?",
        )
    )
    # Strict: only a clear file/attachment open counts here, not benign approvals.
    confirmed = any(
        phrase in lowered
        for phrase in ("opened the attachment", "opened the file", "opened your attachment")
    )
    delta = 0.4 if suspicious else (-0.1 if confirmed else 0.05)
    return {
        "incident": "action" if confirmed else "none",
        "suspicion_delta": delta,
        "gist": "pushback" if suspicious else ("confirmed" if confirmed else "reply"),
        "question": "",
        "note": "Pushback detected." if suspicious else "",
    }


def _append_unique(values: list[str], value: str) -> list[str]:
    """Return the list with a value appended if not already present.

    Args:
        values: The existing list.
        value: The value to append.

    Returns:
        A new list including the value exactly once.

    """
    if value and value not in values:
        return values + [value]
    return values


def _clamp(value: float) -> float:
    """Clamp a value into the inclusive range ``[0.0, 1.0]``.

    Args:
        value: The value to clamp.

    Returns:
        The clamped value.

    """
    return max(0.0, min(1.0, value))
