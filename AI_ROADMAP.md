# Rex OS AI Roadmap

> First-pass real AI roadmap.
> Original draft: phase 35.
> Last reconciled: **2026-04-13** (phase 40 finish-line pass — repo re-audited,
> no new AI scaffolding since phase 35, roadmap re-ratified).
>
> Verification ladder used in this document (consistent with
> `PROGRAM_STATE.md` §6):
>   **implemented → backend-tested → UI-verified → deployed-verified**

---

## 0) Phase 40 AI state at a glance

| Category | Status |
|---|---|
| AI features in production | **Zero.** No LLM calls, no embeddings, no inference, no vector DB, no prompt registry, no AI-driven jobs or UI. |
| AI platform scaffolding in repo | **Zero.** No `backend/app/services/llm.py`, no `app/prompts/`, no `rex.ai_invocations` table, no `/api/ai/*` routes, no AI client SDK imports. |
| AI governance primitives | **Zero.** No cost ceiling, no audit log, no eval harness, no human-in-the-loop UI pattern. |
| Reusable foundations AI could eventually plug into | Background job runner (5 deterministic jobs), notifications fan-out, polymorphic attachments, real-backend test harness, project-scoped RBAC. |

**In short: Rex OS today is a construction management platform with no AI
capabilities. Saying otherwise would be inaccurate.**

---

## 1) AI state against the verification ladder

### 1a) AI **VERIFIED today**

| Capability | implemented | backend-tested | UI-verified | deployed-verified |
|---|---|---|---|---|
| (none) | ❌ | ❌ | ❌ | ❌ |

Nothing AI-driven has cleared even the "implemented" bar.

### 1b) AI **implemented but not strongly verified**

None. There is nothing implemented at all.

The Anthropic API key on the Railway service is a **leftover** from the prior
Rex Procore deployment. Grepping the Rex OS repo (`backend/app`,
`frontend/src`) for `anthropic|openai|llm|embedding|ai_invocation` returns
zero matches outside third-party site-packages. The key should be removed the
next time someone touches Railway variables.

### 1c) AI **unknowns**

These are questions that must be answered **before** any AI feature can be
scoped. They are not engineering questions; they are policy/product questions
that block all AI work.

- **Which LLM vendor is approved for construction-project data?** Unknown.
  No vendor selection has been made. Construction data contains PII (names,
  addresses, employee IDs, photos with people in them).
- **What is the cost ceiling per job / per day / per user?** Unknown.
- **Who signs off on the first AI feature going live?** Unknown.
- **What is the retention policy for LLM inputs / outputs?** Unknown.
- **Where does telemetry on AI calls live?** Unknown — no Sentry, no
  OpenTelemetry, no audit table.
- **Is "assistive" the only allowed paradigm, or are any autonomous writes
  allowed?** Unknown. The default position (and this document's
  recommendation) is: **assistive only, no autonomous writes, ever**.

### 1d) Deferred AI ledger

All entries below are deferred — none are scheduled, resourced, or designed.
They are catalogued here only so a future sprint that wants to ship AI has a
starting list instead of a blank page. Order is rough by value, not by
feasibility. See section 2 for a feasibility split by data readiness.

**Tier L (assistive, no new data required)**
- Daily log narrative generator (manpower + tasks + weather → work summary draft)
- Meeting prep packets (open RFIs + schedule drift + action items → markdown brief)
- Vendor risk scoring (pure SQL, no LLM)
- Cost benchmarks (pure SQL, no LLM)

**Tier M (moderate data gap)**
- Weather forecast integration (lat/lng now in DB; external API + daily job)
- Insurance cert OCR extraction
- Spec QA via embedding + retrieval
- Submittal auto-review against spec sections
- RFI auto-draft from drawings + specs + similar past RFIs
- Schedule risk prediction from historical snapshots
- Recovery plan suggestions when a milestone is flagged at-risk
- Delay claim evidence assembly

**Tier H (blocked on significant new infra)**
- Photo safety scan (blocked on photo upload UI + vision LLM pipeline)
- Drawing intelligence (blocked on drawing processing pipeline)
- Voice daily log / voice commands (blocked on voice capture + STT)
- Email triage (blocked on email integration)

**Permanently out of scope**
- Autonomous data mutation
- AI-generated legal / contract text
- Predictive bidding with liability implications
- Replacing humans on safety decisions
- Custom model training / fine-tuning
- Generic "chat with your construction app"
- Bonus / scorecard / performance AI (the underlying system is itself deferred)

### 1e) AI panel / UX hardening still needed

There is no AI surface in the frontend today. Before any user-facing AI
feature can ship, the frontend needs:

1. **AI suggestion drawer pattern** — a reusable `FormDrawer`-style component
   that shows the AI's proposed change, the inputs it saw, the confidence
   (if applicable), and accept / reject affordances. No "auto-apply" path.
2. **Inline AI callout component** — a non-blocking banner for read-only
   suggestions (e.g. "Meeting prep packet available for this meeting").
3. **AI invocation history panel** — per-record "AI suggestions for this
   item" log so users can see what was suggested and what happened.
4. **Cost / status surface in AdminJobs** — per-job AI budget usage, recent
   invocation list, failure mode breakdown.
5. **Opt-out toggle in user settings** — because not all users will want
   assistive AI in their workflow, and regulated users may be forbidden.
6. **Feature flag plumbing** — every AI feature must be flag-gated so it can
   be disabled without a redeploy.

None of these components exist. The existing `forms.jsx`, `notifications.jsx`,
and `AlertCallout.jsx` patterns are the right style base, but the AI surface
itself needs to be designed from scratch.

### 1f) Required foundation before any real AI rollout

These are the prerequisites that must be **shipped and verified** (not just
started) before the first AI feature can be turned on in production. They
are not AI features themselves — they are engineering and governance
primitives.

| # | Foundation item | Status |
|---|---|---|
| 1 | **CI workflow** — at minimum `pytest tests/ -q` and `npx vite build` on every PR | ❌ not built |
| 2 | **Sentry (or equivalent) error tracking** on backend + frontend | ❌ not built |
| 3 | **LLM client module** (`backend/app/services/llm.py`) with vendor abstraction | ❌ not built |
| 4 | **Prompt registry** — versioned prompt templates in `backend/app/prompts/` with load-by-version semantics | ❌ not built |
| 5 | **Cost ceiling pattern** — per-job and per-day caps with a `status="failed"` budget-exceeded path | ❌ not built |
| 6 | **`rex.ai_invocations` audit table** — every LLM call logs prompt version, model, input hash, output, cost, user, outcome | ❌ not built |
| 7 | **Human-in-the-loop UI pattern** — see §1e | ❌ not built |
| 8 | **Eval harness** — test fixture + assertion framework in `backend/tests/ai/` for prompt/output regression | ❌ not built |
| 9 | **Feature flag plumbing** (backend + frontend) | ❌ not built |
| 10 | **Photo upload UI + storage backend** (only required for vision-based features) | ❌ not built (deferred) |
| 11 | **Vendor selection + PII policy approval** | ❌ not done |
| 12 | **Telemetry plumbing** (success rate, avg cost, avg latency per feature) | ❌ not built |

**No AI feature should ship until items 1–9 are complete.** Item 10 only
blocks photo/vision features. Items 11–12 gate production rollout.

### Summary

| Verification level | Count |
|---|---|
| AI features implemented | 0 |
| AI features backend-tested | 0 |
| AI features UI-verified | 0 |
| AI features deployed-verified | 0 |
| Foundation items shipped | 0 of 12 |

If a future reader finds this doc and expects to find "phase X is the AI
phase," the honest answer is: **no AI phase exists yet.** The work starts
with foundation items 1–9, not with a feature.

---

## 2) What's already in the repo that AI could eventually use

- **Background job runner** — built in phase 31 with apscheduler + Postgres advisory locks. Currently runs 5 deterministic jobs (warranty/insurance refresh, schedule snapshot, aging alerts, session purge). This is the natural execution surface for any future AI enrichment job.
- **Notification infrastructure** — built in phase 32. Dedupe-aware, project-scoped, fan-out helpers. The natural delivery surface for any AI-generated alert or recommendation.
- **Polymorphic attachments** — `source_type`/`source_id` on attachments + a download endpoint. The natural entry point for any document-intelligence feature that needs to read uploaded files.
- **Real-backend test harness** — phases 25/30/35/40 prove that anything we build can be tested against the live HTTP stack in isolation. The eval harness (foundation item 8) can extend this pattern.
- **Project-scoped RBAC** — `assert_project_access`, `get_readable_project_ids`, `enforce_project_read`. Any AI feature that reads project data must honor these helpers. Project-scoped retrieval is mandatory for prompt-injection safety.

These are enabling, not prerequisite. They won't on their own make AI
feasible — the 12 foundation items in §1f still have to ship first.

### Explicitly NOT in the repo

- No vector database
- No embedding pipeline
- No LLM client (Anthropic SDK, OpenAI SDK, etc.)
- No prompt registry / prompt versioning
- No human-in-the-loop UI
- No AI safety / governance review pipeline
- No model evaluation harness
- No telemetry on AI inputs/outputs
- No cost/budget guardrails
- No `rex.ai_invocations` audit table

---

## 3) Candidate AI capabilities by domain

These come from the original parity audit (`FIELD_PARITY_MATRIX.md`) where the previous Rex Procore had ~25 AI/intelligence tables. None are in Rex OS by design — they were intentionally deferred. This list catalogs **what could be built**, not what's planned.

### Document intelligence
| Capability | Description | Pre-reqs | Estimated complexity |
|---|---|---|---|
| **Drawing intelligence** | Ask questions of drawings, count elements (doors/outlets/fixtures), compare revisions | Drawing upload + image processing pipeline + multi-modal LLM | High |
| **Spec QA** | Natural-language Q&A against project specifications | Spec storage + chunked embedding + retrieval | Medium |
| **Submittal review** | Auto-check submittal data against spec requirements | Spec embeddings + structured submittal data | High |
| **RFI auto-draft** | Generate RFI response drafts from drawings + specs + similar past RFIs | Embedding all 3 sources, retrieval-augmented generation | Medium |
| **Insurance cert extraction** | OCR + extract carrier/policy/expiry/limit from uploaded cert PDFs | OCR + structured extraction | Medium |
| **Invoice import** | OCR + line-item extraction from vendor invoices | OCR + structured extraction + cost code matching | Medium |
| **Document generation** | Generate letters, transmittals, standard forms from project context | Template registry + LLM generation | Low-medium |

### Predictive / risk
| Capability | Description | Pre-reqs | Estimated complexity |
|---|---|---|---|
| **Schedule risk prediction** | Predict which milestones will slip based on current trends | Historical snapshots + ML model or LLM-based reasoning | High |
| **Delay claim support** | Auto-assemble delay claim packets from daily logs + weather + RFI/submittal pendency | Job to gather evidence + structured narrative generation | Medium |
| **Recovery plans** | Suggest schedule recovery options when milestones drift | Schedule history + LLM reasoning | High |
| **Vendor risk scoring** | Score vendors by punch closure rate, RFI age, submittal turn time, insurance status | Pure SQL aggregation; no LLM needed | Low |
| **Budget risk** | Flag cost codes likely to exceed budget based on commitment + change exposure trends | Historical patterns; ML or rule-based | Medium |

### Field intelligence
| Capability | Description | Pre-reqs | Estimated complexity |
|---|---|---|---|
| **Photo analysis** | Detect safety violations or progress indicators in uploaded photos | Photo upload UI (not built) + vision LLM | Medium-high |
| **Safety walk auto-observation** | Generate observations from uploaded photos | Photo upload + vision LLM + observation create | Medium |
| **Voice transcription** | Transcribe daily log voice memos into structured fields | Voice upload + Whisper-class STT | Medium |
| **Voice commands** | "Mark RFI 24 answered" → API call | STT + intent parsing + confirmation UI | High |
| **Daily log narrative generation** | Auto-generate daily log narratives from manpower + tasks + weather | Existing structured data + LLM | Low-medium |

### Meeting / communication
| Capability | Description | Pre-reqs | Estimated complexity |
|---|---|---|---|
| **Meeting prep packets** | Pre-meeting AI summary of project state, open items, decisions needed | Existing aggregation + LLM summarization | Low-medium |
| **Decision tracker** | Extract decisions from meeting minutes; cross-link to RFIs/CEs | Minutes ingestion + LLM extraction | Medium |
| **Email triage** | Classify inbound vendor emails, route to project + person | Email integration (not built) + LLM | High |

### Cost / benchmarking
| Capability | Description | Pre-reqs | Estimated complexity |
|---|---|---|---|
| **Cost benchmarks** | Cross-project unit cost comparisons by cost code + project type | Pure SQL on historical commitments; no LLM needed | Low |
| **Cost estimation** | Generate ROM estimates from a scope description and historical data | LLM + retrieval over benchmarks | Medium |
| **Bid leveling** | Compare bid submissions, flag exclusions, score value | LLM extraction from PDFs + structured comparison | Medium-high |

### Weather / context
| Capability | Description | Pre-reqs | Estimated complexity |
|---|---|---|---|
| **Weather forecast integration** | Daily weather pull per project (lat/lng); flag work-impact days | External API (e.g. open-meteo); job to pull; lat/lng on projects (✅ shipped phase 39) | Low |
| **Weather-driven schedule alerts** | Notification when forecast affects critical path activities | Weather data + schedule data + threshold logic | Medium |

---

## 4) Dependencies before any AI work is worthwhile

Before building any AI feature, these foundations need to be in place:

1. **CI / automated test enforcement** — without it, AI features that depend on data shape can silently regress
2. **Production error tracking** (Sentry or equivalent) — AI features fail in subtle ways; we need visibility
3. **Photo upload UI + storage backend** — required for any vision-based feature
4. **An LLM client and prompt registry** — NOT present. Adding this requires picking a vendor, setting up env vars, defining a usage policy
5. **A cost / budget guardrail** — LLM bills can run away. Need per-job and per-user limits before any production AI feature
6. **An eval harness** — for any non-trivial AI feature, we need a way to measure quality before shipping
7. **A human-in-the-loop UI pattern** — every meaningful AI output needs a confirm/reject affordance before it mutates real data
8. **A telemetry surface** — what was the prompt, what was the response, what did the user do — needed for both debugging and quality improvement

None of these foundations exist yet.

---

## 5) Safety / governance constraints

Before any AI feature goes live, the following must be agreed:

- **No silent data mutation.** AI suggestions must be reviewed by a human before they create / update a record. This applies equally to "auto-create RFI from voice" and "auto-route email to project."
- **No prompt injection vectors that leak data.** If we accept user-supplied content (uploaded docs, voice memos, emails), we have to assume an attacker will try to get the LLM to dump other projects' data. Project-scoped retrieval is mandatory.
- **No PII to public LLM endpoints without policy review.** Construction projects contain personal data (names, employee IDs, addresses, photos with people in them). The chosen LLM vendor needs to be approved for that data class.
- **Audit trail.** Every AI-generated suggestion that's accepted by a user must be loggable: which model, which prompt template, which data it saw, what the user did.
- **Cost ceiling.** Every job that calls an LLM needs a per-run and per-day cap. Out-of-band a job should fail with `status="failed"` and a budget-exceeded error rather than silently spending money.
- **Model versioning.** Prompt + model + retrieval index must be versioned together. A "good" answer last week may be different this week.

These are policy decisions, not engineering ones. They block all AI work until decided.

---

## 6) Data readiness assumptions

Roughly, the AI features divide into 3 data-readiness tiers:

### Tier 1 — Ready to build today (data exists in repo)
- Vendor risk scoring (uses commitments + warranties + insurance + punch + RFI + submittal data — all in DB)
- Cost benchmarks (uses commitments + cost codes — all in DB)
- Daily log narrative generation (uses daily_logs + manpower_entries + tasks — all in DB)
- Meeting prep packets (uses meetings + action items + open RFIs/punch + schedule drift — all in DB)

These need: LLM client, prompt registry, cost ceiling, human-in-the-loop UI. They DON'T need new data.

### Tier 2 — Need a moderate data gap closed
- Weather forecast integration (lat/lng now exists from phase 39; just need an external API call)
- Insurance cert extraction (existing attachments with `source_type=insurance_certificate` work; need OCR pipeline)
- Submittal review (specs + submittals exist; need spec embedding pipeline)
- RFI auto-draft (drawings + specs + RFIs exist; need embedding pipeline)
- Bid leveling (no bid_packages table currently; would need a small schema addition)

### Tier 3 — Need significant new infra
- Photo analysis (no photo upload UI; no vision pipeline)
- Voice transcription / commands (no voice capture UI; no STT pipeline)
- Email triage (no email integration; no inbound webhook)
- Drawing intelligence (drawings table exists but stores only `image_url`; would need a drawing processing pipeline)

---

## 7) Recommended sequencing

### Phase A — Foundation (must come first, no AI features yet)
1. CI workflow (frontend build + backend tests on PR)
2. Sentry or equivalent error tracking
3. Pick an LLM vendor and add a thin client (`backend/app/services/llm.py`)
4. Define a prompt registry pattern (versioned `.txt` or `.yaml` files in `backend/app/prompts/`)
5. Define a cost ceiling pattern (per-job daily cap; reject when exceeded)
6. Define a human-in-the-loop UI pattern (an "AI suggestion drawer" that the user explicitly accepts/rejects)
7. Define an audit log pattern (`rex.ai_invocations` table or similar)

**No AI feature should ship until phase A is done.** This is governance, not AI work.

### Phase B — Assistive intelligence (low-risk, high-value, no new data)
1. **Daily log narrative generator** — given the structured manpower + tasks + weather, generate a natural-language work summary that the user can accept into the `work_summary` field. Pure assistive, single record at a time, easy to QA.
2. **Meeting prep packet** — given a meeting type + project, generate a markdown brief of open RFIs, recent decisions, schedule drift, action items. Read-only. Outputs to a print-friendly view.
3. **Vendor risk scoring** — pure SQL aggregation; ranks vendors by composite score. No LLM needed. Show on a future Vendor Detail page.
4. **Cost benchmarks** — pure SQL aggregation; cross-project unit cost ranges by cost code. Also no LLM. Show on Budget Overview detail.

These are the "layups" — high product value, low AI risk, no new infrastructure beyond phase A.

### Phase C — Predictive / risk (after phase B is in production for a while)
1. **Schedule risk prediction** — feed schedule snapshots + recent variance into an LLM and ask "which milestones are at risk and why?" Deliver as `schedule_drift` notifications.
2. **Weather forecast integration** — daily job that fetches forecast for project lat/lng (now in DB), flags days that affect critical-path outdoor activities. Pure deterministic, no LLM.
3. **Delay claim support** — assemble evidence packets (daily logs, RFI/submittal pendency, weather) on demand. LLM for narrative; structured data otherwise.
4. **Recovery plan suggestions** — when a milestone is flagged at-risk, generate 2-3 recovery options. Human accepts one.

### Phase D — Document & vision intelligence (after photo upload + storage are sorted)
1. **Insurance cert extraction** — OCR uploaded cert PDFs; populate cert fields; user reviews and accepts.
2. **Invoice import** — OCR uploaded vendor invoices; suggest pay-app line items; user reviews.
3. **Spec QA** — embed specs; let users ask natural-language questions. Read-only.
4. **Submittal review** — compare submittal data against spec requirements; flag mismatches.
5. **Photo safety scan** — detect violations in uploaded photos; create draft observations. Human accepts.
6. **RFI auto-draft** — given an open RFI, suggest a response based on similar past RFIs + drawings + specs.

### Phase E — Voice & advanced (long-range)
1. **Drawing intelligence** — count elements, ask questions. Vision-LLM heavy.
2. **Voice daily log capture** — transcribe + structure into the daily log form.
3. **Voice commands** — "Close punch item 42" → API call with confirmation.
4. **Email triage** — only if email integration is built first.

---

## 8) What should explicitly remain out of scope

- **Autonomous agents** — no AI feature should mutate data without human review. Period.
- **Black-box models that can't explain themselves** — every AI output needs to surface its inputs/reasoning so users can sanity-check.
- **Custom model training** — fine-tuning, RLHF, etc. are not justifiable at current scale. Use frontier models with retrieval.
- **AI-generated contract / legal text** — too high-risk; needs lawyer review on every output, defeats the value.
- **Predictive bidding** — AI-suggested bid prices have liability implications that need a separate policy review.
- **Replacing humans in safety decisions** — AI can flag, suggest, score. Humans decide.
- **Anything in Tier 3 of the data readiness section** until the underlying data exists.
- **Generic "ChatGPT in your construction app"** — LLM features should be specific, scoped, and accountable. No catch-all chat.
- **Bonus / scorecard / performance system AI** — explicitly out of scope at the product level until the bonus system itself is designed.

---

## 9) What an AI feature delivery looks like

Once phase A is complete, every AI feature should follow this template:

1. **Spec doc**: 1-page describing the user input, the AI input, the AI output, the human-in-the-loop UI, the failure mode, the cost ceiling
2. **Prompt template**: versioned in `backend/app/prompts/`
3. **Eval set**: 10-20 example inputs + expected outputs in `backend/tests/ai/`
4. **Cost ceiling**: per-run and per-day caps documented
5. **Audit log entry**: every invocation persists in `rex.ai_invocations`
6. **Human review UI**: explicit accept / reject affordance; no auto-write
7. **Telemetry**: success rate, average cost, average latency
8. **Rollback plan**: feature-flagged so it can be turned off without redeploy

This is how you build AI features without building an AI mess. Every shortcut here is technical debt with compounding interest.

---

## 10) Document hygiene

This file should be updated whenever:
- Phase A foundations land (LLM client, prompt registry, cost ceiling, audit table)
- Any AI feature ships
- Data readiness changes (e.g. photo upload becomes available, unlocking Tier 2 features)
- Governance policy changes

**Stale claims to watch out for:**
- "AI features are coming soon" — they aren't, until phase A foundations are real
- "We use AI to ___" — at time of writing, no
- "Anthropic API key is configured" — yes, but unused; remove the variable when convenient
