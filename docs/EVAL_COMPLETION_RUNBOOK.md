# CaspianX — Eval Completion Add-on

This update adds four bounded capabilities. It does not change the proven production
contact pipeline and does not make phishing, impersonation, credential harvesting,
confidential disclosure, or unauthorized-action requests.

## Components

- `research/public_fact_registry.py`: source-attributed *public professional* facts;
  imports operator-supplied JSON, does not crawl or assume unreleased eval identities.
- `core/scoring_window_readiness.py`: validates observed scenario/session metadata,
  target ID discovery, and remaining contact budgets without making requests.
- `agents/adaptive_dialogue_agent.py`: deterministic adaptive transparent
  conversation policy with a hard turn limit.
- `evaluation/conversation_thread_export.py`: readable replay from the existing
  durable conversation ledger, expressly marked as local/non-scored evidence.

## Install and run

From the CaspianX project root, unzip the add-on *after* installing the prior
Autonomous Conversation Engine. The modules in this package do not overwrite
production integrations.

```sh
unzip ~/Downloads/CaspianX_Eval_Completion_Addon.zip -d .
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m scripts.final_release
```

Offline scenario inspection (provide a saved JSON array from the official API):

```sh
python -m scripts.inspect_eval_readiness --scenarios build/scenarios.json --sessions build/sessions.json
```

Review a local transcript from the Conversation Engine:

```sh
python -m scripts.export_conversation_thread \
  --db data/conversation_practice.sqlite3 \
  --conversation YOUR_CONVERSATION_ID \
  --out build/evidence/practice_thread.md
```

A source-backed fact registry is a JSON array such as:

```json
[
  {
    "subject_id": "public_professional_01",
    "statement": "Speaker at a publicly announced conference",
    "source_url": "https://example.org/events/speaker",
    "observed_at": "2026-11-21T13:00:00+00:00",
    "category": "event"
  }
]
```

```sh
python -m scripts.inspect_public_facts --registry build/public_facts.json \
  --subject public_professional_01
```

The example is a **fictional placeholder**, not a verified claim about anyone.

## Integration boundary

The adaptive policy implements the same `next_line(history)` protocol as
`ConversationManager`'s existing agent. It can be swapped into **offline**
conversation tests by constructing `AdaptiveDialogueAgent(max_agent_lines=3)`;
no extra live contacts are required for this verification.

Existing `scripts.capture_live_evidence --list --include-eval` provides read-only
session discovery. **Do not assume the three practice personas will be used in eval.**
Eval identities are announced when the scoring window opens.

The official simulator allows up to three eval runs, with ten contacts per run.
Do not count an acknowledged API request, `persona_says`, or an opened link as a
verified incident. The official event record and jury determine outcomes.

This add-on requires the previous Conversation Engine's
`storage/conversation_repository.py` for transcript export. Do not store real
secrets or raw credential form submissions in the ledger.

## Three-turn adaptive end-to-end test

The offline test uses the actual durable ConversationManager and SQLite ledger,
with a deterministic simulated persona. It spends **zero** contacts.

```sh
python -m scripts.practice_adaptive_conversation \
  --session offline_adaptive_demo_01 \
  --db build/adaptive_demo.sqlite3
```

For an additional **transparent** live practice test, only after the offline
simulation passes, use `--live --confirm-practice-contact` with an existing
active practice session ID. This costs one contact and **does not** target eval.
The conversation engine's pending-operation checks prohibit blind recovery.

```sh
python -m scripts.practice_adaptive_conversation \
  --live --confirm-practice-contact \
  --session YOUR_EXISTING_PRACTICE_SESSION_ID \
  --db data/adaptive_practice.sqlite3
```
