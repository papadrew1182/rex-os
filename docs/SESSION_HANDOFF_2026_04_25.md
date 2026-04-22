# Session Handoff — 2026-04-25

Pick this up immediately in the next session.

## Where we are

**Phase 6a (backend):** SHIPPED 2026-04-21 — framework + 4 core tools (PR #16 `0578a0d`).
**Phase 6b Wave 1 (backend):** SHIPPED 2026-04-22 — 5 tools + real undo compensators (PR #17 `d487660`).
**Phase 6 Frontend Wave 1:** SHIPPED 2026-04-22 — approval cards + undo + failure UI (PR #18 `4887990`).
**Phase 4 Wave 2:** PAUSED 2026-04-22 — source data strategy decision needed (see `project_phase4_wave2_blocked` memory).
**Phase 6b Wave 2:** SHIPPED 2026-04-22 — 5 more tools (4 financial approval + 1 decision auto-pass). PR #19, merge commit `1044d6a`.

## What's live as of Phase 6b Wave 2

**14 tools registered** (up from 9). The new 5:

| slug | class | target | blast-radius profile |
|---|---|---|---|
| `create_change_event` | approval, financial | `rex.change_events` | `fires_external_effect=True`, amount informational |
| `create_pco` | approval, financial | `rex.potential_change_orders` | same |
| `pay_application` | approval, financial | `rex.payment_applications` | same |
| `lien_waiver` | approval, financial | `rex.lien_waivers` | same |
| `create_decision` | auto-pass internal | `rex.pending_decisions` | 60s undo; DELETE-by-id compensator |

All 4 financial tools are Rex-OS INSERT only — no Procore API calls in this wave (per parent spec §5 writeback sequence). Financial writeback joins a future wave after submittal writeback validates.

## Which tools work where

**Demo (seeded FK deps available):** all 5 tools work end-to-end.

**Prod (Procore-sourced FK tables empty because Phase 4 Wave 2 paused):**
- `create_change_event` ✅ needs only project_id (exists)
- `create_decision` ✅ needs only project_id
- `create_pco` ✅ works after user first creates a change_event via the tool above
- `pay_application` ❌ needs commitment_id — `rex.commitments` empty in prod
- `lien_waiver` ❌ needs payment_application_id — chicken-and-egg since pay_app blocked

Prod-blocked tools land immediately when Phase 4 data strategy ships commitments.

## Deploy state

- **Prod backend (`rex-os-api-production.up.railway.app`):** Railway auto-deployed from main, migrations applied=31 failed=0, `/api/ready` 200.
- **Demo backend (`rex-os-demo.up.railway.app`):** Same, `/api/ready` 200.
- **Vercel prod (`rex-os.vercel.app`):** Frontend deployed on merge.

Logs on both Railway envs clean on two passes.

## Known follow-ups

1. **Live LLM smoke in demo** — one real chat message triggering each of the 5 new tools to confirm SSE → card → approve/undo end-to-end.
2. **Mobile smoke on Andrew's phone** — one approval-required card (e.g. `create_change_event`) to verify touch targets + layout.
3. **Phase 4 data strategy decision** — see `project_phase4_wave2_blocked` memory for the 3 options (fix old app / direct Procore API / keep pausing). Blocks: `punch_close`, `punch_reopen`, financial-prod usability for `pay_application`/`lien_waiver`, schedule tools, inspections.
4. **Procore OAuth creds on demo Railway** — `answer_rfi` still needs `PROCORE_CLIENT_ID/CLIENT_SECRET/REFRESH_TOKEN/COMPANY_ID` to actually land in Procore.
5. **Schema gotchas banked** (for any future tools targeting these tables):
   - `rex.companies.company_type` CHECK values: `subcontractor`, `supplier`, `architect`, `engineer`, `owner`, `gc`, `consultant` (NOT `'sub'`).
   - `rex.billing_periods` uses `start_date`/`end_date`/`due_date` (NOT `period_start`/`period_end` — those are on `rex.payment_applications`).

## What's next

Andrew's pattern has been: ship → let it sit → see what hurts. With 14 tools registered and the frontend card UI live, the leverage moves away from adding more tools and toward either:

1. **Let usage guide.** Actually use the 14 tools for a few days. Gaps surface: copy quality, blast-radius tuning, missing slugs, UI rough edges.
2. **Phase 4 data strategy brainstorm.** Fix-old-app vs direct-Procore-API. This is the biggest architectural decision remaining in Phase 4/6. Unblocks a LOT (submittals/daily_logs/punch_items/schedule_activities/inspections/commitments → unlocks schedule tools, inspection tool, financial tools on prod).
3. **"Send correction" design for approval-required tools.** Once Andrew has approved a wrong RFI answer or change event, how does he reverse it? Currently there's no path. This is Phase 6c.
4. **Rex-procore writeback freeze.** Validated for RFIs (shipped 2026-04-21). Per spec §5 the next in the sequence is submittals — but Phase 4 Wave 2 blocks that too.

Candidate 1 (wait-and-learn) is probably the right default. Candidate 2 (Phase 4 data strategy brainstorm) is the highest-information follow-up if Andrew's ready to commit to a path.

## PRs merged this session

- **#19** — feat: Phase 6b Wave 2 — 5 financial/decision tools (merge commit `1044d6a`)

## Plan + spec documents

- Spec: `docs/superpowers/specs/2026-04-22-phase6b-wave2-design.md`
- Plan: `docs/superpowers/plans/2026-04-22-phase6b-wave2.md`

## Test suite

- **Backend:** 977 passed, 1 skipped (baseline 957 + 20 new Wave 2 tests).
- **Frontend:** 24 reducer + 7 action-reducer + 20 actionSummary = 51 pure-Node tests. All green.
- **Frontend build:** vite build succeeds.

## Learnings banked this session

1. **Plan-time schema assumptions need verification.** Three CHECK/column mismatches surfaced as subagent concerns during Wave 2 (company_type 'sub' vs 'subcontractor', billing_periods column names, user_accounts.person_id NOT NULL). Would have been caught earlier by running the plan's fixtures against live demo DB before dispatching the subagent. Worth adding a "discovery smoke" step to future tool-rollout plans.
2. **Subagent-driven development now feels reliable for same-pattern-repeated-N-times tasks** — 5 very similar tool modules shipped in ~15 min of subagent time vs ~90 min of direct coding. The pattern scaffolding (base.py, registry, test conventions) is the investment that pays off at T_n.
3. **`fires_external_effect=True` is the unconditional-approval marker.** Cleaner than trying to force `financial_dollar_amount>0` via magic values. Makes intent grep-able.

## Operator checklist (you, the next day)

- [ ] Railway logs first pass clean on both envs
- [ ] Railway logs second pass clean ~1 minute later
- [ ] Vercel `rex-os.vercel.app` 200
- [ ] Send one real chat message in demo that triggers `create_change_event` → verify amber approval card
- [ ] Click approve → verify row lands in rex.change_events
- [ ] Send one real chat message that triggers `create_decision` → verify green card with countdown; click Undo → verify row gone
