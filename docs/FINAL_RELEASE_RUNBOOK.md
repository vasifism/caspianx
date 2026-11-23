# CaspianX — final release and evidence runbook

## Scope

This additive bundle provides **offline-only acceptance evidence**. It does not send simulated contacts, generate persuasive social-engineering content, scrape real people, or claim a scored incident. It does not change an existing orchestrator, database schema, API client, or model integration.

## Install

1. Commit a known-good version of CaspianX first.
2. Extract the ZIP **into the CaspianX project root**. Six project files are added, plus INSTALL_FIRST.txt.
3. Run these commands (the block contains no shell comments):

```bash
python -m ruff check . --fix
python -m ruff format .
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m scripts.final_acceptance --out build/final_acceptance.json
python -m scripts.final_preflight
python -m scripts.failure_matrix
python -m scripts.audit_readiness
python -m scripts.inspect_recovery
python -m scripts.release_gate --db data/caspianx.sqlite3 --out build/release_decision.json
python -m scripts.rehearse_demo --out build/rehearsal_report.json
python -m scripts.build_jury_package --out build/CaspianX_Jury_Materials.zip
python -m scripts.inspect_jury_package --zip build/CaspianX_Jury_Materials.zip
```

## Expected checks

- All existing tests remain green; the new files add 16 tests (baseline reported: 228, target: **244**).
- `FINAL ACCEPTANCE: PASS` (synthetic event sequence, no API calls).
- `FINAL PREFLIGHT: PASS`, `FAILURE MATRIX: PASS`, `Audit: PASS`, `Recovery inspection: OK`, `RELEASE GATE: PASS`.
- The jury package inspection should report `PASS`; inspect documents manually for secrets or private material.

## Offline input format

To check your own **sanitized** cumulative metadata snapshots:

```json
{"snapshots": [[{"id": "evt_1", "type": "message.sent"}], [{"id": "evt_1", "type": "message.sent"}, {"id": "evt_2", "type": "message.opened"}]]}
```

Run: `python -m scripts.final_acceptance --input path/to/safe_snapshots.json --out build/final_acceptance.json`.

Never include message bodies, link destinations, form values, secret tokens, or personal details. The tool ignores additional fields but you should avoid putting them in the input to begin with.

## Required final human checks

1. Git: verify `.env`, keys, local SQLite, and confidential content are not tracked or packaged.
2. Run from a clean checkout using a properly configured environment; ensure tests do not rely on an existing local DB.
3. Compare `ARCHITECTURE.md` and pitch materials with the actual code, without claiming unimplemented autonomy.
4. Record a genuine simulator thread only if one exists; do not present synthetic tests as scored evidence.
5. Respect simulator-only boundaries: no real-world impersonation, credential capture, confidential-data extraction, or attempts to alter AI twin instructions.

## Release truthfulness

**Infrastructure acceptance is not scoring success.** A passing report certifies metadata checks only. Anomaly candidates are not incidents. Scoring-run performance remains unknown until the competition API and judges confirm it.

## One-command final gate

After installation, run `python -m scripts.final_release`. This executes Ruff, the full test suite, offline acceptance, preflight, failure matrix, SQLite audit, recovery diagnostics, release gate, rehearsal, jury archive build, and archive inspection in order. The manifest is written to `build/final_release.json`. It stops on the first error and does not call the live contact API or OpenAI.
