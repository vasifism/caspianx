# CaspianX — Eval Day Playbook

## What this package actually does

- Bounded **GET-only** event polling for an already known session, with immutable evidence snapshots.
- Difference reports for before/after captures, including contact deltas, new event metadata, and missing events.
- An evidence-only chronological brief for the jury. **It does not reconstruct the message bodies or official rendered thread.**
- Eleven local tests covering comparison, data minimization, and file immutability.

There are **no contact-sending endpoints** and no autonomous persuasion functionality in this package. This package cannot create an incident or guarantee that a twin responds. A session with 0 events remains a 0-event session.

## Tonight (practice session)

```bash
python -m ruff check . --fix
python -m ruff format .
python -m pytest -q
python -m scripts.final_release
python -m scripts.watch_live_events --session s_678d0c7e74 --checks 3 --interval 10 --out-dir build/evidence/practice_watch
```

If you have an existing baseline `build/evidence/practice_before.json`, compare it with the first new watch file using:

```bash
python -m scripts.compare_live_evidence build/evidence/practice_before.json PATH_TO_NEW_SNAPSHOT.json --out build/evidence/practice_diff.json
python -m scripts.build_thread_brief PATH_TO_NEW_SNAPSHOT.json --out build/evidence/practice_thread_brief.md
```

## Tomorrow (after official window opens)

1. Confirm the organizers have opened scoring. Do not assume `eval` is writable based only on the presence of a scenario listing.
2. Retrieve authorized sessions using:

```bash
python -m scripts.capture_live_evidence --list --include-eval
```

3. For an **actual official session ID** shown by the service, capture a baseline:

```bash
python -m scripts.capture_live_evidence --session OFFICIAL_SESSION_ID --include-eval --out build/evidence/eval_run_01_before.json
```

4. During/after the run, watch and save only actual API observations:

```bash
python -m scripts.watch_live_events --session OFFICIAL_SESSION_ID --include-eval --checks 6 --interval 10 --out-dir build/evidence/eval_watch_01
```

5. Compare before/after and create the metadata brief with the two scripts above. Use new paths each time: snapshots are immutable.
6. Use the organizer's **official turn-by-turn run renderer** for the jury's required real thread. Verify session ID, channel, actual content shown, and official incident determination; do not extrapolate from event type alone.
7. Retain contact budgets for any explicitly authorized interactions and do not use `eval` as an ad-hoc test environment.

## Scoring presentation checklist

- One architecture page (existing `docs/ARCHITECTURE_ONE_PAGE.pdf`).
- The five-minute pitch (existing presentation deck).
- One authentic scoring-run thread from the official renderer (required for the jury criterion).
- An accurate account of the run: number of contacts, observed types and timestamps if returned, and the official incident outcome (if any).
- An honest separation between synthetic replay, read-only event metadata, and the organizer's official incident assessment.

## What remains external to the software

- Official window activation, scoring sessions, real responses, and scoring verdicts are controlled by revel8.
- A read-only API capture cannot force the twin to react or confirm an incident.
- This package does not send contacts or implement a complete autonomous agent; do not claim otherwise in the pitch.
