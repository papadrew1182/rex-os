# Rex OS Screen-to-Data Map

> Audit Date: 2026-04-11
> Sources: Rex Procore live app, Rex OS frontend, Rex OS backend models

---

## POST-SPRINT UPDATE — 2026-04-12 (Phase 34)

### New screens shipped (Phase 34)

| Screen | Route | Data sources | Audience |
|---|---|---|---|
| Notifications | /notifications | /api/notifications/, unread-count, read, dismiss | All users |
| Operations | /admin/jobs | /api/admin/jobs, /api/admin/job-runs, /api/admin/jobs/:key/run | Admin/VP only |

### Topbar additions

- Notification bell with red unread badge (polls every 60s)
- Click opens slide-in drawer with most-recent 20 notifications
- Drawer supports per-item mark-read, dismiss, deep-link via action_path
- "View all" button navigates to full Notifications page

---

## POST-SPRINT UPDATE — 2026-04-12 (Phases 22-25)

### New screens shipped

| Screen | Route | Data sources | Status |
|---|---|---|---|
| Schedule Health (tabbed) | /schedule | `/projects/:id/schedule-health-summary`, `/schedules`, `/schedule-activities`, `/schedule-constraints` | Health + Activities + Lookahead + Critical Path tabs |
| Warranties | /warranties | `/warranties`, `/warranty-claims`, `/warranty-alerts`, `/companies`, `/cost-codes` | Full CRUD + system_or_product + manufacturer |
| Insurance Certificates | /insurance | `/insurance-certificates`, `/insurance-certificates/summary`, `/companies` | Full CRUD + auto-status refresh |

### Updated screens

| Screen | What's new |
|---|---|
| Milestones | forecast_date, percent_complete, milestone health derivation (ON TRACK / SLIPPING / AT RISK / OVERDUE / ACHIEVED), progress visualization, edit form |
| Project Readiness | Milestones card now shows on-track/at-risk counts and progress |

### All screens now operational (read + write)
With phases 1-25 complete, every screen in the navigation supports real CRUD against real backend routes with permission-aware UX. The only intentionally read-only screen is **Photos** (file upload requires multipart + storage backend wiring, deferred).

---

## Currently Built Screens

### 1. Portfolio (Closeout Readiness)

**Screen:** `frontend/src/pages/Portfolio.jsx`
**Route:** `/#/`
**Purpose:** Portfolio-wide closeout readiness dashboard

| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Notes |
|---|---|---|---|---|
| Project name | projects.name | Yes | Yes | |
| Project number | projects.project_number | Yes | Yes | |
| Project status (pass/warning/fail/not_started) | Computed from checklists+milestones | Yes | Yes | Derived via API |
| Checklist % complete (best) | closeout_checklists.percent_complete | Yes | Yes | |
| Milestones achieved/total | completion_milestones (aggregate) | Yes | Yes | |
| Holdback gate status | Gate evaluation endpoint | Yes | Yes | |
| Open issues count | API aggregation | Yes | Yes | |
| Search filter | Client-side | Yes | Yes | |
| Status filter | Client-side | Yes | Yes | |
| "Hide test" filter | Client-side pattern match | Yes | Yes | |

**Verdict: COMPLETE for current slice.** No blockers.

---

### 2. Project Readiness

**Screen:** `frontend/src/pages/ProjectReadiness.jsx`
**Route:** `/#/project/:id`
**Purpose:** Single-project closeout readiness summary

| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Notes |
|---|---|---|---|---|
| Project name + overall status | projects + computed | Yes | Yes | |
| Checklist count | closeout_checklists | Yes | Yes | |
| Checklist items completed/total | closeout_checklists.completed_items/total_items | Yes | Yes | |
| Best checklist % | closeout_checklists.percent_complete | Yes | Yes | |
| Milestones total/achieved/evidence/certified | completion_milestones | Yes | Yes | |
| Holdback release status | Gate evaluation | Yes | Yes | |
| Warranties claimed / expiring soon | warranties + warranty_claims | Yes | Yes | |
| Open issues | API endpoint | Yes | Yes | |
| Quick-nav links | Static UI | Yes | Yes | |

**Verdict: COMPLETE for current slice.** No blockers.

---

### 3. Checklists

**Screen:** `frontend/src/pages/Checklists.jsx`
**Route:** `/#/checklists`
**Purpose:** Closeout checklist management with item toggle

| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Notes |
|---|---|---|---|---|
| Checklist list with SC date | closeout_checklists.substantial_completion_date | Yes | Yes | |
| Items completed/total/percent | closeout_checklists aggregate fields | Yes | Yes | |
| Per-item name | closeout_checklist_items.name | Yes | Yes | |
| Per-item status | closeout_checklist_items.status | Yes | Yes | |
| Per-item category | closeout_checklist_items.category | Yes | Yes | |
| Per-item due date | closeout_checklist_items.due_date | Yes | Yes | |
| Item toggle (complete/not) | PATCH endpoint | Yes | Yes | |
| Create from template | closeout_templates + API | Yes | Yes | Admin-only |
| SC date input | closeout_checklists.substantial_completion_date | Yes | Yes | Admin-only |

**Verdict: COMPLETE.** No blockers.

---

### 4. Milestones

**Screen:** `frontend/src/pages/Milestones.jsx`
**Route:** `/#/milestones`
**Purpose:** Milestone evidence tracking and certification

| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Notes |
|---|---|---|---|---|
| Milestone name | completion_milestones.milestone_name | Yes | Yes | |
| Milestone type | completion_milestones.milestone_type | Yes | Yes | |
| Milestone status | completion_milestones.status | Yes | Yes | |
| Evidence checklist | completion_milestones.evidence_requirements | Yes | Yes | JSONB field |
| Evidence complete flag | completion_milestones.is_evidence_complete | Yes | Yes | |
| Mark evidence complete action | API endpoint | Yes | Yes | |
| Certify milestone action | API endpoint | Yes | Yes | Admin-only |
| Gate evaluation | Dedicated gate logic | Yes | Yes | |
| Gate results (per-gate status) | API response | Yes | Yes | |

**Verdict: COMPLETE.** No blockers.

---

### 5. Schedule Health

**Screen:** `frontend/src/pages/ScheduleHealth.jsx`
**Route:** `/#/schedule`
**Purpose:** Schedule health metrics and drift analysis

| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Notes |
|---|---|---|---|---|
| Health status | Computed from activities | Yes | Yes | |
| Schedule count | schedules | Yes | Yes | |
| Activity count | schedule_activities | Yes | Yes | |
| Critical activity count | schedule_activities WHERE is_critical | Yes | Yes | |
| Completed count | schedule_activities WHERE percent_complete=100 | Yes | Yes | |
| Avg variance | AVG(schedule_activities.variance_days) | Yes | Yes | |
| Constraint count | schedule_constraints | Yes | Yes | |
| Constraints by severity | schedule_constraints.severity | Yes | Yes | |
| Per-schedule drift details | schedule_activities per schedule | Yes | Yes | |
| Worst drift activity | MAX(variance_days) | Yes | Yes | |

**Verdict: COMPLETE for current data model.** Missing actual_start/actual_finish separation (P1).

---

### 6. Execution Health

**Screen:** `frontend/src/pages/ExecutionHealth.jsx`
**Route:** `/#/execution`
**Purpose:** Field execution metrics dashboard

| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Notes |
|---|---|---|---|---|
| Daily log count | daily_logs | Yes | Yes | |
| Total workers | SUM(manpower_entries.worker_count) | Yes | Yes | Computed |
| Total hours | SUM(manpower_entries.hours) | Yes | Yes | Computed |
| Avg workers/log | Computed | Yes | Yes | |
| Inspection total | inspections | Yes | Yes | |
| Inspections open | inspections WHERE status not closed | Yes | Yes | |
| Failed inspection items | inspection_items WHERE result='fail' | Yes | Yes | |
| Punch items total/open | punch_items | Yes | Yes | |
| Punch closure rate | Computed | Yes | Yes | |
| Tasks by status | tasks grouped by status | Yes | Yes | |
| Active constraints | schedule_constraints WHERE status='active' | Yes | Yes | |
| Constraints by severity | schedule_constraints.severity | Yes | Yes | |

**Verdict: COMPLETE for current data model.** No blockers.

---

### 7. Attachments

**Screen:** `frontend/src/pages/Attachments.jsx`
**Route:** `/#/attachments`
**Purpose:** File upload and download management

| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Notes |
|---|---|---|---|---|
| Filename | attachments.filename | Yes | Yes | |
| Content type | attachments.content_type | Yes | Yes | |
| Source type | attachments.source_type | Yes | Yes | |
| File size | attachments.file_size | Yes | Yes | |
| Upload date | attachments.created_at | Yes | Yes | |
| Upload action | POST endpoint | Yes | Yes | |
| Download action | GET endpoint | Yes | Yes | |
| Source type selector | Static enum | Yes | Yes | |

**Verdict: COMPLETE.** No blockers.

---

## Upcoming Screen Families

### 8. Financials Pages (NOT YET BUILT)

#### 8a. Budget Overview
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| Cost code + description | cost_codes.code + name | Yes | Yes | No |
| Original budget | budget_line_items.original_budget | Yes | Yes | No |
| Approved changes | budget_line_items.approved_changes | Yes | Yes | No |
| Revised budget | budget_line_items.revised_budget | Yes | Yes | No |
| Committed costs | budget_line_items.committed_costs | Yes | Yes | No |
| Direct costs | budget_line_items.direct_costs | Yes | Yes | No |
| Pending changes | budget_line_items.pending_changes | Yes | Yes | No |
| Projected cost | budget_line_items.projected_cost | Yes | Yes | No |
| Over/under | budget_line_items.over_under | Yes | Yes | No |
| Forecast to complete | Computed | No (computed) | Yes | No |
| Total billings | Computed from pay_apps | No (computed) | Yes | No |
| Portfolio-level KPIs | Aggregation | Computable | Yes | No |

**Verdict: DATA MODEL READY.** Can build this screen now.

#### 8b. Commitment Management
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| Commitment number/title/status | commitments | Yes | Yes | No |
| Vendor name | companies via vendor_id FK | Yes | Yes | No |
| Contract type | commitments.contract_type | Yes | Yes | No |
| Original/approved COs/revised value | commitments | Yes | Yes | No |
| Invoiced to date | commitments.invoiced_to_date | Yes | Yes | No |
| Retention rate/held | commitments | Yes | Yes | No |
| Line items | commitment_line_items | Yes | Yes | No |
| Estimated completion date | -- | No | -- | P1 gap |
| Scope of work | commitments.scope_of_work | Yes | Yes | No |

**Verdict: DATA MODEL MOSTLY READY.** Minor gap: missing estimated_completion_date.

#### 8c. Change Order Workflow
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| Change events with status/scope/reason | change_events | Yes | Yes | No |
| PCOs per CE | potential_change_orders | Yes | Yes | No |
| CCOs per commitment | commitment_change_orders | Yes | Yes | No |
| PCO-to-CCO links | pco_cco_links | Yes | Yes | No |
| CE line items / RFQ data | -- | No | -- | P1 gap |

**Verdict: DATA MODEL MOSTLY READY.** Gap: CE line items not stored (were JSONB in Procore).

#### 8d. Pay Applications
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| Pay app number/status | payment_applications | Yes | Yes | No |
| Period start/end | payment_applications | Yes | Yes | No |
| This period amount | payment_applications.this_period_amount | Yes | Yes | No |
| Total completed | payment_applications.total_completed | Yes | Yes | No |
| Retention held/released | payment_applications | Yes | Yes | No |
| Net payment due | payment_applications.net_payment_due | Yes | Yes | No |
| Billing period | billing_periods | Yes | Yes | No |
| Lien waivers | lien_waivers | Yes | Yes | No |

**Verdict: DATA MODEL READY.** Can build this screen now.

---

### 9. Field Ops Pages (NOT YET BUILT)

#### 9a. RFI Management
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| RFI number/subject/status | rfis | Yes | Yes | No |
| Question/answer | rfis | Yes | Yes | No |
| Ball in court | rfis.ball_in_court FK | Yes | Yes | No |
| Assigned to | rfis.assigned_to FK | Yes | Yes | No |
| Days open | rfis.days_open | Yes | Yes | No |
| Due date | rfis.due_date | Yes | Yes | No |
| Cost/schedule impact | rfis | Yes | Yes | No |
| Drawing reference | rfis.drawing_id FK | Yes | Yes | No |
| RFI manager | -- | No | -- | P1 gap |

**Verdict: DATA MODEL MOSTLY READY.** Minor gap: rfi_manager field.

#### 9b. Punch List
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| All punch fields | punch_items | Yes | Yes | No |
| Assignee name | people via assigned_to FK | Yes | Yes | No |
| Company name | companies via assigned_company_id FK | Yes | Yes | No |
| is_critical_path | -- | No | -- | P1 gap |
| closed_by | -- | No | -- | P1 gap |

**Verdict: DATA MODEL MOSTLY READY.** Gaps are P1 not P0.

#### 9c. Daily Log Management
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| All daily log fields | daily_logs | Yes | Yes | No |
| Manpower entries | manpower_entries | Yes | Yes | No |
| Approval workflow | daily_logs.approved_by/at | Yes | Yes | No |

**Verdict: DATA MODEL READY.** Can build now.

#### 9d. Inspection Management
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| Inspection list with status | inspections | Yes | Yes | No |
| Inspection items with results | inspection_items | Yes | Yes | No |
| Auto-punch from failed items | inspection_items.punch_item_id FK | Yes | Yes | No |

**Verdict: DATA MODEL READY.** Can build now.

#### 9e. Submittal Management
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| All submittal fields | submittals | Yes | Yes | No |
| Package grouping | submittal_packages | Yes | Yes | No |
| Submittal manager | -- | No | -- | P1 gap |
| is_critical_path | -- | No | -- | P1 gap |

**Verdict: DATA MODEL MOSTLY READY.** Gaps are P1.

#### 9f. Task/Action Item Management
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| All task fields | tasks | Yes | Yes | No |
| Company assignment | tasks.assigned_company_id | Yes | Yes | No |

**Verdict: DATA MODEL READY.** Can build now.

#### 9g. Safety Incident Reporting
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| All incident fields | safety_incidents | Yes | Yes | No |
| OSHA recordable flag | safety_incidents.is_osha_recordable | Yes | Yes | No |

**Verdict: DATA MODEL READY.** Can build now. Rex OS model is richer than Procore's.

---

### 10. Document Management Pages (NOT YET BUILT)

#### 10a. Drawing Management
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| Drawing number/title/discipline | drawings | Yes | Yes | No |
| Drawing areas | drawing_areas | Yes | Yes | No |
| Revision history | drawing_revisions | Yes | Yes | No |
| Current revision | drawings.current_revision | Yes | Yes | No |
| Image URL | drawings.image_url | Yes | Yes | No |

**Verdict: DATA MODEL READY.** Can build now.

#### 10b. Specification Management
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| Section number/title/division | specifications | Yes | Yes | No |
| Revision | specifications.current_revision | Yes | Yes | No |
| Attachment | specifications.attachment_id FK | Yes | Yes | No |

**Verdict: DATA MODEL READY.** Can build now.

#### 10c. Correspondence Log
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| All correspondence fields | correspondence | Yes | Yes | No |
| From/to person | FKs to people | Yes | Yes | No |

**Verdict: DATA MODEL READY.** Can build now.

---

### 11. Additional Upcoming Screens

#### 11a. Photo Gallery
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| Photo list with thumbnails | photos + photo_albums | Yes | Yes | No |
| Album grouping | photo_albums | Yes | Yes | No |
| Location/description/tags | photos | Yes | Yes | No |

**Verdict: DATA MODEL READY.** Can build now.

#### 11b. Meeting Management
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| Meeting list | meetings | Yes | Yes | No |
| Action items | meeting_action_items | Yes | Yes | No |
| Task linkage | meeting_action_items.task_id | Yes | Yes | No |

**Verdict: DATA MODEL READY.** Can build now.

#### 11c. Observation/Safety Dashboard
| Required Field | Source Table(s) | Rex OS Has It? | Complete? | Blocker? |
|---|---|---|---|---|
| Observations | observations | Yes | Yes | No |
| Safety incidents | safety_incidents | Yes | Yes | No |

**Verdict: DATA MODEL READY.** Can build now.

---

## Screen Readiness Summary

| Screen Family | Data Model Status | Can Build Now? | Gaps |
|---|---|---|---|
| Portfolio | Complete | Yes (built) | None |
| Project Readiness | Complete | Yes (built) | None |
| Checklists | Complete | Yes (built) | None |
| Milestones | Complete | Yes (built) | None |
| Schedule Health | Complete | Yes (built) | actual_start/finish (P1) |
| Execution Health | Complete | Yes (built) | None |
| Attachments | Complete | Yes (built) | None |
| **Budget Overview** | **Complete** | **Yes** | **None** |
| **Commitment Mgmt** | **Mostly complete** | **Yes** | **estimated_completion_date (P1)** |
| **Change Orders** | **Mostly complete** | **Yes** | **CE line items (P1)** |
| **Pay Applications** | **Complete** | **Yes** | **None** |
| **RFI Management** | **Mostly complete** | **Yes** | **rfi_manager (P1)** |
| **Punch List** | **Mostly complete** | **Yes** | **is_critical_path, closed_by (P1)** |
| **Daily Log** | **Complete** | **Yes** | **None** |
| **Inspections** | **Complete** | **Yes** | **None** |
| **Submittals** | **Mostly complete** | **Yes** | **submittal_manager, is_critical_path (P1)** |
| **Tasks** | **Complete** | **Yes** | **None** |
| **Safety Incidents** | **Complete** | **Yes** | **None** |
| **Drawings** | **Complete** | **Yes** | **None** |
| **Specifications** | **Complete** | **Yes** | **None** |
| **Photos** | **Complete** | **Yes** | **None** |
| **Meetings** | **Complete** | **Yes** | **None** |
| **Observations** | **Complete** | **Yes** | **None** |
| **Correspondence** | **Complete** | **Yes** | **None** |

**Key Finding:** The Rex OS data model is remarkably complete. Of 24 screen families assessed, 19 have complete data models and 5 have minor P1 gaps that don't block initial screen builds. No P0 data gaps were found for any screen.
