# CaspianX — Fast Finalization, Phases 41–45

## Purpose

Deliver a single offline command for demo rehearsal and a shareable jury-materials ZIP. The scripts do **not** send simulation contacts, call OpenAI, alter SQLite state, or attempt to generate persuasive social-engineering messages.

### Phase 41 — consolidated rehearsal

```bash
python -m scripts.rehearse_demo --out build/rehearsal_report.json
```

This launches existing `scripts.final_preflight`, `scripts.audit_readiness`, `scripts.inspect_recovery`, and `scripts.demo_replay`. Only fixed status lines are copied into the JSON summary; raw logs are not exported. The audit scripts might still create their own local tables if their existing implementations do so; this new wrapper does not add writes.

### Phase 42 — safe presentation package

```bash
python -m scripts.build_jury_package --out build/CaspianX_Jury_Materials.zip
```

Only eight predefined architecture and presentation files are included. Source credentials, local database, `.env`, and event payloads are **excluded by design**. The package is deterministic and self-checks SHA-256 hashes for each member.

### Phase 43 — quality gates

```bash
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

Eleven new offline tests have been provided. A previous local result of 161 tests implies a *target* of 172 tests after adding them; that count has not been verified in your exact working tree.

### Phase 44 — stage rehearsal (five minutes)

- 0:00–0:35 — problem, simulation boundary, goal
- 0:35–1:25 — architecture and durable event recording
- 1:25–2:15 — deduplication, LLM cache, session lease, crash recovery
- 2:15–3:05 — run `python -m scripts.demo_replay` live
- 3:05–3:40 — show `FINAL PREFLIGHT: PASS` and SQLite audit result
- 3:40–4:35 — show **a real scoring thread**, only if one is actually available; otherwise state that the current demonstration uses synthetic events
- 4:35–5:00 — limitations and future work

The event organizer's rubric explicitly expects one real thread; synthetic replay should never be presented as one. Claims of success/incident must be backed by API results.

### Phase 45 — release freeze

1. Commit tested source code, excluding `.env`, SQLite data, API keys, and generated reports.
2. Archive the build's verified document ZIP outside the repository if needed.
3. Preserve the command output from the rehearsal as evidence, but do not publish personal or sensitive logs.
4. Do not modify working infrastructure immediately before judging without rerunning the full preflight.

## What is not claimed

This package does not implement an autonomous exploitation agent, create credential-collection workflows, or claim success in contest scoring. It adds operational verification and presentation readiness only.
