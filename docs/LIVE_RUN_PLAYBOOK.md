# CaspianX — Live competition playbook

## What is verified

The project's latest *user-reported* validation was **244 tests passed** and **FINAL RELEASE: PASS**. The verified path includes read-only API retrieval, structured LLM analysis on metadata, SQLite persistence, replay, local anomaly checks, and demo packaging. It does **not** demonstrate an autonomous multi-contact run or a confirmed incident.

## Competition requirements from the attached revel8 documents

- Three scoring runs, with ten contacts available in each run; the actual scoring window is announced by the organizers.
- **Results (25):** incidents and speed. **Targeting (10):** target-relevant topics and accuracy. **Craft (10):** rendered messages/pages.
- **Architecture & persistence (40)** and **pitch (15)** are judged separately.
- Pitch is five minutes; the jury asks for one **real** recorded thread, start to finish. Never use synthetic events to imply a real run succeeded.
- All interactions remain within the official simulation. No real people, real channels, real malware, real organization domains, or instruction injection. The challenge states no human editing/approval of individual outgoing messages during scoring.

## Step A — Before the official scoring window

```bash
cd ~/Desktop/caspianx
source .venv/bin/activate
python -m scripts.final_release
python -m scripts.capture_live_evidence --list
```

Inspect the available scenario and official status. Never assume eval is open just because it appears in the listing.

## Step B — Read-only capture of an existing practice session

```bash
python -m scripts.capture_live_evidence --session s_678d0c7e74 --out build/evidence/practice_before.json
python -m scripts.print_live_evidence build/evidence/practice_before.json
```

No API messages are sent by this tool. It does not spend simulation contacts. The evidence is metadata-only. Its snapshot is immutable: choose a **new filename** on each new capture.

## Step C — Official scoring-run observation

Only after the organizer opens scoring, use the official session ID from the API. This package **does not create scoring sessions or send messages**.

```bash
python -m scripts.capture_live_evidence --list --include-eval
python -m scripts.capture_live_evidence --session OFFICIAL_SESSION_ID --include-eval --out build/evidence/scoring_run_01.json
python -m scripts.print_live_evidence build/evidence/scoring_run_01.json
```

Repeat with unique files for each authorized run and capture timestamp. Use only official API or organizer confirmation to claim an incident; event types alone do not prove it. The collector does not retrieve bodies or submitted form values for evidence exports.

## Step D — Jury demonstration

Run `python -m scripts.demo_replay` (clearly label **synthetic**). Show `ARCHITECTURE_ONE_PAGE.pdf` and the prepared deck. If an authentic thread exists, use the official simulation's own thread rendering; this metadata package does not reconstruct verbatim conversations.

## Step E — Safeguards

- Do not share `.env`, team keys, OpenAI keys, raw event bodies, form values, or SQLite databases.
- `build/evidence/` may contain session identifiers: share only with authorized judges if permitted.
- `build/CaspianX_Jury_Materials.zip` requires manual review of binary document contents and metadata.
- If API rejects access or no events appear, stop and report that accurately; do not manufacture outcomes.
- For API state-changing operations, use only pre-existing authorized contest mechanisms and the organizer's rules. This package is intentionally **read-only**.
