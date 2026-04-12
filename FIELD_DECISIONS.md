# Rex OS Field Decisions

> Audit Date: 2026-04-11
> Companion to: FIELD_PARITY_MATRIX.md

---

## 1. Fields to Preserve As-Is

These Rex OS fields have exact or near-exact parity with Rex Procore and should remain unchanged.

### Foundation
| Field | Table | Why Keep |
|---|---|---|
| projects.name | rex.projects | Core identity field, same semantic as Procore project_name |
| projects.project_number | rex.projects | Universal reference ID, matches Procore exactly |
| projects.status | rex.projects | Lifecycle state; Rex OS adds useful states (pre_construction, completed) |
| projects.start_date / end_date | rex.projects | Core schedule fields |
| companies.name | rex.companies | Universal vendor/company name |
| companies.license_number | rex.companies | Regulatory compliance, exact match |
| companies.insurance_expiry | rex.companies | Critical compliance tracking |
| companies.insurance_carrier | rex.companies | Insurance source tracking |
| companies.bonding_capacity | rex.companies | Financial qualification |
| people.first_name / last_name / email / phone | rex.people | Core contact info |
| user_accounts.email / password_hash | rex.user_accounts | Auth essentials |

### Schedule
| Field | Table | Why Keep |
|---|---|---|
| schedule_activities.name / start_date / end_date | rex.schedule_activities | Core activity data |
| schedule_activities.percent_complete | rex.schedule_activities | Progress tracking |
| schedule_activities.is_critical | rex.schedule_activities | Critical path identification |
| schedule_activities.baseline_start / baseline_end | rex.schedule_activities | Baseline comparison |
| schedule_activities.variance_days / float_days | rex.schedule_activities | Schedule health metrics |
| activity_links.link_type / lag_days | rex.activity_links | Dependency logic |

### Field Ops
| Field | Table | Why Keep |
|---|---|---|
| daily_logs.log_date / status | rex.daily_logs | Core daily log identity |
| punch_items.title / status / priority / due_date | rex.punch_items | Core punch tracking |
| punch_items.days_open | rex.punch_items | Aging metric |
| inspections.title / status / scheduled_date | rex.inspections | Core inspection tracking |
| rfis.subject / status / question / answer | rex.rfis | Core RFI workflow |
| rfis.days_open / due_date | rex.rfis | Aging and urgency |
| submittals.title / status / submittal_type | rex.submittals | Core submittal tracking |
| tasks.title / status / priority / due_date | rex.tasks | Core task management |

### Financials
| Field | Table | Why Keep |
|---|---|---|
| budget_line_items.original_budget / revised_budget / projected_cost / over_under | rex.budget_line_items | Core budget tracking |
| commitments.title / status / original_value / revised_value | rex.commitments | Core commitment data |
| change_events.title / status / scope / change_reason | rex.change_events | Core CE workflow |
| prime_contracts.title / status / original_value | rex.prime_contracts | Core contract tracking |

### Closeout
| Field | Table | Why Keep |
|---|---|---|
| closeout_checklist_items.name / status / category | rex.closeout_checklist_items | Core checklist tracking |
| warranties.scope_description / warranty_type / duration_months | rex.warranties | Core warranty data |
| completion_milestones.milestone_name / milestone_type / status | rex.completion_milestones | Core milestone tracking |
| completion_milestones.is_evidence_complete / evidence_requirements | rex.completion_milestones | Evidence workflow (Rex OS advantage) |

---

## 2. Fields to Rename / Remap

These fields exist in both systems but need name alignment for migration clarity.

| Rex Procore Name | Rex OS Name | Decision | Rationale |
|---|---|---|---|
| project_name | name | **Keep Rex OS** | Shorter, cleaner column name |
| completion_date | end_date | **Keep Rex OS** | Consistent with start_date |
| state_code | state | **Keep Rex OS** | Simpler |
| zip_code | zip | **Keep Rex OS** | Simpler |
| vendor_name / company_name | companies.name | **Keep Rex OS** | Normalized in companies table |
| finish_date (on tasks) | end_date | **Keep Rex OS** | Consistent naming |
| percentage_complete | percent_complete | **Keep Rex OS** | Shorter |
| critical_path (boolean) | is_critical (boolean) | **Keep Rex OS** | follows `is_` prefix convention |
| headcount | worker_count | **Keep Rex OS** | More descriptive |
| deficiency_type | punch_type | **Keep Rex OS** | Cleaner name |
| closed_at (timestamps) | closed_date (dates) | **Keep Rex OS** | Date-only is sufficient for most use cases |
| ball_in_court (text name) | ball_in_court (FK uuid) | **Keep Rex OS** | FK is normalized, text is denormalized |
| assignee/assignee_name/assignee_id (mixed) | assigned_to (FK) | **Keep Rex OS** | Single normalized FK |
| task_name | name (on schedule_activities) | **Keep Rex OS** | Concise |
| grand_total / contract_value / original_value | original_value | **Keep Rex OS** | Single canonical name |
| retainage_held | retention_held | **Keep Rex OS** | More precise term |
| balance_to_finish | remaining_to_invoice | **Keep Rex OS** | More specific |
| slippage_days (generated) | variance_days | **Keep Rex OS** | Consistent with schedule_activities |
| budget_modifications | approved_changes | **Keep Rex OS** | Describes the source, not the action |
| cost_code + description (text fields) | cost_code_id (FK) | **Keep Rex OS** | Normalized via FK |

---

## 3. Fields to Compute Rather Than Store

These fields are stored in Rex Procore but should be computed on-read in Rex OS.

| Field | Stored In Procore | Rex OS Approach | Rationale |
|---|---|---|---|
| full_name | procore.users.full_name | `first_name || ' ' || last_name` | Computed from components |
| initials | procore.users.initials | `LEFT(first_name,1) || LEFT(last_name,1)` | Trivial derivation |
| manpower_count | daily_logs.manpower_count | `SUM(manpower_entries.worker_count)` | Aggregate from child rows |
| total_hours | daily_logs.total_hours | `SUM(manpower_entries.hours)` | Aggregate from child rows |
| delay_count | daily_logs.delay_count | Count from schedule_constraints | Aggregate |
| passed_count/failed_count/na_count/total_items | inspections.* | `COUNT/SUM from inspection_items` | Aggregate from child rows |
| pass_rate | inspections.pass_rate | `passed_count / total_items * 100` | Derived from aggregates |
| deficiency_count | inspections.deficiency_count | `COUNT WHERE result='fail'` | Filtered aggregate |
| days_in_review | submittals.days_in_review | `CURRENT_DATE - submitted_date` | Date math |
| forecast_to_complete | budgets.forecast_to_complete | `projected_cost - committed_costs - direct_costs` | Arithmetic |
| total_billings | budgets.total_billings | `SUM(payment_applications.total_completed)` | Aggregate |
| revision_count | drawings.revision_count | `COUNT(drawing_revisions)` | Aggregate |
| attachments_count | observations.attachments_count | `COUNT(attachments WHERE source_type/id match)` | Aggregate |
| has_subtasks | tasks.has_subtasks | `EXISTS(... WHERE parent_id=...)` | Existence check |
| full_outline_path | tasks.full_outline_path | Recursive CTE on parent_id chain | Computed hierarchy |
| is_active (on projects) | projects.is_active | `status != 'archived'` | Derived from status |
| contributing fields (denormalized company_name on punch) | Various _company_name fields | JOIN to companies via FK | Normalized query |
| balance_to_finish (on commitments) | commitments.balance_to_finish | `revised_value - invoiced_to_date` | Arithmetic |
| pending_changes_amount | commitments.pending_changes_amount | `SUM(PCOs WHERE status='pending')` | Aggregate |

---

## 4. Fields to Deprecate

These Rex Procore fields should NOT be brought into Rex OS.

### Procore Sync Infrastructure (entire category)
| Field Pattern | Why Deprecate |
|---|---|
| procore_id on every table | Rex OS is source of truth, not a Procore mirror. Use connector_mappings for any external ID linkage. |
| synced_at / sync_source on every table | Same: Rex OS is primary, not a sync target |
| is_deleted / deleted_at on every table | Rex OS uses proper deletion or status fields, not soft-delete tombstones |
| sync_log / webhook_events tables | Procore webhook infrastructure not needed |
| datagrid_uuid / datagrid_created_at | Procore DataGrid internal fields |

### Denormalized Name Fields
| Field | Why Deprecate |
|---|---|
| project_name on every table | Redundant: JOIN to projects.name via project_id FK |
| assignee_name / assignee / ball_in_court (text) | Redundant: JOIN to people via FK |
| vendor_name / vendor (text) on commitments | Redundant: JOIN to companies via FK |
| created_by_name / inspector_name (text) | Redundant: JOIN to people via FK |
| company_name (text on various tables) | Redundant: JOIN to companies via FK |
| punch_item_manager_company_name | Redundant: 3-level JOIN |
| closed_by_company_name | Redundant: 3-level JOIN |
| final_approver_company_name | Redundant: 3-level JOIN |

### Legacy/Redundant Data Fields
| Field | Why Deprecate |
|---|---|
| rfis.title (separate from subject) | Redundant with rfis.subject |
| rfis.number (numeric) alongside rfi_number (text) | Use rfi_number only |
| commitments.signed_contract_amount | Redundant with original_value |
| commitments.contract_amount | Redundant with original_value |
| prime_contracts.contract_amount | Redundant with original_value |
| tasks.short_task_name | Redundant with task_name |
| change_events.status_id / status_mapped_to_status / all change_event_status_* | Procore internal status mapping |
| change_events.change_type_id / change_type_abbreviation | Procore type metadata |
| change_events.change_reason_id / change_reason_company_id | Procore reason metadata |
| change_events.source_of_revenue_rom | Procore-specific field |
| change_events.comments_enabled / has_edited_markups / deletable / in_recycle_bin | Procore UI state |
| change_events.currency_iso_code | Always USD for Rex |
| tasks.color | Procore UI cosmetic |
| tasks.created_by_login / updated_by_login (JSONB) | Procore auth metadata |
| drawings.floorplan / is_obsolete | Procore-specific flags |
| users.avatar_url | Not needed for Rex OS MVP |
| users.welcome_email_sent_at / last_activated_at | Procore lifecycle |
| users.erp_integrated_accountant | Procore ERP flag |
| users.permission_template_* (all 10 fields) | Replaced by Rex OS role_templates |
| users.origin_data / origin_id | Procore provenance |
| vendors.origin_code / origin_data / origin_id | Procore provenance |
| vendors.business_register / business_register_id / etc | Procore vendor validation |

### AI/Intelligence Features (defer, not deprecate)
| Table/Feature | Status |
|---|---|
| risk_predictions | Phase 2+ (Rex OS will build its own) |
| photo_analysis | Phase 2+ |
| voice_transcriptions | Phase 2+ |
| safety_scans | Phase 2+ |
| rfi_drafts | Phase 2+ |
| delay_claims engine | Phase 2+ |
| BIM integration | Phase 2+ |
| cost_benchmarks | Phase 2+ |

### Bonus System (defer, not deprecate)
| Table/Feature | Status |
|---|---|
| quarterly_scorecards | Phase 2+ (requires significant design work for Rex OS) |
| milestone_bonus / buyout / EBITDA | Phase 2+ |
| achievements / leaderboard_metrics | Phase 2+ |

---

## 5. Fields That Rex OS Added Intentionally and Should Stay

These fields are Rex OS improvements over Rex Procore.

### Foundation
| Field | Table | Why It Should Stay |
|---|---|---|
| project_type (richer enum) | rex.projects | More project type options for diverse portfolios |
| status = pre_construction / completed | rex.projects | Better lifecycle tracking |
| contract_value | rex.projects | Project-level financial summary |
| square_footage | rex.projects | Portfolio comparison metric |
| description | rex.projects | Project description |
| companies.company_type (7 values) | rex.companies | Proper vendor classification |
| companies.status (4 values) | rex.companies | Better than boolean is_active |
| companies.notes | rex.companies | Free-text vendor notes |
| people.role_type (internal/external) | rex.people | Employee vs contractor |
| user_accounts.mfa_secret | rex.user_accounts | Security improvement |
| sessions (full table) | rex.sessions | Proper session management vs text PK |
| role_templates (full table) | rex.role_templates | Granular RBAC with visible_tools/panels |
| role_template_overrides | rex.role_template_overrides | Per-member permission tuning |
| connector_mappings | rex.connector_mappings | Generic external system mapping |
| project_members.is_primary | rex.project_members | Primary role flag per project |

### Schedule
| Field | Table | Why It Should Stay |
|---|---|---|
| schedules (container entity) | rex.schedules | Proper schedule management (Procore has none) |
| schedule_constraints (full table) | rex.schedule_constraints | Explicit constraint tracking with severity |
| schedule_snapshots | rex.schedule_snapshots | Per-activity historical tracking |
| schedule_activities.cost_code_id | rex.schedule_activities | Cost-schedule integration |
| schedule_activities.location | rex.schedule_activities | Location tracking |
| activity_links.schedule_id | rex.activity_links | Scoped to schedule |

### Field Ops
| Field | Table | Why It Should Stay |
|---|---|---|
| daily_logs.is_weather_delay | rex.daily_logs | Explicit delay flag |
| daily_logs.safety_notes / visitor_notes / delay_notes | rex.daily_logs | Structured log sections |
| daily_logs.approved_by / approved_at | rex.daily_logs | Approval workflow |
| punch_items.punch_number | rex.punch_items | Sequential numbering |
| punch_items.final_approver_id | rex.punch_items | Approval workflow |
| punch_items.drawing_id / cost_code_id | rex.punch_items | Cross-domain links |
| inspection_items (full table) | rex.inspection_items | Individual item tracking (Procore uses flat counts) |
| observations.corrective_action | rex.observations | Action tracking |
| safety_incidents (full table, 20 fields) | rex.safety_incidents | Much richer than Procore's 12-field version |
| meeting_action_items (full table) | rex.meeting_action_items | Normalized meeting actions |
| photos.storage_key / thumbnail_url | rex.photos | Cloud storage integration |

### Financials
| Field | Table | Why It Should Stay |
|---|---|---|
| budget_line_items.pending_changes | rex.budget_line_items | Pending CO visibility |
| budget_snapshots | rex.budget_snapshots | Historical budget tracking |
| commitment_line_items | rex.commitment_line_items | Detailed commitment breakdown |
| commitments.retention_rate | rex.commitments | Configurable retention |
| prime_contracts.retention_rate / billed_to_date | rex.prime_contracts | Billing tracking |
| pco_cco_links | rex.pco_cco_links | Many-to-many PCO/CCO linkage |
| billing_periods | rex.billing_periods | Billing period management |
| direct_costs | rex.direct_costs | Direct cost tracking |
| lien_waivers (full table) | rex.lien_waivers | Richer waiver tracking |

### Document Management
| Field | Table | Why It Should Stay |
|---|---|---|
| drawing_areas / drawing_revisions | rex.drawing_areas / drawing_revisions | Proper drawing revision management |
| submittal_packages | rex.submittal_packages | Package grouping |
| submittals.schedule_activity_id / required_on_site | rex.submittals | Schedule-submittal integration |
| correspondence | rex.correspondence | Formal project correspondence |
| attachments (normalized polymorphic table) | rex.attachments | Clean architecture vs JSONB blobs |

### Closeout & Warranty
| Field | Table | Why It Should Stay |
|---|---|---|
| closeout_templates / closeout_template_items | rex.closeout_templates | Template-based checklist generation |
| closeout_checklists (container with SC date) | rex.closeout_checklists | Checklist-level entity |
| warranties.commitment_id / cost_code_id | rex.warranties | Financial linkage |
| warranties.is_letter_received / is_om_received | rex.warranties | Explicit document tracking |
| warranty_claims (full table) | rex.warranty_claims | Formal claims management |
| warranty_alerts (full table) | rex.warranty_alerts | Proactive alert management |
| completion_milestones.is_evidence_complete / evidence_requirements | rex.completion_milestones | Evidence-based milestone certification |

---

## 6. Missing Fields That Should Be Added to Rex OS

### P0 - Blocks Current Product Slice
| Field | Target Table | Source | Why Needed |
|---|---|---|---|
| (none identified) | -- | -- | Current closeout slice fields are complete |

### P1 - Important for Next Slices
| Field | Target Table | Source | Why Needed |
|---|---|---|---|
| is_critical_path (boolean) | punch_items, submittals | Procore | Critical path impact tracking |
| actual_start_date / actual_finish_date | schedule_activities | Procore tasks | Actual vs planned separation |
| work_breakdown_structure (text) | schedule_activities | Procore tasks | WBS code for schedule analysis |
| closed_by (uuid FK) | punch_items | Procore | Punch closure accountability |
| rfi_manager (uuid FK) | rfis | Procore | RFI workflow management |
| submittal_manager_id (uuid FK) | submittals | Procore | Submittal workflow management |
| estimated_completion_date | commitments | Procore | Commitment timeline |
| forecast_date | completion_milestones | Procore milestone_tracking | Forecast vs scheduled date |
| percent_complete | completion_milestones | Procore milestone_tracking | Milestone progress |
| system_or_product (text) | warranties | Procore warranty_items | System identification |
| manufacturer (text) | warranties | Procore warranty_items | Manufacturer tracking |
| Insurance detail fields (gl/wc/auto expiry + limits) | companies OR new insurance table | Procore vendors + insurances | Insurance compliance |

### P2 - Lower Priority
| Field | Target Table | Source | Why Needed |
|---|---|---|---|
| latitude / longitude | projects | Procore | Map-based portfolio views |
| contributing_behavior / contributing_condition | observations | Procore | Root cause analysis |
| spec_division / spec_section | closeout_checklist_items | Procore closeout_checklist | Spec-based closeout tracking |
| O&M manual tracking fields | New table or warranties extension | Procore om_manual_tracker | Document completeness |

---

## POST-SPRINT UPDATE — 2026-04-12 (Phase 25)

The following fields have moved from "P1 Missing" to "Present in Rex OS" since the original audit:

### Schedule
- `schedule_activities.actual_start_date` — for actual vs planned variance
- `schedule_activities.actual_finish_date` — for actual vs planned variance
- `schedule_activities.wbs_code` — for WBS hierarchy filtering and reporting
- Variance computation now uses actuals when both are present, otherwise falls back to stored variance_days

### Completion Milestones
- `completion_milestones.forecast_date` — forecast vs scheduled tracking
- `completion_milestones.percent_complete` — milestone progress (0-100)
- New milestone health derivation: ON TRACK / SLIPPING / AT RISK / OVERDUE / ACHIEVED

### Warranties
- `warranties.system_or_product` — what system/product is covered
- `warranties.manufacturer` — manufacturer name

### Insurance Compliance (NEW DOMAIN)
- New normalized table `rex.insurance_certificates` with full CRUD
- Fields: company_id, policy_type (gl/wc/auto/umbrella/other), carrier, policy_number, effective_date, expiry_date, limit_amount, status, attachment_id, notes
- Status auto-computes from expiry_date via `/api/insurance-certificates/refresh-status` endpoint
- One company → many certificates (proper normalization vs flat company columns)

### Field Ops (closed in earlier sprints)
- `rfis.rfi_manager`, `punch_items.closed_by`, `punch_items.is_critical_path`, `submittals.submittal_manager_id`, `submittals.is_critical_path`, `commitments.estimated_completion_date`, `change_event_line_items` table — all closed in phases 3-5

### Still intentionally excluded (Procore baggage)
- `procore_id` columns on every table — Rex OS uses `connector_mappings` for external linkage
- `synced_at` / `sync_source` / `is_deleted` / `deleted_at` columns — Rex OS is the source of truth
- Denormalized `*_name` mirror columns — Rex OS uses FK joins
- Procore internal status_id / change_type_id / change_reason_id metadata

---

## POST-SPRINT UPDATE — 2026-04-12 (Phases 31-35)

### New tables added (operational, not domain parity)

- `rex.job_runs` — background job execution history
- `rex.notifications` — generic in-app notification inbox

### Background job runner

- apscheduler-based, env-gated via `REX_ENABLE_SCHEDULER`
- Postgres advisory locks prevent duplicate runs across instances
- DB-backed run history for admin visibility
- 5 jobs registered:
  - `warranty_refresh` (daily 06:00 UTC)
  - `insurance_refresh` (daily 06:15 UTC)
  - `schedule_snapshot` (daily 06:30 UTC)
  - `aging_alerts` (daily 06:45 UTC)
  - `session_purge` (every 2 hours)

### Notification system

- Dedupe via partial unique index on `(user_account_id, dedupe_key)` WHERE active
- `upsert_notification` updates existing unresolved alerts in place
- `resolve_notifications_by_dedupe_prefix` clears stale alerts when conditions clear
- Project-bound notifications fan out to project members + admin/VPs
- Insurance notifications fan out to admin/VPs only (insurance is global)
- Action paths deep-link to relevant frontend pages

### Email transport

- 3 implementations: noop (default), log, smtp
- Selected via `REX_EMAIL_TRANSPORT` env var
- SMTP absence never crashes the app — in-app inbox is the source of truth

### Why these decisions

- Jobs+notifications are infrastructure, not domain parity. Existing
  domain-specific tables like `warranty_alerts` are kept; notifications
  are the delivery/inbox layer.
- No new external queue/broker — single-instance apscheduler with DB
  advisory locks for multi-instance safety.
- Notifications are dedupe-keyed to prevent spam on repeat job runs.
- Email is enhancement, not requirement.

### Closed P2 items
- P2-8 generic notification/alert infrastructure ✅
