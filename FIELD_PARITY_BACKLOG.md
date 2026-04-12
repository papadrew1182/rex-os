# Rex OS Field Parity Backlog

> Audit Date: 2026-04-11
> Derived from: FIELD_PARITY_MATRIX.md, FIELD_DECISIONS.md, SCREEN_TO_DATA_MAP.md

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

### P2 Items: still open
- P2-1 latitude/longitude on projects (not yet needed)
- P2-2 contributing_behavior/condition on observations (root cause analysis)
- P2-3 spec_division/section on closeout_checklist_items
- P2-4 O&M Manual Tracker table
- P2-5 mobile_phone/website on companies
- P2-6 start_variance/finish_variance separation (currently single variance_days)
- P2-7 free_float on schedule_activities (currently single float_days)
- P2-8 Notification/alert infrastructure (warranty_alerts exists; general alerts deferred)
- P2-9 Bonus/performance system (phase 2+ design needed)

### Intentionally excluded (Procore mirror baggage)
- procore_id, synced_at, sync_source, is_deleted, deleted_at on every table
- Denormalized *_name mirror fields where FK joins exist
- Procore internal status/type/reason mapping metadata
- Procore datagrid_uuid / datagrid_created_at fields

### Sprint progress summary
- **25 phases completed** (1 audit + 24 build phases)
- **3 migrations applied** (001 base + 002 phase 4-5 batch + 003 phase 21 batch)
- **All P0 + P1 audited gaps closed**
- **No mock data anywhere** — every screen reads/writes real backend

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

## Backlog Summary

| Priority | Count | Schema Columns | New Tables | Effort |
|---|---|---|---|---|
| P0 | 0 | 0 | 0 | None |
| P1 | 11 | ~18 columns | 1 (change_event_line_items) | Small-medium |
| P2 | 9 | ~12 columns | 1 (om_manuals) + design work | Medium-large |

### Recommended Execution Order for P1

1. **P1-1 + P1-2**: closed_by + is_critical_path (punch/submittals) - enables Punch List and Submittal screens
2. **P1-3 + P1-4**: rfi_manager + submittal_manager - enables RFI and Submittal management
3. **P1-5 + P1-6**: actual dates + WBS - enriches Schedule Health
4. **P1-7**: estimated_completion_date on commitments - enables Commitment screen
5. **P1-8**: forecast_date + percent_complete on milestones - enriches milestone tracking
6. **P1-9**: insurance detail - enables vendor compliance
7. **P1-10**: warranty system/manufacturer - enriches warranty management
8. **P1-11**: CE line items - enables full Change Order workflow

All P1 items can be done as a single migration batch or incrementally per screen build.
