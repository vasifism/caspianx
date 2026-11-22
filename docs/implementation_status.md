# Implementation status and test boundary

## Grounding

- Challenge PDF: research, simulated contacts, reaction handling, three scored runs,
  disqualification conditions, architecture page and five-minute pitch.
- Rubric PDF: Results 25, Targeting 10, Craft 10, Architecture 40, Pitch 15.
- `docs.md`: read-only routes, `story_time`/`sent_at`, form event metadata, limits,
  idempotency requirements, and API response examples.

## Implemented

- Local typed settings and virtual time validation.
- API response schemas and a read-only dry-run-controlled client.
- Peewee-backed SQLite event, session, and state snapshot storage.
- Redaction of submitted form values and known credential-key fields.
- Offline pytest suite and non-secret config diagnostics.

## Not yet implemented or validated

- No actual Target API call or OpenAI call has been made.
- Full autonomous agent runtime, message sending, conversation turns, page registration,
  exploitation strategies, and scoring outcomes are not in this build.
- Storage redaction is not a semantic secret detector for arbitrary prose.
- Rate limiting, HTTP retries, coverage thresholds and rendered UI are pending.
- Actual jury scoring and contest results cannot be predicted.
