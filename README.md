# CaspianX

**Agent infrastructure and evaluation toolkit for the authorized START Hack 2026 / revel8 simulation.**

CaspianX is a Python project for scenario discovery, agent orchestration, target-API integration, event observation, evidence processing, reproducible offline testing, and session recovery. The repository contains a conversation engine and an experimental `offense/` overlay for use **only within the authorized simulator**.

> **Scope:** This repository is provided for simulation and research. A successful local test is not evidence of a scored challenge incident. Do not contact real individuals or transmit credentials.

## Features

- **Scenario and session management:** scenario discovery, session lifecycle, contact-budget awareness and story-clock tracking.
- **Agent and conversation components:** dialogue orchestration, response processing, bounded conversations and state transitions.
- **Simulation API integration:** typed clients, observations, event handling, retries and recovery utilities.
- **Research and memory:** sourced public facts, evidence provenance, context and summarization components.
- **Evaluation:** event classification, offline replay, incident-evidence review, acceptance and release checks.
- **Persistence:** Peewee/SQLite-backed session data, deduplication and conversation records.
- **Safety:** dry-run defaults and separate configuration for local vs. live-simulator interactions.
- **Experimental overlay:** `offense/` modules and `scripts/run_attack.py` for authorized simulation workflows (not validated as a scored result).

## Requirements

- Python **3.12+**
- `pip` and a virtual environment
- Credentials for relevant providers **only if** using their API-backed features

## Quick start

```bash
# From the repository root
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
python main.py --check-config
python -m pytest -q
python -m ruff check .
```

The `.env.example` file is a template. Add your own credentials **locally** in `.env`. Keep `CASPIANX_DRY_RUN=true` when developing or testing offline.

To install the optional UI dependencies:

```bash
python -m pip install -e '.[ui]'
```

## Configuration

Configuration is loaded via `config/settings.py` and environment variables. Relevant keys in `.env.example` include:

| Variable | Description |
| --- | --- |
| `CASPIANX_DRY_RUN` | Prevent live operations when set to `true` |
| `CASPIANX_SCENARIO` | Scenario selection |
| `CASPIANX_TARGET_API_BASE_URL` | Authorized simulation API URL |
| `CASPIANX_TEAM_KEY` | Team authentication token (secret) |
| `CASPIANX_OPENAI_API_KEY` | Optional model API key (secret) |
| `CASPIANX_OPENAI_MODEL` | Configured model name |
| `CASPIANX_SQLITE_PATH` | Local SQLite storage location |
| `CASPIANX_HTTP_TIMEOUT_SECONDS` | Client timeout |

Other backend-specific settings may be required by certain scripts. Never commit any `.env` or actual credential values.

## Repository layout

```text
agents/          Agent behavior and conversation orchestration
config/          Environment settings and constants
core/            Runtime engine, session and recovery logic
dashboard/       UI components
data/            Local data (ignored by Git)
docs/            Runbooks, usage and architecture documentation
evaluation/      Evidence and offline evaluation
integrations/    External/simulator API clients
llm/             Model interface, schemas and prompts
memory/          Conversation context and memory
 offense/        Experimental simulation-specific overlay
research/        Public-source facts and evidence
safety/          Safety checks and secret handling
scripts/         Diagnostics, replay, tests and simulation entry points
storage/         SQLite persistence and repositories
tests/           Automated tests
main.py          Configuration diagnostics
pyproject.toml   Build metadata and dependencies
ARCHITECTURE.md  Architecture overview
```

## Common commands

```bash
# Validate local configuration (no network calls)
python main.py --check-config

# Run tests and code quality checks
python -m pytest -q
python -m ruff check .
python -m ruff format --check .

# Offline adaptive conversation exercise
python -m scripts.practice_adaptive_conversation \
  --session offline_demo_01 \
  --db build/adaptive_demo.sqlite3

# Run all configured offline release checks
python -m scripts.final_release

# Inspect the current eval scenario using saved API JSON (read-only/offline)
python -m scripts.inspect_eval_readiness \
  --scenarios build/scenarios.json \
  --sessions build/sessions.json
```

Some scripts need additional arguments, credentials, prior state or explicit live-usage confirmation. Check `python -m scripts.<module> --help` and the relevant `docs/` runbook before running them.

## Architecture

```text
Scenario discovery -> Session management -> Agent/Conversation engine
                                              |
                                              v
                                     Authorized simulation API
                                              |
                                              v
                                 Events -> SQLite -> Evaluation
                                              |
                                              v
                                     Recovery / Replay / Reports
```

Read [ARCHITECTURE.md](ARCHITECTURE.md) for component responsibilities and [docs/EVAL_COMPLETION_RUNBOOK.md](docs/EVAL_COMPLETION_RUNBOOK.md) for the evaluation runbook.

## Security and publication hygiene

- `.env`, tokens, private keys and provider credentials are excluded from version control.
- `data/`, `build/`, `recordings/`, `runs/` and `state/` contain local artifacts and are ignored.
- Avoid publishing captured conversations, personal data or simulator evidence without explicit permission.
- Keep evaluation claims tied to actual observed events; opening a link is not equivalent to completing an objective.
- This project must not be used for real-world social engineering, phishing or malware delivery.

## Status

The archive includes both a local engineering baseline and later experimental modules. API-backed execution, score attainment, and end-to-end release readiness are **not independently verified** by this README. Run the tests before publishing and validate any live integration only within the event's authorized boundaries.

## License

No license is included. All rights reserved unless a license is added by the repository owner.
