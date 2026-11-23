# CaspianX phases 46–50: offline release and resilience

This is an **additive** bundle: no production modules are replaced, no simulated
contact is sent, and neither the Target API nor OpenAI is called by the new code.

## Contents

- `evaluation/release_validation.py`: conservative release decision based on
  *independent, sanitized* rehearsal and SQLite evidence.
- `evaluation/failure_matrix.py`: isolated SQLite fault injections (rollback,
  duplicate writes, competing ownership and a persisted running marker).
- `scripts/release_gate.py`: one-command release gate using existing
  `scripts.rehearse_demo` and `scripts.evidence_snapshot`.
- `scripts/failure_matrix.py`: fast, deterministic fault demonstration.
- `tests/test_release_validation.py`: 18 regression and negative tests.
- `tests/test_failure_matrix.py`: 4 fault-injection tests.

**New automated tests: 31.** Starting with 172 passing tests, the expected
full count is **203**, provided the current project has not changed.

## Install from the project root

```bash
unzip ~/Downloads/CaspianX_Phases_46_50_Bundle.zip -d .
python -m ruff check . --fix
python -m ruff format .
python -m pytest -q
python -m scripts.failure_matrix
python -m scripts.release_gate --db data/caspianx.sqlite3 --out build/release_decision.json
```

The release gate reruns existing preflight, SQLite audit, lease diagnostics and
Replay; it will take longer than a single pytest invocation.

## Scope of verification

PASS establishes that **local engineering evidence** is internally consistent.
It does **not** establish a live successful social-engineering incident,
a real positive response from an AI twin, availability of external APIs during
scoring or an autonomous persuasion strategy. Those are explicitly listed as
unverified in the JSON decision.

An isolated fault matrix tests SQLite principles using a miniature schema and
must not be mistaken for proof of distributed transactions or process-liveness
recovery in the production Orchestrator.

## Expected outputs

```text
203 passed
FAILURE MATRIX: PASS
RELEASE GATE: PASS
```

No new contact is sent and the practice budget is unchanged.

## Practical demo sequence

1. `python -m scripts.final_preflight`
2. `python -m scripts.failure_matrix`
3. `python -m scripts.demo_replay`
4. `python -m scripts.release_gate`
5. Open `build/release_decision.json` to show verified and unverified claims.

Do not include local `.env`, SQLite database, logs, or person-level event data in
jury archives. Re-review included documents for hidden credentials.

## Additional package inspection

```bash
python -m scripts.inspect_jury_package --zip build/CaspianX_Jury_Materials.zip
```

This detects suspicious paths and common plaintext secret assignments in
small UTF-8 files, but **cannot** prove a PDF or PPTX contains no secret.
Review document contents and metadata manually before submission.

The additive bundle also includes **9 ZIP inspection tests**, for **31 new tests**
and an expected project total of **203 passed** (172 + 31).
