# CaspianX — five-minute jury narrative (English)

> Practice the timing; replace every bracketed segment only with verified facts. Do not claim incidents or a real thread if the API did not record one.

**0:00–0:40 | Challenge.** "Social engineering simulations are difficult to evaluate consistently, especially across multiple contacts. CaspianX is our event-driven observation and analysis platform for the authorized revel8 simulation."

**0:40–1:35 | Architecture.** "The system separates the simulation API client, a recording reader, SQLite persistence, an orchestrator, structured OpenAI analysis, and an analysis cache. Events are persisted before downstream analysis. Our display focuses on state transitions and evidence, not raw sensitive values."

**1:35–2:25 | Persistence.** "A session lease ensures a single cooperating worker owns a session at a time, even across processes. Observation cycles are recorded independently from the long-lived session status. The recovery inspector reports potentially abandoned work without silently replaying state-changing requests."

**2:25–3:10 | Validation.** "Our most recent verified local release completed [test count from current run] tests, an offline replay demonstration, failure injection, SQLite integrity checks, and a release gate. That supports our engineering claims, not a guaranteed contest outcome."

**3:10–4:15 | Actual run thread.** "Here is [OFFICIAL SESSION IDENTIFIER], shown using the official simulator's recorded thread." Walk through the timestamps and contacts **only if** a real, organizer-recorded thread is available. If no real thread exists: "We have not observed a real response thread yet; the following is a clearly labelled synthetic demo of persistence and replay, not a scored result." This may limit pitch points, but keeps claims accurate.

**4:15–5:00 | Takeaway.** "CaspianX focuses on operational reliability: durable state, reproducible observations, deduplicated events and auditable results. We can identify what the API actually reported, distinguish missing data from negative outcomes, and recover context after failures."

## Judge Q&A

**What did you prove?** Reliable local infrastructure and a limited live API connectivity test.

**Did the system autonomously achieve an incident?** No confirmed result has been supplied. Do not infer one.

**Does it recover after a crash?** It detects orphaned cycles and preserves leases; automatically taking over work still requires owner-liveness coordination.

**Do two completed cycles mean two sessions completed?** No. Session lifecycle and observation-cycle lifecycle are independent.

**Why is the cache safe?** It is keyed by session, model, instruction version and the selected event metadata; its version must change when analysis inputs or instructions change.
