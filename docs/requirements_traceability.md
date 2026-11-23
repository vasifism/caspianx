# Revel8 challenge requirements and implementation traceability

Sources: **Agentic Social Engineer Challenge**, pages 1–3; **Scoring Rubric**, pages 1–2; updated `docs.md` included in the repository.

| Requirement | Points / constraint | Current status |
| --- | --- | --- |
| Research + contact + persistence | Challenge, p. 1 | Research/agent/contact components are placeholders; Peewee persistence implemented |
| Results | 25 points | Not implemented; only organizer scoring can confirm incidents |
| Targeting | 10 points, up to -5 for incorrect facts | Not implemented |
| Craft | 10 points | Not implemented |
| Architecture and persistence | 40 points | Configuration, event persistence, session-clock logic, read-only API integration partially implemented |
| Pitch and demo | 15 points, 5-minute pitch | Not implemented |
| Practice versus eval | 30 versus 10 contacts per session | Limits represented in configuration; outbound execution not implemented |
| Live conversation | 1 contact, up to 10 turns | Typed schema only; outbound execution not implemented |
| Story timestamps | Monotonic `sent_at`, session `story_time` | Story clock and request models present |
| Form submissions | May contain `values` | Sanitization and schema present; no real credentials stored |
| API resilience | 120-second timeout, idempotency, 60 req/min, 6 concurrent | Read-only HTTP client, concurrency bound; retry/rate limit not yet implemented |
| Fair play | Simulation-only, no real contact or malware | Dry-run by default, read-only client, strict API hostname |

This document is an engineering checklist, not proof of competition readiness.
