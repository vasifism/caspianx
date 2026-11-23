# CaspianX — Conversation Engine: Installation and Runbook

This package **adds** new modules. It does not overwrite `core/engine.py`, `integrations/target_api.py`, or existing local SQLite databases.

## Install

From the CaspianX root, extract the bundle, then run:

```bash
python -m ruff check . --fix
python -m ruff format .
python -m ruff check .
python -m pytest -q
python -m scripts.practice_autonomous_conversation --session offline_new_001 --db build/offline_conversations.sqlite3
```

This offline command has no network or model calls.

## Live practice-only connectivity run

Only run after checking the active practice session and budget. It spends one practice touch.

```bash
python -m scripts.practice_autonomous_conversation --live --session YOUR_EXISTING_PRACTICE_SESSION_ID --target julius --db data/conversation_practice.sqlite3
```

For neutral OpenAI-generated line instead of deterministic greeting, add `--use-openai`. This is not an exploit-oriented agent. Set `CASPIANX_DRY_RUN=false` and supply the normal team credentials via `.env`.

Do **not** run the same live command again automatically after a timeout. Check:

```bash
python -m scripts.inspect_conversation_ledger --session YOUR_EXISTING_PRACTICE_SESSION_ID --db data/conversation_practice.sqlite3
```

A pending ledger entry indicates an ambiguous request. Reconcile using the session and conversations returned by the official API; never manually delete a pending operation without knowing what happened.

## What it proves

- Live session gate checks scenario, status and budget.
- Uses documented `POST /sessions/{sid}/conversations`, `POST /conversations/{cid}/turns`, and `POST /conversations/{cid}/end`.
- Persists idempotency keys **before** each outbound request.
- Persists conversation IDs and each agent/persona transcript line.
- Honors a ten-turn maximum, default two, and stops when the persona ends the conversation.
- No automatic retry after timeout, no real contact channels, and no credential/exfiltration prompt generation.

## Known limitations

- Session-level lease is not shared with the existing `SessionLeaseRepository`; never launch this live CLI concurrently with another process operating on the same session.
- Failed or interrupted operation may remain pending and must be reconciled manually.
- Acknowledgement and conversation replies are not scored incidents.
- Transcript persistence is local; inspect outputs before sharing them publicly.
- A model response is bounded and guarded but this is not an exhaustive semantic security filter.
- Evaluation sessions are **not** eligible for live sends through this package. The existing read-only eval evidence tooling remains separate.
