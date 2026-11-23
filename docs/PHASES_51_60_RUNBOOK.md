# CaspianX — Phases 51–60: Offline Run Validation & Anomaly Detection

This is an **additive package**. It does not modify the existing Orchestrator,
Target API, OpenAI client, database schema, or outbound message code.

## Contents

- `evaluation/anomaly_detector.py` — conservative event-metadata anomaly detection.
- `evaluation/offline_run_validation.py` — replay multiple cumulative snapshots,
  count unique and reused events, flag conflicting identifiers.
- `scripts/offline_full_run.py` — produce deterministic, offline run evidence.
- `scripts/inspect_event_anomalies.py` — inspect a local JSON event array.
- `tests/test_anomaly_detector.py` — regression tests.
- `tests/test_offline_run_validation.py` — offline replay validation tests.

## Run

From the project root with the virtual environment enabled:

```bash
python -m ruff check . --fix
python -m ruff format .
python -m ruff check .
python -m pytest -q
python -m scripts.offline_full_run --out build/offline_full_run.json
python -m scripts.final_preflight
python -m scripts.failure_matrix
python -m scripts.release_gate --db data/caspianx.sqlite3 --out build/release_decision.json
```

Do not paste lines beginning with `#` into interactive zsh if interactive
comments are disabled. The above command block contains no shell comments.

You can inspect local event metadata stored as a JSON list:

```bash
python -m scripts.inspect_event_anomalies --input path/to/events.json --out build/anomalies.json
```

**Do not upload or share raw private conversation data.** The CLI reads local
JSON and writes diagnostics, but raw input remains on the local machine. Do not
run it on real private data without authorization.

## What is actually verified

- Event-ID and type validation.
- Duplicate and conflicting event identifiers.
- Unexpected event types and out-of-order ISO timestamps.
- Reported contact count versus contact budget.
- Deterministic offline snapshot fingerprints and event counters.
- Metadata-only reports without message bodies and form values.
- Reproducible offline CLI reports.

## What is NOT implemented by this package

- No model-driven selection of targets, persuasion strategies, or contact text.
- No automatic outbound messages.
- No change to the simulator's scoring system or its incident assessments.
- No inference of incidents from message content or unknown event types.
- No guarantee that the API's event schema uses these exact event names.
- No automatic reconciliation of killed-process SQLite leases.

### 'Something else' rule from the challenge PDF

The rules invite teams to submit an unlisted successful outcome for review.
Therefore the detector emits a **review candidate** for an unrecognized event
name. This is **not** proof of a scoring incident. Only the organizer's
confirmed evidence can establish such an outcome.

## Compatibility and installation

The bundle intentionally adds files only. If your current repository already
contains `evaluation/anomaly_detector.py`, back it up before unzipping, or
inspect the archive and compare the local version.

The new modules are self-contained and require Python 3.11+ and pytest for
tests. The existing project remains responsible for its full integration.

### Additional analysis modules

- `evaluation/event_classifier.py`: classify known event names without inspecting payloads.
- `evaluation/novel_outcomes.py`: aggregate unusual events as **unverified** candidates
  for organizer review (the “Something else” category).
