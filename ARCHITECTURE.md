# CaspianX — System Architecture

## Overview

CaspianX is a Python-based autonomous conversation and observation
system for the authorized revel8 simulation.

## Architecture

1. Scenario Discovery
   - Retrieves available scenarios and target identifiers.
   - Validates session status and contact budgets.

2. Public Fact Registry
   - Stores sourced public facts.
   - Tracks evidence provenance and uncertainty.

3. Conversation Agent
   - Generates bounded, neutral dialogue responses.
   - Processes persona replies and determines when to stop.

4. Target API Integration
   - Handles session and conversation lifecycle operations.
   - Applies idempotency keys and request limits.

5. Persistence
   - Stores conversation identifiers, turns and observed events.
   - Uses SQLite for recovery and event deduplication.

6. Observation and Evaluation
   - Classifies observable API events.
   - Separates confirmed outcomes from unverified assumptions.

7. Recovery and Replay
   - Inspects incomplete operations.
   - Reconstructs recorded interactions without resending contacts.

## Data Flow

Scenario Discovery
    -> Conversation Agent
    -> Target API
    -> Response Processing
    -> SQLite Persistence
    -> Evaluation and Replay

## Reliability

- Idempotent API operations.
- Persistent conversation history.
- Session budget enforcement.
- Recovery diagnostics.
- Read-only evidence extraction.
- Automated regression and offline acceptance tests.

## Competition Constraints

- All interactions remain inside the authorized simulation.
- No real-world communications.
- No malware.
- No attempts to override simulator instructions.
- No claims of verified incidents without supporting evidence.
