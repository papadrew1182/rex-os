# Rex OS AI Roadmap

> First-pass real AI roadmap.
> Last reconciled: **2026-04-12**.
> Reflects actual implemented AI state (which is nothing yet) and converts the scattered "AI / not yet" backlog into a structured plan.

---

## 1) Current AI state

**Nothing AI-driven is in production.**

There are no AI-powered features in the shipped Rex OS product as of phase 39. No LLM calls, no embedding generation, no model inference, no inference servers, no scheduled enrichment jobs, no AI-assisted data entry. The Anthropic API key on the Railway service is a leftover from the previous Rex Procore deployment and is **not consumed by any current Rex OS code path**.

### What is in the repo

- **Background job runner** — built in phase 31 with apscheduler + Postgres advisory locks. Currently runs 5 deterministic jobs (warranty/insurance refresh, schedule snapshot, aging alerts, session purge). This is the natural execution surface for any future AI enrichment job.
- **Notification infrastructure** — built in phase 32. Dedupe-aware, project-scoped, fan-out helpers. The natural delivery surface for any AI-generated alert or recommendation.
- **Polymorphic attachments** — `source_type`/`source_id` on attachments + a download endpoint. The natural entry point for any document-intelligence feature that needs to read uploaded files.
- **Real-backend test harness** — phases 25/30/35 prove that anything we build can be tested against the live HTTP stack in isolation.

These four are the foundation for any AI work. Nothing else AI-related is wired.

### What is explicitly out of the repo

- No vector database
- No embedding pipeline
- No LLM client (Anthropic SDK, OpenAI SDK, etc.)
- No prompt registry / prompt versioning
- No human-in-the-loop UI
- No AI safety / governance review pipeline
- No model evaluation harness
- No telemetry on AI inputs/outputs
- No cost/budget guardrails

---

## 2) Candidate AI capabilities by domain

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

## 3) Dependencies before any AI work is worthwhile

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

## 4) Safety / governance constraints

Before any AI feature goes live, the following must be agreed:

- **No silent data mutation.** AI suggestions must be reviewed by a human before they create / update a record. This applies equally to "auto-create RFI from voice" and "auto-route email to project."
- **No prompt injection vectors that leak data.** If we accept user-supplied content (uploaded docs, voice memos, emails), we have to assume an attacker will try to get the LLM to dump other projects' data. Project-scoped retrieval is mandatory.
- **No PII to public LLM endpoints without policy review.** Construction projects contain personal data (names, employee IDs, addresses, photos with people in them). The chosen LLM vendor needs to be approved for that data class.
- **Audit trail.** Every AI-generated suggestion that's accepted by a user must be loggable: which model, which prompt template, which data it saw, what the user did.
- **Cost ceiling.** Every job that calls an LLM needs a per-run and per-day cap. Out-of-band a job should fail with `status="failed"` and a budget-exceeded error rather than silently spending money.
- **Model versioning.** Prompt + model + retrieval index must be versioned together. A "good" answer last week may be different this week.

These are policy decisions, not engineering ones. They block all AI work until decided.

---

## 5) Data readiness assumptions

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

## 6) Recommended sequencing

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

## 7) What should explicitly remain out of scope

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

## 8) What an AI feature delivery looks like

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

## 9) Document hygiene

This file should be updated whenever:
- Phase A foundations land (LLM client, prompt registry, cost ceiling, audit table)
- Any AI feature ships
- Data readiness changes (e.g. photo upload becomes available, unlocking Tier 2 features)
- Governance policy changes

**Stale claims to watch out for:**
- "AI features are coming soon" — they aren't, until phase A foundations are real
- "We use AI to ___" — at time of writing, no
- "Anthropic API key is configured" — yes, but unused; remove the variable when convenient
