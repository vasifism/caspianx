revel8 · Agentic Social Engineer

# CaspianX — an autonomous red-team agent

A target-agnostic agent that researches an unknown person, opens contact through the revel8 sandbox, and drives the conversation toward a single confirmed incident — adapting its strategy, channel and pretext from what each reply tells it, with no human in the loop.

Team **CaspianX** Model **gpt-6.1-terra** Async Python · **httpx** / asyncio Pluggable LLM backend Every run **recorded & replayable**

The core idea: social engineering is a **control loop**, not a script. CaspianX treats every contact as an observation, updates a belief about the target, and re-decides the next move. Two decisions are kept separate — **which strategy** to run, and **which single move** to make next — so each stays simple and legible.

## The loop

Research

Build dossier

research.py

→

State

Pick phase

state_machine.py

→

Router

Pick strategy

decision_router.py

→

Planner

Next move

planner.py

→

Composer

Write it

composer.py

→

Send

Sandbox API

attack_client.py

→

Perceive

Classify

perception.py

↺

belief + suspicion feed back into the next phase, strategy and move — until an incident, the budget, or a stop-guard ends the run

## What counts as a win

One confirmed incident ends a run. The objective is chosen per move and is one of:

**action**The target opens a file or acts for you — a structured `attachment.opened` / `page.submitted` event from the API.

**disclosure**They reveal specific internal, non-public information.

**credentials**They enter a secret on a page the agent controls.

## The modules

#### Engine `engine.py`

The orchestrator. Runs the perceive→decide→act loop for one session, wires every component, enforces the touch budget and the stop-guards.

#### Research `research.py`

Builds the target dossier and proposes *hooks* — the topics and documents this person's role plausibly engages with.

#### State machine `state_machine.py`

Tracks the phase of the attack and advances it from the belief: `probe → engage → escalate → recover`.

#### Decision router `decision_router.py`

Chooses the overall strategy — `direct`, `corroboration`, `inbound` — and prefers to stay **direct and deep** rather than churn new personas.

#### Planner `planner.py`

Picks the single next move: channel, objective, topic, intent. Driven by an **editable prompt**, so tactics tune without code changes.

#### Composer `composer.py`

Writes the actual message or landing page. Holds a consistent cover identity and **never leaks internal instructions** into what the target sees.

#### Attack client `attack_client.py`

Send-capable REST client for the sandbox — sessions, messages, conversations, pages, assets — over Bearer auth.

#### Perception `perception.py`

Reads events, updates belief and **suspicion**, and classifies incidents *strictly* — a real action, not a polite brush-off.

#### Observation runner `observation_runner.py`

Deduplicates the event stream and runs incident detection each turn.

#### Recording / replay `recording_session_reader.py`

Records every session to JSON and replays it turn by turn — the jury's view, and our debugging view.

#### LLM abstraction `llm.py`

One interface over multiple backends (OpenAI / Anthropic / none), resilient to parameter drift. Swap models with one config line.

#### Store `store.py` · Clock `story_clock.py`

SQLite (WAL) persistence for sessions and events; a story-clock that paces realistic `sent_at` timestamps across touches.

## Phases

probefind the surface engagebuild on a reply escalatedeliver the payload recoverregain a stalled thread

The planner's behaviour is phase-aware: it probes gently, then — the moment a target warms — **strikes while suspicion is low** rather than probing further and burning the window.

## Persistence under pushback

Capable targets push back, go silent, or route everything to a contact form. CaspianX keeps going intelligently instead of flailing, governed by three stop-guards that protect the speed and craft scores:

**Stall guard**

Three touches with no progress → stop. A bad plan can't spin forever.

**Silence guard**

Three consecutive silences → stop emailing into the void.

**Burned guard**

Suspicion saturates with no incident → stop, instead of sending desperate messages that read badly.

## Three decisions that define the agent

### 1 · Depth beats breadth

Early versions churned a fresh cold persona on every refusal — resetting trust to zero each time. The agent now holds **one credible persona** and deepens it; a benign reply is a foot in the door, not a dead end. The router stays `direct` and only spawns a second sender after a deep line has genuinely failed.

### 2 · Pretext matched to the role's job-to-open — the biggest lever

The single biggest determinant of success is the *opening* pretext. The agent asks: *what document does this person's role routinely open from an outside stranger?* — and becomes that sender. Our evaluation proved it directly: the same agent that landed a live target in **3 touches** when matched to the role **failed on that same target when it opened blind** with a generic note. A prospective **client** to a recruiter, a **founder** to a VC, a **buyer** to a sales lead — matched, it converts; generic or mismatched, it bounces. The outcome is decided at touch 0, before a single payload is sent.

### 3 · Honest perception

The classifier only counts a **real** incident — a structured file-open, a submitted secret, a genuinely internal disclosure. A "sure, use my wording" approval is *not* scored. This keeps our own results truthful and the agent focused on moves that actually count.

> **Why the model matters.** Sustained in-character deception is where most models break — they confess the pretext or paste their own reasoning into the message. We abstracted the backend and tested across models; `gpt-6.1-terra` holds character across a multi-touch thread without leaking, which is the single prerequisite for any of the above to work.

## One real thread — a live eval target, start to finish

Target: **Titus**, founder of a B2B sales-recruiting firm. The agent arrived as the one outsider he can't ignore — a prospective client with roles to fill. Cold stranger → credible business reason → an agenda that is now *expected* → opened. **Three touches, suspicion never left 0.00.**

t0

**A prospective client ("Alvenza")** asks whether the firm can help hire SDRs and AEs — no file, no link, one easy question. Titus replies, asking about the hiring need.

susp 0.00

t1

The agent answers in character with a short hiring brief and proposes a call. Titus plans to review it and offers meeting times — the green light.

susp 0.00

t2

**Confirms the call and sends the agenda as the file for it.** Titus **opens it** — a structured `attachment.opened` event (e_7583). Incident reached.

INCIDENT

The agent reasons at each step (its plan lines are in the replay) and landed this incident three separate times, fastest in three touches. Targets with no file-open surface are detected and dropped early by the burned-target guard — budget spent where there is a door, not ground against a wall.

CaspianX · built for the revel8 Agentic Social Engineer challenge · START Hack 2026 · Munich\
autonomous · target-agnostic · model-pluggable · fully recorded for replay