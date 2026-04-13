# Rex OS Field Parity Backlog

> Original audit date: 2026-04-11
> Last reconciled: **2026-04-12** (phase 40 reconciliation pass)
> Derived from: FIELD_PARITY_MATRIX.md, FIELD_DECISIONS.md, SCREEN_TO_DATA_MAP.md

---

## CURRENT STATE (Post-Phase 40)

**Parity-class backlog is empty except for one deferred major item.**

- **P0 items**: 0 open (none were ever opened in the audit).
- **P1 items**: 0 open — all 11 closed across phases 3, 4, 5, and 21.
- **Practical P2 items (P2-1 through P2-8)**: 0 open — all 8 closed across
  phases 21 (P1/P2 batch), 31–34 (notifications/alerts), and 38/39 (schedule
  variance + free float, project lat/lng, company mobile/website, observation
  contributing fields, closeout checklist spec fields, O&M manual tracker).
- **P2-9 bonus / performance system**: **deferred major work** — explicitly out
  of scope until a product design pass. Not tracked as "open" here because
  closing it is a multi-sprint product redesign, not a parity fix.

The sections below are preserved as audit history for how each P1/P2 item was
actually closed. They should be read as a "completed work log," not an
active backlog.

---

## STATUS UPDATE — 2026-04-12 (Phase 38/39)

### All practical P2 items CLOSED ✅

Migration `005_phase38_phase39_p2_batch.sql` closed the remaining P2 items:

| Item | Closure |
|---|---|
| P2-1 projects.latitude/longitude | ✅ Phase 39 (migration 005 + `Project` model + `/api/projects/` CRUD + test_phase38_phase39_p2) |
| P2-2 observations.contributing_behavior/contributing_condition | ✅ Phase 39 |
| P2-3 closeout_checklist_items.spec_division/spec_section | ✅ Phase 39 (display-only; edit drawer deferred frontend-side) |
| P2-4 `om_manuals` table + CRUD + OmManuals page | ✅ Phase 39 |
| P2-5 companies.mobile_phone/website | ✅ Phase 39 |
| P2-6 schedule_activities.start_variance_days/finish_variance_days | ✅ Phase 38 |
| P2-7 schedule_activities.free_float_days | ✅ Phase 38 |
| P2-8 generic alert/notification infrastructure | ✅ Phases 31–34 (see section below) |

The only remaining P2 item is **P2-9 bonus/performance system**, which is
deferred major work, not an open backlog item.

---

## STATUS UPDATE — 2026-04-12 (Phase 35)

### P2-8 CLOSED ✅
- **P2-8 generic alert/notification infrastructure** — closed by phases 32+33+34.
  - `rex.notifications` table with dedupe partial unique index ships in migration 004.
  - `upsert_notification` / `resolve_notifications_by_dedupe_prefix` services handle fan-out and stale-alert resolution.
  - 5 user-facing API endpoints + admin job-trigger endpoints.
  - Topbar bell (60 s poll) + full Notifications page.
  - Domain-specific alert tables like `warranty_alerts` are preserved as the canonical source; `rex.notifications` is the delivery/inbox layer.

---

## STATUS UPDATE — 2026-04-12 (Phase 25)

### P0 Items: 0 open (none ever opened)

### P1 Items: ALL CLOSED ✅
The following items from the original April 11 audit have been **closed**:

| Item | Sprint | Status |
|---|---|---|
| P1-1 closed_by on punch_items | Phase 4 | ✅ Closed |
| P1-2 is_critical_path on punch_items + submittals | Phase 4 | ✅ Closed |
| P1-3 rfi_manager on rfis | Phase 4 | ✅ Closed |
| P1-4 submittal_manager_id on submittals | Phase 4 | ✅ Closed |
| P1-5 actual_start/actual_finish on schedule_activities | Phase 21 | ✅ Closed |
| P1-6 wbs_code on schedule_activities | Phase 21 | ✅ Closed |
| P1-7 estimated_completion_date on commitments | Phase 3 | ✅ Closed |
| P1-8 forecast_date + percent_complete on completion_milestones | Phase 21 | ✅ Closed |
| P1-9 Insurance detail (new normalized insurance_certificates table) | Phase 21 | ✅ Closed |
| P1-10 system_or_product + manufacturer on warranties | Phase 21 | ✅ Closed |
| P1-11 change_event_line_items table | Phase 5 | ✅ Closed |

**P1 backlog is now empty.**

### P2 Items (as of this phase 25 update — see phase 38/39 section above for final state)
- P2-1 latitude/longitude on projects → **CLOSED in phase 39**
- P2-2 contributing_behavior/condition on observations → **CLOSED in phase 39**
- P2-3 spec_division/section on closeout_checklist_items → **CLOSED in phase 39** (display-only; edit drawer deferred)
- P2-4 O&M Manual Tracker table → **CLOSED in phase 39** (new `om_manuals` table + page)
- P2-5 mobile_phone/website on companies → **CLOSED in phase 39**
- P2-6 start_variance/finish_variance separation → **CLOSED in phase 38**
- P2-7 free_float on schedule_activities → **CLOSED in phase 38**
- P2-8 Notification/alert infrastructure → **CLOSED in phases 31–34**
- P2-9 Bonus/performance system → **DEFERRED** major product work (see "Deferred major work" section)

### Intentionally excluded (Procore mirror baggage)
- procore_id, synced_at, sync_source, is_deleted, deleted_at on every table
- Denormalized *_name mirror fields where FK joins exist
- Procore internal status/type/reason mapping metadata
- Procore datagrid_uuid / datagrid_created_at fields

### Sprint progress summary (phase 25 snapshot — superseded by phase 40)
- **35 phases completed at time of this update** (1 audit + 34 build phases)
- **4 migrations applied at time of this update** — superseded: there are now
  **8 migrations total** (4 `rex2_*` bootstrap files + `002` through `005`
  phase-numbered batches). See `migrations/` and `BACKEND_ROADMAP.md`.
- **All P0 + P1 audited gaps closed**
- **P2-8 also closed** (generic notification/alert infrastructure shipped in phases 32-34)
- **No mock data anywhere** — every screen reads/writes real backend

### Deferred major work (not an "open P2" item)

- **P2-9 bonus / performance system** — ~12 tables in the original Rex Procore
  schema (`quarterly_scorecards`, `milestone_bonus_pools`, `buyout_savings`,
  `ebitda_growth`, `achievements`, `leaderboard_metrics`, etc.). Requires a
  full product design pass before any engineering work. Not blocking any
  current product surface. **Intentionally deferred — not tracked as open
  parity work in this backlog.**

---

> **Reader note (phase 40 reconciliation):** Every P1 and P2 item enumerated
> below has been **closed** except for P2-9 (bonus/performance system). The
> detailed descriptions are preserved as audit history so you can see what
> shipped and how. See the "CURRENT STATE" summary at the top of this file
> for the active picture.

---

## P0 Parity Fixes

> P0 = Blocks parity with current product slice or prevents building the next logical screen family.

### P0-1: No P0 schema gaps identified

**Why it matters:** The current Rex OS closeout slice (Portfolio, Checklists, Milestones, Schedule Health, Execution Health, Attachments) has complete field parity. The data model for all 57 tables covers the needed fields.

**Acceptance criteria:** N/A - this is a positive finding.

**Work type:** None required.

---

## P1 Parity Fixes

> P1 = Important for the next wave of screen builds. These are small schema additions, not redesigns.

### P1-1: Add `closed_by` to punch_items

**Why it matters:** Rex Procore tracks who closed a punch item. This is needed for the Punch List management screen to show accountability and for audit trails.

**Affected domains/screens:** Field Ops > Punch List page
**Acceptance criteria:**
- `closed_by UUID REFERENCES rex.people(id)` column added to `rex.punch_items`
- ORM model updated
- Schema updated (create/update/response)
- Migration script

**Work type:** Backend schema/model + migration

---

### P1-2: Add `is_critical_path` to punch_items and submittals

**Why it matters:** Rex Procore flags items on the critical path. This drives portfolio-level risk views and helps PMs prioritize.

**Affected domains/screens:** Field Ops > Punch List, Submittals, Portfolio risk views
**Acceptance criteria:**
- `is_critical_path BOOLEAN NOT NULL DEFAULT false` added to `rex.punch_items` and `rex.submittals`
- ORM models updated
- Schemas updated
- Migration script

**Work type:** Backend schema/model + migration

---

### P1-3: Add `rfi_manager` to rfis

**Why it matters:** Rex Procore has an RFI manager role distinct from assignee and ball-in-court. This is needed for the RFI management screen workflow.

**Affected domains/screens:** Field Ops > RFI Management page
**Acceptance criteria:**
- `rfi_manager UUID REFERENCES rex.people(id)` column added to `rex.rfis`
- ORM model and schema updated
- Migration script

**Work type:** Backend schema/model + migration

---

### P1-4: Add `submittal_manager_id` to submittals

**Why it matters:** Rex Procore has a submittal manager role. Needed for the Submittal management screen workflow.

**Affected domains/screens:** Field Ops > Submittals page
**Acceptance criteria:**
- `submittal_manager_id UUID REFERENCES rex.people(id)` column added to `rex.submittals`
- ORM model and schema updated
- Migration script

**Work type:** Backend schema/model + migration

---

### P1-5: Add `actual_start_date` / `actual_finish_date` to schedule_activities

**Why it matters:** Rex Procore separates planned dates from actual dates. Rex OS currently stores only start_date/end_date without distinguishing planned vs actual. This matters for schedule variance analysis and earned value calculations.

**Affected domains/screens:** Schedule > Schedule Health, any schedule analysis
**Acceptance criteria:**
- `actual_start_date DATE` and `actual_finish_date DATE` columns added to `rex.schedule_activities`
- Existing `start_date`/`end_date` become the planned/current dates
- `variance_days` logic updated to use actuals when available
- ORM model and schema updated
- Migration script

**Work type:** Backend schema/model + migration + workflow logic

---

### P1-6: Add `work_breakdown_structure` to schedule_activities

**Why it matters:** Rex Procore stores WBS codes on tasks. This is used for schedule organization and reporting in the Schedule Intelligence views.

**Affected domains/screens:** Schedule > Schedule Health, Enriched Lookahead
**Acceptance criteria:**
- `wbs_code TEXT` column added to `rex.schedule_activities`
- ORM model and schema updated
- Migration script

**Work type:** Backend schema/model + migration

---

### P1-7: Add `estimated_completion_date` to commitments

**Why it matters:** Rex Procore tracks when a commitment is expected to complete. Needed for commitment management and schedule-financial integration.

**Affected domains/screens:** Financials > Commitment Management
**Acceptance criteria:**
- `estimated_completion_date DATE` column added to `rex.commitments`
- ORM model and schema updated
- Migration script

**Work type:** Backend schema/model + migration

---

### P1-8: Add `forecast_date` and `percent_complete` to completion_milestones

**Why it matters:** Rex Procore milestone_tracking has both baseline and forecast dates, plus percent_complete. Rex OS only has scheduled_date and actual_date. Forecast date enables proactive milestone monitoring.

**Affected domains/screens:** Closeout > Milestones, Portfolio readiness
**Acceptance criteria:**
- `forecast_date DATE` column added to `rex.completion_milestones`
- `percent_complete NUMERIC NOT NULL DEFAULT 0 CHECK (>= 0 AND <= 100)` added
- ORM model and schema updated
- Remove UNIQUE constraint on (project_id, milestone_type) if forecast tracking requires multiple milestone instances
- Migration script

**Work type:** Backend schema/model + migration

---

### P1-9: Add insurance detail fields to companies (or new table)

**Why it matters:** Rex Procore tracks GL, WC, and Auto insurance separately with expiration dates and limits. Rex OS has only a single `insurance_expiry` field. Insurance compliance is a core GC workflow.

**Affected domains/screens:** Foundation > Vendor management, Compliance views
**Acceptance criteria:** Either:
- Option A: Add `insurance_gl_expiry DATE`, `insurance_wc_expiry DATE`, `insurance_auto_expiry DATE`, `insurance_gl_limit NUMERIC`, `insurance_wc_limit NUMERIC`, `insurance_auto_limit NUMERIC` to `rex.companies`
- Option B: Create `rex.insurance_certificates` table (more normalized, allows multiple certs per vendor)
- Decision: Option B is recommended for extensibility

**Work type:** Backend schema/model + migration

---

### P1-10: Add `system_or_product` and `manufacturer` to warranties

**Why it matters:** Rex Procore warranty_items tracks what system/product is covered and who manufactured it. This is essential for warranty claim management.

**Affected domains/screens:** Closeout > Warranties
**Acceptance criteria:**
- `system_or_product TEXT` and `manufacturer TEXT` columns added to `rex.warranties`
- ORM model and schema updated
- Migration script

**Work type:** Backend schema/model + migration

---

### P1-11: Add change event line items

**Why it matters:** Rex Procore stores CE line items (as JSONB). Rex OS change_events has no line-item breakdown. Needed for change order workflow screens.

**Affected domains/screens:** Financials > Change Order Workflow
**Acceptance criteria:**
- Create `rex.change_event_line_items` table with: id, change_event_id (FK), cost_code_id (FK), description, amount, sort_order, created_at
- ORM model and schema created
- Routes added
- Migration script

**Work type:** Backend schema/model + API/serializer + migration

---

## P2 Parity Fixes

> P2 = Nice-to-have or future-phase. Not blocking any near-term screen builds.

### P2-1: Add geolocation to projects

**Why it matters:** Rex Procore stores latitude/longitude for map-based views. Not needed for current screens but useful for future portfolio map.

**Affected domains/screens:** Portfolio map view (not yet planned)
**Acceptance criteria:**
- `latitude NUMERIC` and `longitude NUMERIC` columns added to `rex.projects`
- Migration script

**Work type:** Backend schema/model + migration

---

### P2-2: Add contributing_behavior / contributing_condition to observations

**Why it matters:** Rex Procore tracks root cause factors on observations. Useful for safety analytics but not required for the observations list screen.

**Affected domains/screens:** Field Ops > Observations, Safety analytics
**Acceptance criteria:**
- `contributing_behavior TEXT` and `contributing_condition TEXT` columns added to `rex.observations`
- Migration script

**Work type:** Backend schema/model + migration

---

### P2-3: Add spec_division / spec_section to closeout_checklist_items

**Why it matters:** Rex Procore extended closeout_checklist links items to spec sections. Useful for spec-based closeout tracking.

**Affected domains/screens:** Closeout > Checklists
**Acceptance criteria:**
- `spec_division TEXT` and `spec_section TEXT` columns added to `rex.closeout_checklist_items`
- Migration script

**Work type:** Backend schema/model + migration

---

### P2-4: Create O&M Manual Tracker table

**Why it matters:** Rex Procore has a dedicated om_manual_tracker for tracking O&M document receipt by spec section. Rex OS currently only has is_om_received boolean on warranties.

**Affected domains/screens:** Closeout > Document completeness
**Acceptance criteria:**
- Create `rex.om_manuals` table with: id, project_id, spec_section, spec_title, required_count, received_count, status, vendor_company_id, notes, created_at, updated_at
- ORM model and schema created
- Migration script

**Work type:** Backend schema/model + API/serializer + migration

---

### P2-5: Add mobile_phone and website to companies

**Why it matters:** Rex Procore vendors have multiple phone fields and website. Low priority but useful for vendor contact management.

**Affected domains/screens:** Foundation > Vendor details
**Acceptance criteria:**
- `mobile_phone TEXT` and `website TEXT` columns added to `rex.companies`
- Migration script

**Work type:** Backend schema/model + migration

---

### P2-6: Add start_variance / finish_variance separation to schedule_activities

**Why it matters:** Rex Procore tracks start and finish variance separately. Rex OS has a single variance_days. Useful for detailed schedule analysis.

**Affected domains/screens:** Schedule > Schedule Health
**Acceptance criteria:**
- `start_variance_days INT` and `finish_variance_days INT` columns (alongside existing variance_days as the "primary" variance)
- Migration script

**Work type:** Backend schema/model + migration

---

### P2-7: Add free_float to schedule_activities

**Why it matters:** Rex Procore tracks total float and free float separately. Rex OS has only float_days. Free float is useful for resource leveling.

**Affected domains/screens:** Schedule > Schedule analysis
**Acceptance criteria:**
- `free_float_days INT` column added to `rex.schedule_activities`
- Migration script

**Work type:** Backend schema/model + migration

---

### P2-8: Design and build notification/alert infrastructure

**Why it matters:** Rex Procore has extensive alert/compliance log tables (RFI alerts, punch alerts, insurance alerts, daily log compliance, etc.). Rex OS has warranty_alerts but no general alert system.

**Affected domains/screens:** Cross-cutting
**Acceptance criteria:**
- Design decision: individual alert tables per domain vs. generic `rex.alerts` table
- Minimum: insurance expiry alerts, RFI aging alerts, punch aging alerts
- Not required for any current screen

**Work type:** Architecture design + backend schema/model + workflow logic + migration

---

### P2-9: Design and build bonus/performance system

**Why it matters:** Rex Procore has extensive bonus/scorecard infrastructure. This is a major feature area that Rex OS hasn't started.

**Affected domains/screens:** Performance > Scorecards, Bonus Engine, My Scorecard
**Acceptance criteria:**
- Requires full design document before implementation
- At minimum: quarterly_scorecards, milestone_bonus_pools tables
- Must support: safety, schedule, quality, process hygiene scoring categories

**Work type:** Architecture design + backend schema/model + API + frontend + migration (major effort)

---

## Backlog Summary (Historical → Current)

| Priority | Original Count | Remaining Open | Notes |
|---|---|---|---|
| P0 | 0 | 0 | None ever opened |
| P1 | 11 | **0** | All closed phases 3–5, 21 |
| P2 | 9 | **0 practical, 1 deferred** | P2-1..P2-8 closed phases 21, 31–34, 38, 39 · P2-9 bonus/performance deferred |

### How each P1 closed

| Item | Sprint |
|---|---|
| P1-1 closed_by on punch_items | Phase 4 |
| P1-2 is_critical_path on punch_items + submittals | Phase 4 |
| P1-3 rfi_manager on rfis | Phase 4 |
| P1-4 submittal_manager_id on submittals | Phase 4 |
| P1-5 actual_start/actual_finish_date on schedule_activities | Phase 21 |
| P1-6 wbs_code on schedule_activities | Phase 21 |
| P1-7 estimated_completion_date on commitments | Phase 3 |
| P1-8 forecast_date + percent_complete on completion_milestones | Phase 21 |
| P1-9 Insurance detail → `insurance_certificates` table | Phase 21 |
| P1-10 system_or_product + manufacturer on warranties | Phase 21 |
| P1-11 change_event_line_items table | Phase 5 |

### How each practical P2 closed

| Item | Sprint |
|---|---|
| P2-1 projects.latitude / longitude | Phase 39 |
| P2-2 observations contributing_behavior / contributing_condition | Phase 39 |
| P2-3 closeout_checklist_items spec_division / spec_section | Phase 39 (display-only; edit drawer deferred) |
| P2-4 O&M manual tracker (`om_manuals` table + CRUD + OmManuals page) | Phase 39 |
| P2-5 companies.mobile_phone / website | Phase 39 |
| P2-6 schedule start_variance_days / finish_variance_days | Phase 38 |
| P2-7 schedule free_float_days | Phase 38 |
| P2-8 generic notification/alert infrastructure | Phases 31–34 |

### What remains

- **P2-9 Bonus / performance system** — **deferred**, not open. Scope requires
  a product design pass before any engineering work. See `PROGRAM_STATE.md`
  "Deferred (intentionally)" section.

Everything else in this backlog is a closed work log, not active todo.
