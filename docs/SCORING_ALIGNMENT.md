# Evidence-based scoring alignment

Source: revel8 **Agentic Social Engineer - Scoring Rubric**, 2 pages, and **Challenge**, 3 pages (Road to START Hack 2026).

| Criterion | Maximum | What the document requires | What is actually validated today |
|---|---:|---|---|
| Results | 25 | Incidents in three scored runs and speed to first incident | **Not established**. One neutral practice message was accepted; no reaction events. |
| Targeting | 10 | Topic matches, own angle, factual accuracy | **Not established**. No targeting results; do not invent susceptible topics. |
| Craft | 10 | Rendered mails and landing pages during scoring | **Not established**. No rated scoring artifact. |
| Architecture & persistence | 40 | Architecture page + replayed scoring turns | **Evidence available**: 157 tests, replay, deduplication, LLM cache, SQLite persistence, leases, recovery diagnostics. Final score depends on jury. |
| Pitch & demo | 15 | Five-minute explanation + one real run thread | **Presentation prepared**, but real scoring-run thread not yet available. |

## Competition safety and validity constraints

- Everything must stay inside the simulation; no real recipients or real communications channels.
- No real malware; attachments are only names.
- No attempts to modify a target's AI instructions or address it as an AI in scored contacts.
- No sender or landing page on a real organization's own domain.
- During scoring, human operators must not write, edit or approve individual messages.
- Three scoring runs are recorded by the competition API; their times are announced at the event.

## Claims to avoid

Do not claim any incident, target reply, validated targeting angle, full autonomous persuasion, automatic crash recovery, or rated craft output unless independently verified.

## Recommended jury evidence

1. One-page system diagram showing API -> metadata recording -> SQLite -> orchestrator -> cache/LLM -> cycle journal.
2. `python -m scripts.demo_replay` showing three *synthetic* events, replay and idempotency.
3. `python -m scripts.audit_readiness` showing SQLite integrity, completed cycles, and no leftover leases.
4. `python -m scripts.final_preflight` showing lint/test status.
5. One **genuine** scoring-run thread exported through the organizer's permitted review process; clearly label what is real vs simulated.
