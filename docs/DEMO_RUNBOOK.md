# CaspianX - Five-minute demo runbook

## Pre-demo (offline; no target contacts)

1. `source .venv/bin/activate`
2. `python -m scripts.final_preflight` - lint, formatting, pytest, synthetic replay.
3. `python -m scripts.audit_readiness` - local SQLite health.
4. `python -m scripts.inspect_recovery` - current lease and potentially stale cycles.
5. `python -m scripts.evidence_snapshot --db data/caspianx.sqlite3 --out demo_evidence.json` - share aggregate counts only.

All commands above are local/offline if the project's existing audit/demo scripts remain as described. Inspect every command before running in an unfamiliar environment.

## On stage

**0:00-0:45**: Show the problem and explain the authorized simulation, not actual people.

**0:45-1:40**: Show the architecture slide. Explain explicit boundaries: Target API, durable event recorder, SQLite, cache, analyzer, cycle journal, session lease.

**1:40-2:30**: Run `python -m scripts.demo_replay`: three synthetic events recorded; second write inserts zero; SQLite reopened and replayed.

**2:30-3:15**: Show local `python -m scripts.audit_readiness`: no active session leases, clean integrity, completed cycles. Give the *current* numbers, not a prerecorded claim.

**3:15-4:15**: Show a genuine approved scoring-run thread **if available**. If not, state plainly that live response behavior was not demonstrated and use a synthetic replay as architecture evidence, not as a replacement for the real-thread criterion.

**4:15-5:00**: Explain architecture tradeoffs and future improvements. Focus on idempotency, crash recovery limits, and exact operational boundaries.

## For genuine scored-run evidence

- Do not fabricate a target response or incident.
- Do not capture credentials, private disclosures, hidden evaluation notes, or secret fields in materials shared outside the team.
- Use the organizer's sanctioned transcript/replay facilities and strip sensitive content.
- Never show API keys or `.env` in the terminal or presentation.
- Do not attempt extra live contacts just to improve a demo unless explicitly permitted and planned within competition rules.

## Last-minute failure handling

If the live API is unavailable, demo only the proven offline replay and audit. If tests fail, do not claim a passing release. If a session lease remains, investigate it; never delete it automatically. If the real scoring run has no response, describe that outcome without reframing a synthetic event as real.
