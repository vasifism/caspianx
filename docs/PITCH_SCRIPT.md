# CaspianX - Five-minute pitch (English)

**Slide 1 - 0:00-0:40: Why CaspianX?**

"Social-engineering simulations are difficult to evaluate because every interaction happens over time and failures are often silent. We built CaspianX as an auditable Python observation and orchestration foundation for revel8's authorized AI-twin simulation. Our focus is not just producing an output, but making every observed step reproducible and defensible."

**Slide 2 - 0:40-1:45: Architecture**

"The simulation API is the single boundary for all target interaction. An API reader retrieves session metadata and event records. Before analysis begins, a recording adapter validates and stores only event identifiers and event types in SQLite. The orchestrator then checks a deterministic model-and-history fingerprint, reuses an analysis when the input is unchanged, or requests a structured result from our OpenAI adapter. Every observation has an independent cycle record. A SQLite lease prevents two instrumented runners from observing the same session concurrently."

**Slide 3 - 1:45-2:45: Proof and replay**

"This is our offline replay demonstration. Three synthetic events are inserted. Submitting them again creates zero duplicates. We reopen the database and reconstruct the same ordered event history. This is intentionally labeled as synthetic. In our verified practice session, the API accepted one neutral test contact, but the event endpoint returned no reaction events. We do not treat silence as evidence of a successful incident."

**Slide 4 - 2:45-3:40: Reliability**

"Our last confirmed full test run passed 157 tests. We additionally verified SQLite integrity, six completed observation cycles, one reusable analysis cache entry, and no active execution leases. We simulated analysis errors and process termination. The system preserves already-recorded events even when later analysis fails. A killed process intentionally leaves its lease behind, requiring explicit inspection before recovery."

**Slide 5 - 3:40-4:35: Real thread**

"[INSERT A REAL SCORING-RUN THREAD HERE AFTER IT EXISTS. Describe the initial permitted contact, the actual recorded reaction, the system's documented decision, and the recorded outcome. If no genuine thread exists, say: 'We do not yet have a real multi-turn scoring thread to show. This is our verified practice contact record and our separate synthetic replay.']"

**Slide 6 - 4:35-5:00: Close**

"Our main result is an independently testable architecture for durable observation, safe event minimization, idempotent replay, and clear failure reporting. We can demonstrate exactly what is proven and what still needs live validation. Thank you."

## Presenter rules

- Rehearse for five minutes; timings are guidance, not guaranteed.
- Never claim that a synthetic thread was a real target reaction.
- Replace '157' with the verified local test count after installing the new additive pack.
- Distinguish scores assigned by the jury from engineering evidence.
- Never expose keys, form values, internal information, or confidential target content.
