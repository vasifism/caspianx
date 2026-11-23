# CaspianX - Final Handoff Pack

This package is **additive**. It does not replace existing CaspianX modules or touch the live simulation by itself.

## Includes

- `ARCHITECTURE_ONE_PAGE.pdf` - one-page jury architecture hand-in.
- `CaspianX_Pitch.pptx` - six-slide, editable five-minute presentation.
- `CaspianX_Pitch.pdf` - ready-to-display PDF version of the same deck.
- `PITCH_SCRIPT.md` - five-minute English speaking script (contains a clearly labeled real-thread placeholder).
- `DEMO_RUNBOOK.md` - safe operational commands and live evidence instructions.
- `SCORING_ALIGNMENT.md` - mapping from the revel8 rubric to proven capabilities and gaps.
- `scripts/final_preflight.py` - offline repository, test and lint quality gates.
- `scripts/evidence_snapshot.py` - read-only aggregate SQLite evidence exporter.
- `tests/test_final_handoff.py` - four new independent unit tests.

## Install

From the repository root, extract the ZIP preserving its directory structure, then:

```bash
python -m ruff check . --fix
python -m ruff format .
python -m pytest -q
python -m scripts.final_preflight
python -m scripts.evidence_snapshot --db data/caspianx.sqlite3 --out demo_evidence.json
```

Expected: previous 157 tests plus four new tests = **161**, assuming the local source layout is compatible.

**Before submitting**: verify that the one-page diagram matches the actual implementation; replace the real-thread placeholder with a genuine simulation transcript from your own scoring run, if and only if one exists. Never present synthetic events as a real target reaction. Do not submit private `.env`, API keys, raw conversations, credential values, or SQLite databases.

## Limits

The current verified history contains one neutral, accepted practice contact, but no response events; the deck does not claim a successful incident or an autonomous multi-contact strategy. Session leases protect the observation runner but do not automatically recover stale ownership. The scripts in this package never make network requests or send contacts.
