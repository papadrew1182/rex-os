# Rex OS Field Parity Matrix

> Audit Date: 2026-04-11
> Sources: Rex Procore repo (C:\Users\rober\rex-procore), live app (railway), Rex OS repo (C:\Users\rober\rex-os)

> **Updated 2026-04-12 (Phase 25)** — All P0 items remained at zero. The following P1 items have been **CLOSED** since the original audit:
> - ✅ punch_items.closed_by (phase 4)
> - ✅ punch_items.is_critical_path (phase 4)
> - ✅ submittals.is_critical_path (phase 4)
> - ✅ submittals.submittal_manager_id (phase 4)
> - ✅ rfis.rfi_manager (phase 4)
> - ✅ commitments.estimated_completion_date (phase 3)
> - ✅ change_event_line_items table (phase 5)
> - ✅ schedule_activities.actual_start_date / actual_finish_date / wbs_code (phase 21)
> - ✅ completion_milestones.forecast_date / percent_complete (phase 21)
> - ✅ warranties.system_or_product / manufacturer (phase 21)
> - ✅ insurance_certificates table (phase 21 — implemented as normalized table option)
> 
> **Remaining P1 items**: none currently identified.
> **Remaining P2 items**: see FIELD_PARITY_BACKLOG.md for the current list.

---

## 1. Foundation

### 1.1 Projects

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| project_name | DB/UI | Display name | name | renamed | Trivial remap | P0 |
| project_number | DB/UI | Reference ID | project_number | exact match | | P0 |
| status (Active/Inactive/Archived) | DB/UI | Lifecycle | status (5 values) | renamed | Rex OS adds pre_construction, completed | P0 |
| project_type (varchar 50) | DB | Classification | project_type (6 values) | exact match | Rex OS adds industrial, residential, mixed_use | P0 |
| is_active | DB | Soft filter | -- | derived | Can derive from status != archived | P2 |
| procore_status | DB | Procore sync state | -- | deprecated | Rex OS is source of truth, not Procore | P2 |
| start_date | DB/UI | Project start | start_date | exact match | | P0 |
| completion_date | DB | Project end | end_date | renamed | Same concept, different name | P0 |
| address | DB | Street address | address_line1 | renamed | Same concept | P1 |
| city | DB | City | city | exact match | | P1 |
| state_code | DB | State | state | renamed | state vs state_code | P1 |
| zip_code | DB | Postal code | zip | renamed | zip vs zip_code | P1 |
| latitude | DB | Geolocation | -- | missing | Not in Rex OS | P2 |
| longitude | DB | Geolocation | -- | missing | Not in Rex OS | P2 |
| procore_id | DB | Procore sync | connector_mappings.external_id | renamed | Rex OS uses generic connector table | P1 |
| procore_project_id | DB | Procore link | connector_mappings.external_id | renamed | Same as above | P1 |
| company_id (bigint) | DB | Parent company | -- | missing | Rex OS uses project_members instead | P1 |
| synced_at | DB | Sync timestamp | connector_mappings.synced_at | renamed | Generic connector approach | P2 |
| -- | -- | -- | contract_value | extra in Rex OS | Project-level contract value | P1 |
| -- | -- | -- | square_footage | extra in Rex OS | Building size metric | P1 |
| -- | -- | -- | description | extra in Rex OS | Project description | P1 |

### 1.2 Companies / Vendors

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| vendor_name / company_name | DB/UI | Display name | companies.name | renamed | | P0 |
| trade_name | DB | Trade specialty | companies.trade | renamed | | P0 |
| vendor_group | DB | Vendor classification | companies.company_type | renamed | Rex OS has richer enum | P1 |
| email_address | DB | Contact email | companies.email | renamed | | P1 |
| business_phone | DB | Phone | companies.phone | renamed | | P1 |
| mobile_phone | DB | Alt phone | -- | missing | Rex OS only has one phone field | P2 |
| fax_number | DB | Fax | -- | deprecated | Fax is obsolete | P2 |
| website | DB | Company URL | -- | missing | Not in Rex OS | P2 |
| address / city / state_code / zip_code | DB | Location | address_line1 / city / state / zip | renamed | | P1 |
| country_code | DB | Country | -- | missing | Not in Rex OS (US-only assumption) | P2 |
| is_active | DB | Active flag | companies.status | renamed | Rex OS uses status enum instead | P0 |
| license_number | DB | Trade license | companies.license_number | exact match | | P1 |
| insurance_expiration_date | DB/UI | Insurance tracking | companies.insurance_expiry | renamed | | P0 |
| insurance_gl_expiration_date | DB | GL insurance | -- | missing | Rex OS has single insurance_expiry | P1 |
| insurance_wc_expiration_date | DB | WC insurance | -- | missing | | P1 |
| insurance_auto_expiration_date | DB | Auto insurance | -- | missing | | P1 |
| insurance_gl_limit | DB | GL limit | -- | missing | Rex OS lacks insurance detail | P1 |
| insurance_wc_limit | DB | WC limit | -- | missing | | P1 |
| insurance_auto_limit | DB | Auto limit | -- | missing | | P1 |
| insurance_carrier (procore) | DB | Insurer name | companies.insurance_carrier | exact match | Rex OS has this | P1 |
| bonding_capacity | DB | Bond limit | companies.bonding_capacity | exact match | Rex OS has this | P1 |
| prequalified | DB | Prequalification | companies.status='prequalified' | renamed | Rex OS uses status enum | P1 |
| authorized_bidder | DB | Bid eligibility | -- | missing | | P2 |
| union_member | DB | Union status | -- | missing | | P2 |
| non_union_prevailing_wage | DB | Wage class | -- | missing | | P2 |
| procore_id / vendor_id | DB | Procore link | connector_mappings | renamed | Generic connector | P1 |
| business_register / business_register_id | DB | Registration | -- | deprecated | Procore-specific metadata | P2 |
| primary_contact_* (7 fields) | DB | Primary contact | people + project_members | renamed | Rex OS normalizes via people table | P1 |
| attachments (JSONB) | DB | Vendor docs | attachments (source_type) | renamed | Rex OS uses polymorphic attachments | P1 |
| -- | -- | -- | companies.notes | extra in Rex OS | Free-text notes | P1 |

### 1.3 People / Users

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| full_name | DB/UI | Display name | people.first_name + last_name | derived | Rex OS stores separately | P0 |
| first_name / last_name | DB | Name parts | people.first_name / last_name | exact match | | P0 |
| email_address | DB | Email | people.email | renamed | | P0 |
| business_phone / mobile_phone | DB | Phones | people.phone | renamed | Rex OS has single phone | P1 |
| job_title (JSONB) | DB | Title | people.title (text) | renamed | Procore stores as JSONB multi-select | P1 |
| is_active | DB | Active flag | people.is_active | exact match | | P0 |
| is_employee | DB | Employee flag | people.role_type | renamed | Rex OS uses internal/external enum | P1 |
| avatar_url | DB | Profile photo | -- | missing | Not in Rex OS | P2 |
| initials | DB | Initials | -- | derived | Can compute from first/last name | P2 |
| employee_id | DB | HR ID | -- | missing | Not in Rex OS | P2 |
| vendor_id / vendor_name | DB | Company link | people.company_id | renamed | Rex OS uses FK to companies | P0 |

### 1.4 User Accounts / Auth

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| app_users.email | DB | Login email | user_accounts.email | exact match | | P0 |
| app_users.password_hash | DB | Auth | user_accounts.password_hash | exact match | | P0 |
| app_users.name | DB | Display name | people.first_name + last_name | renamed | Rex OS separates person from account | P0 |
| app_users.role | DB | System role | user_accounts.global_role | renamed | | P0 |
| app_users.permission_level | DB | Access level | user_accounts.is_admin + project_members.access_level | renamed | Rex OS splits global + project-level | P0 |
| app_users.allowed_projects (BIGINT[]) | DB | Project access | project_members (join table) | renamed | Rex OS normalizes properly | P0 |
| app_users.visible_panels (TEXT[]) | DB | UI panels | role_templates.visible_panels | renamed | Rex OS uses role templates | P1 |
| app_users.allowed_topics (TEXT[]) | DB | Topic access | role_templates.visible_tools | renamed | | P1 |
| app_users.must_change_password | DB | Password policy | -- | missing | Not in Rex OS | P2 |
| app_users.procore_user_id | DB | Procore link | connector_mappings | renamed | Generic connector | P1 |
| -- | -- | -- | user_accounts.mfa_secret | extra in Rex OS | MFA support | P1 |
| -- | -- | -- | sessions (full table) | extra in Rex OS | Proper session management | P0 |
| -- | -- | -- | role_templates (full table) | extra in Rex OS | Granular RBAC | P1 |
| -- | -- | -- | role_template_overrides | extra in Rex OS | Per-member permission tuning | P2 |

### 1.5 Project Members / Assignments

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| team_members.name | DB | Employee name | people.first_name + last_name | renamed | Rex OS normalizes | P0 |
| team_members.role (VP/GS/Lead_Supt/Asst_Supt/Accountant) | DB | Job role | project_members.role_template_id | renamed | Rex OS uses role templates | P0 |
| team_members.email | DB | Contact | people.email | renamed | | P0 |
| team_members.target_bonus_usd | DB | Bonus target | -- | missing | Bonus system not yet in Rex OS | P2 |
| project_assignments.project_name | DB | Project link | project_members.project_id | renamed | Rex OS uses FK instead of name | P0 |
| project_assignments.role_on_project | DB | Project role | project_members.role_template_id | renamed | | P0 |
| project_assignments.start_date / end_date | DB | Assignment period | project_members.start_date / end_date | exact match | | P1 |
| -- | -- | -- | project_members.is_primary | extra in Rex OS | Primary role flag | P1 |
| -- | -- | -- | project_members.company_id | extra in Rex OS | Company affiliation | P1 |

---

## 2. Schedule

### 2.1 Schedules

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| (no explicit schedule container in Procore) | -- | -- | schedules.id | extra in Rex OS | Rex OS has proper schedule entity | P0 |
| -- | -- | -- | schedules.name | extra in Rex OS | Schedule name | P0 |
| -- | -- | -- | schedules.schedule_type | extra in Rex OS | master/baseline/lookahead/what_if | P0 |
| -- | -- | -- | schedules.status | extra in Rex OS | active/archived/draft | P0 |
| -- | -- | -- | schedules.start_date / end_date | extra in Rex OS | Schedule date range | P0 |
| -- | -- | -- | schedules.created_by | extra in Rex OS | Author | P1 |

### 2.2 Schedule Activities / Tasks

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| tasks.task_name | DB/UI | Activity name | schedule_activities.name | renamed | | P0 |
| tasks.procore_id | DB | Procore link | connector_mappings | renamed | | P1 |
| tasks.start_date / finish_date | DB/UI | Date range | schedule_activities.start_date / end_date | renamed | finish_date vs end_date | P0 |
| tasks.actual_start_date / actual_finish_date | DB | Actuals | -- | missing | Rex OS lacks actual vs planned separation | P1 |
| tasks.baseline_start / baseline_finish | DB | Baseline | schedule_activities.baseline_start / baseline_end | renamed | | P0 |
| tasks.percentage_complete | DB/UI | Progress | schedule_activities.percent_complete | renamed | | P0 |
| tasks.critical_path | DB/UI | Critical flag | schedule_activities.is_critical | renamed | | P0 |
| tasks.is_milestone | DB | Milestone flag | schedule_activities.activity_type='milestone' | renamed | Rex OS uses type enum | P0 |
| tasks.scheduled_duration | DB | Duration | schedule_activities.duration_days | renamed | | P0 |
| tasks.start_variance / finish_variance | DB | Variance | schedule_activities.variance_days | renamed | Rex OS has single variance | P1 |
| tasks.parent_task_id | DB | Hierarchy | schedule_activities.parent_id | renamed | | P0 |
| tasks.has_subtasks | DB | Has children | -- | derived | Can derive from parent_id query | P2 |
| tasks.work_breakdown_structure | DB | WBS | -- | missing | Not in Rex OS | P1 |
| tasks.full_outline_path | DB | Path string | -- | derived | Can compute from hierarchy | P2 |
| tasks.resource_name / resource_ids | DB | Resources | schedule_activities.assigned_person_id / assigned_company_id | renamed | Rex OS normalizes | P1 |
| tasks.color | DB | UI color | -- | missing | Not in Rex OS | P2 |
| tasks.key | DB | Unique key | schedule_activities.activity_number | renamed | | P1 |
| tasks.manually_edited | DB | Edit flag | schedule_activities.is_manually_scheduled | renamed | | P1 |
| schedule_tasks.total_float / free_float | DB | Float analysis | schedule_activities.float_days | renamed | Rex OS has single float | P1 |
| schedule_tasks.trade | DB | Trade | schedule_activities.assigned_company_id | renamed | Rex OS uses FK | P1 |
| schedule_tasks.activity_id | DB | Activity ID | schedule_activities.activity_number | renamed | | P1 |
| schedule_tasks.predecessor_task_ids | DB | Dependencies | activity_links.from_activity_id | renamed | Rex OS uses link table | P0 |
| schedule_tasks.status | DB | Status | -- | missing | Rex OS uses percent_complete instead | P1 |
| -- | -- | -- | schedule_activities.cost_code_id | extra in Rex OS | Cost code link | P1 |
| -- | -- | -- | schedule_activities.location | extra in Rex OS | Location text | P1 |
| -- | -- | -- | schedule_activities.notes | extra in Rex OS | Notes | P1 |
| -- | -- | -- | schedule_activities.sort_order | extra in Rex OS | Display order | P1 |

### 2.3 Activity Links

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| scheduling_activity_links.from_activity / to_activity | DB | Link | activity_links.from_activity_id / to_activity_id | renamed | | P0 |
| scheduling_activity_links.link_type | DB | FS/FF/SS/SF | activity_links.link_type | exact match | | P0 |
| scheduling_activity_links.lag | DB | Lag | activity_links.lag_days | renamed | | P0 |

### 2.4 Schedule Constraints

Rex Procore has no dedicated constraint table. Rex OS adds:

| Rex OS Field | Status | Notes | Priority |
|---|---|---|---|
| schedule_constraints (full table) | extra in Rex OS | Constraint tracking with type/source/severity | P0 |

### 2.5 Schedule Snapshots

Rex Procore has portfolio_snapshots (aggregate). Rex OS adds:

| Rex OS Field | Status | Notes | Priority |
|---|---|---|---|
| schedule_snapshots (full table) | extra in Rex OS | Per-activity point-in-time snapshots | P1 |

---

## 3. Field Ops

### 3.1 Daily Logs

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| daily_logs.log_date | DB/UI | Date | daily_logs.log_date | exact match | | P0 |
| daily_logs.status | DB | Approval | daily_logs.status | exact match | Similar enums | P0 |
| daily_logs.weather | DB | Weather | daily_logs.weather_summary | renamed | | P0 |
| daily_logs.temperature_high / _low | DB/UI | Temperature | daily_logs.temp_high_f / temp_low_f | renamed | | P0 |
| daily_logs.notes | DB | Notes | daily_logs.work_summary | renamed | Rex OS has more specific fields | P0 |
| daily_logs.manpower_count | DB/UI | Workers | -- | derived | Sum from manpower_entries | P0 |
| daily_logs.total_hours | DB/UI | Hours | -- | derived | Sum from manpower_entries | P0 |
| daily_logs.delay_count | DB | Delays | -- | derived | Separate delay_logs in Procore | P1 |
| daily_logs.weather_conditions | DB | Rex-native | daily_logs.weather_summary | renamed | | P1 |
| daily_logs.manpower_data (JSONB) | DB | Rex-native | manpower_entries (table) | renamed | Rex OS normalizes into rows | P0 |
| daily_logs.work_performed_data (JSONB) | DB | Rex-native | daily_logs.work_summary | renamed | | P1 |
| -- | -- | -- | daily_logs.is_weather_delay | extra in Rex OS | Explicit delay flag | P1 |
| -- | -- | -- | daily_logs.delay_notes | extra in Rex OS | Delay description | P1 |
| -- | -- | -- | daily_logs.safety_notes | extra in Rex OS | Safety notes | P1 |
| -- | -- | -- | daily_logs.visitor_notes | extra in Rex OS | Visitor log | P1 |
| -- | -- | -- | daily_logs.approved_by / approved_at | extra in Rex OS | Approval tracking | P0 |

### 3.2 Manpower Entries

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| manpower_logs.company | DB | Company name | manpower_entries.company_id | renamed | Rex OS uses FK | P0 |
| manpower_logs.company_id | DB | Company link | manpower_entries.company_id | exact match | | P0 |
| manpower_logs.trade | DB | Trade | -- | derived | Can derive from companies.trade | P1 |
| manpower_logs.headcount | DB/UI | Workers | manpower_entries.worker_count | renamed | | P0 |
| manpower_logs.hours | DB/UI | Hours | manpower_entries.hours | exact match | | P0 |
| manpower_logs.notes | DB | Notes | manpower_entries.description | renamed | | P1 |

### 3.3 Punch Items

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| punch_items.title | DB/UI | Title | punch_items.title | exact match | | P0 |
| punch_items.description | DB | Description | punch_items.description | exact match | | P0 |
| punch_items.status | DB/UI | Status | punch_items.status | exact match | Rex OS has richer workflow states | P0 |
| punch_items.priority | DB/UI | Priority | punch_items.priority | exact match | | P0 |
| punch_items.deficiency_type | DB | Type | punch_items.punch_type | renamed | | P1 |
| punch_items.location / location_name | DB/UI | Location | punch_items.location | renamed | Rex OS uses text field | P0 |
| punch_items.assignee / assignee_id / assignee_name | DB/UI | Assignee | punch_items.assigned_to (FK) | renamed | Rex OS normalizes | P0 |
| punch_items.manager_id / manager_name | DB | Manager | punch_items.punch_manager_id | renamed | | P1 |
| punch_items.due_date | DB/UI | Due date | punch_items.due_date | exact match | | P0 |
| punch_items.closed_at | DB | Close date | punch_items.closed_date | renamed | | P0 |
| punch_items.days_open | DB/UI | Age | punch_items.days_open | exact match | | P0 |
| punch_items.cost_impact (boolean) | DB | Cost flag | punch_items.cost_impact (yes/no/tbd) | renamed | Rex OS uses text enum | P1 |
| punch_items.schedule_impact (boolean) | DB | Schedule flag | punch_items.schedule_impact (yes/no/tbd) | renamed | Rex OS uses text enum | P1 |
| punch_items.is_critical_path | DB | CP flag | -- | missing | Not in Rex OS | P1 |
| punch_items.trade | DB | Trade | -- | derived | Via assigned_company_id -> companies.trade | P1 |
| punch_items.punch_item_manager_company_name | DB | Manager company | -- | derived | Via punch_manager_id -> people -> company | P2 |
| punch_items.closed_by | DB | Closer | -- | missing | Rex OS lacks closed_by field | P1 |
| punch_items.closed_by_company_name | DB | Closer company | -- | missing | | P2 |
| punch_items.final_approver_company_name | DB | Approver company | -- | derived | Via final_approver_id | P2 |
| punch_items.created_by_company_name | DB | Creator company | -- | derived | Via created_by -> people -> company | P2 |
| -- | -- | -- | punch_items.punch_number | extra in Rex OS | Sequential number | P0 |
| -- | -- | -- | punch_items.assigned_company_id | extra in Rex OS | Company-level assignment | P1 |
| -- | -- | -- | punch_items.final_approver_id | extra in Rex OS | Final approver | P1 |
| -- | -- | -- | punch_items.drawing_id | extra in Rex OS | Drawing link | P1 |
| -- | -- | -- | punch_items.cost_code_id | extra in Rex OS | Cost code link | P1 |

### 3.4 Inspections

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| inspections.name / title | DB/UI | Title | inspections.title | exact match | | P0 |
| inspections.inspection_number | DB | Number | inspections.inspection_number | exact match | | P0 |
| inspections.status | DB/UI | Status | inspections.status | exact match | Similar enums | P0 |
| inspections.inspection_type / type_name | DB | Type | inspections.inspection_type | renamed | Rex OS has predefined enum | P0 |
| inspections.scheduled_date | DB/UI | Date | inspections.scheduled_date | exact match | | P0 |
| inspections.completed_date | DB | Completed | inspections.completed_date | exact match | | P0 |
| inspections.inspector_name | DB | Inspector | inspections.inspector_name | exact match | | P0 |
| inspections.passed_count / failed_count / na_count / total_items | DB/UI | Counts | -- | derived | Rex OS computes from inspection_items | P0 |
| inspections.pass_rate | DB | Rate | -- | derived | Computed from items | P1 |
| inspections.deficiency_count | DB | Deficiencies | -- | derived | Computed from items | P1 |
| inspections.responsible_contractor_id | DB | Contractor | inspections.inspecting_company_id | renamed | | P1 |
| inspections.point_of_contact_id | DB | Contact | inspections.responsible_person_id | renamed | | P1 |
| inspections.location / location_name | DB | Location | inspections.location | renamed | | P1 |
| inspections.auto_punch_id | DB | Auto-punch | -- | missing | Rex Procore auto-creates punch from failed inspection | P2 |
| inspections.deficiency_notes | DB | Notes | inspections.comments | renamed | | P1 |
| -- | -- | -- | inspections.activity_id | extra in Rex OS | Schedule link | P1 |
| -- | -- | -- | inspection_items (full table) | extra in Rex OS | Individual inspection items | P0 |

### 3.5 RFIs

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| rfis.subject | DB/UI | Subject | rfis.subject | exact match | | P0 |
| rfis.rfi_number | DB/UI | Number | rfis.rfi_number | exact match | | P0 |
| rfis.status | DB/UI | Status | rfis.status | exact match | Similar enums | P0 |
| rfis.question | DB | Question | rfis.question | exact match | | P0 |
| rfis.answer | DB | Answer | rfis.answer | exact match | | P0 |
| rfis.ball_in_court / ball_in_court_id / ball_in_court_name | DB | BIC | rfis.ball_in_court (FK) | renamed | Rex OS normalizes | P0 |
| rfis.assignee / assignee_id / assignee_name | DB | Assignee | rfis.assigned_to (FK) | renamed | Rex OS normalizes | P0 |
| rfis.due_date | DB/UI | Due date | rfis.due_date | exact match | | P0 |
| rfis.closed_at / closed_date | DB | Closed | rfis.answered_date | renamed | | P0 |
| rfis.days_open | DB/UI | Age | rfis.days_open | exact match | | P0 |
| rfis.cost_impact | DB | Cost flag | rfis.cost_impact | exact match | | P1 |
| rfis.schedule_impact | DB | Schedule flag | rfis.schedule_impact | exact match | | P1 |
| rfis.cost_code | DB | Cost code (text) | rfis.cost_code_id (FK) | renamed | Rex OS normalizes | P1 |
| rfis.drawing_number | DB | Drawing ref | rfis.drawing_id (FK) | renamed | Rex OS uses FK | P1 |
| rfis.spec_section | DB | Spec section | rfis.spec_section | exact match | | P1 |
| rfis.location_id | DB | Location | rfis.location | renamed | Rex OS uses text | P1 |
| rfis.rfi_manager | DB | Manager | -- | missing | Not in Rex OS | P1 |
| rfis.title | DB | Alt title | -- | deprecated | Redundant with subject | P2 |
| rfis.number (numeric) | DB | Numeric number | -- | deprecated | Redundant with rfi_number | P2 |
| -- | -- | -- | rfis.priority | extra in Rex OS | Priority field | P1 |
| -- | -- | -- | rfis.created_by | extra in Rex OS | Creator FK | P0 |

### 3.6 Submittals

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| submittals.title | DB/UI | Title | submittals.title | exact match | | P0 |
| submittals.submittal_number | DB/UI | Number | submittals.submittal_number | exact match | | P0 |
| submittals.status | DB/UI | Status | submittals.status | exact match | Rex OS has richer enum | P0 |
| submittals.submittal_type | DB | Type | submittals.submittal_type | exact match | Rex OS has defined enum | P0 |
| submittals.spec_section | DB | Spec section | submittals.spec_section | exact match | | P1 |
| submittals.revision / current_revision | DB | Revision | submittals.current_revision | renamed | | P0 |
| submittals.ball_in_court / current_reviewer | DB | BIC | submittals.ball_in_court (FK) | renamed | Rex OS uses FK | P0 |
| submittals.responsible_contractor_id / name | DB | Contractor | submittals.responsible_contractor (FK) | renamed | | P1 |
| submittals.submitted_at / received_date | DB | Submit date | submittals.submitted_date | renamed | | P0 |
| submittals.review_due_date / due_date | DB | Due date | submittals.due_date | renamed | | P0 |
| submittals.returned_date | DB | Return date | submittals.approved_date | renamed | | P1 |
| submittals.days_in_review | DB | Review age | -- | derived | Compute from dates | P1 |
| submittals.lead_time | DB | Lead time | submittals.lead_time_days | renamed | | P1 |
| submittals.is_critical_path | DB | CP flag | -- | missing | Not in Rex OS | P1 |
| submittals.submittal_manager_id | DB | Manager | -- | missing | Not in Rex OS | P1 |
| -- | -- | -- | submittals.submittal_package_id | extra in Rex OS | Package grouping | P1 |
| -- | -- | -- | submittals.schedule_activity_id | extra in Rex OS | Schedule link | P1 |
| -- | -- | -- | submittals.required_on_site | extra in Rex OS | Site need date | P1 |
| -- | -- | -- | submittals.location | extra in Rex OS | Location text | P1 |
| -- | -- | -- | submittal_packages (full table) | extra in Rex OS | Package management | P1 |

### 3.7 Observations

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| observations.name / title | DB | Title | observations.title | exact match | | P0 |
| observations.number | DB | Number | observations.observation_number | renamed | | P0 |
| observations.observation_type / type_name | DB | Type | observations.observation_type | exact match | | P0 |
| observations.status | DB | Status | observations.status | exact match | | P0 |
| observations.priority | DB | Priority | observations.priority | exact match | Rex OS adds 'critical' | P0 |
| observations.description | DB | Description | observations.description | exact match | | P0 |
| observations.assignee_id / assignee_name | DB | Assignee | observations.assigned_to (FK) | renamed | | P1 |
| observations.assignee_company_name | DB | Company | observations.assigned_company_id (FK) | renamed | | P1 |
| observations.location / location_name | DB | Location | observations.location | renamed | | P1 |
| observations.due_date | DB | Due date | observations.due_date | exact match | | P1 |
| observations.closed_at | DB | Closed | observations.closed_date | renamed | | P1 |
| observations.contributing_behavior / contributing_condition | DB | Root cause | -- | missing | Not in Rex OS | P2 |
| observations.attachments_count | DB | Attachment count | -- | derived | Count from attachments table | P2 |
| -- | -- | -- | observations.corrective_action | extra in Rex OS | Corrective action text | P1 |

### 3.8 Tasks (Action Items)

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| tasks_tool.title | DB/UI | Title | tasks.title | exact match | | P0 |
| tasks_tool.description | DB | Description | tasks.description | exact match | | P0 |
| tasks_tool.status | DB/UI | Status | tasks.status | exact match | Similar enums | P0 |
| tasks_tool.category | DB | Category | tasks.category | exact match | Rex OS has defined enum | P1 |
| tasks_tool.assignees | DB | Assignees (text) | tasks.assigned_to (FK) | renamed | Rex OS normalizes | P0 |
| tasks_tool.due_date | DB/UI | Due date | tasks.due_date | exact match | | P0 |
| tasks_tool.date_closed | DB | Closed date | tasks.completed_date | renamed | | P0 |
| tasks_tool.date_created | DB | Created | tasks.created_at | renamed | | P0 |
| tasks_tool.number | DB | Number | tasks.task_number | renamed | | P0 |
| tasks_tool.priority | DB | Priority | tasks.priority | exact match | | P1 |
| tasks_tool.is_private | DB | Private flag | -- | deprecated | Rex OS uses RBAC instead | P2 |
| tasks_tool.latest_comment | DB | Last comment | -- | missing | No comment system yet | P2 |
| tasks_tool.activity_count | DB | Activity count | -- | deprecated | Procore-specific | P2 |
| -- | -- | -- | tasks.assigned_company_id | extra in Rex OS | Company assignment | P1 |
| -- | -- | -- | tasks.created_by | extra in Rex OS | Creator FK | P0 |

### 3.9 Safety Incidents

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| safety_incidents.incident_date | DB | Date | safety_incidents.incident_date | exact match | | P0 |
| safety_incidents.incident_type | DB | Type | safety_incidents.incident_type | exact match | Rex OS has richer enum | P0 |
| safety_incidents.description | DB | Description | safety_incidents.description | exact match | | P0 |
| safety_incidents.employees_involved | DB | People | safety_incidents.affected_person_id (FK) | renamed | Rex OS normalizes | P1 |
| safety_incidents.reported_by | DB | Reporter | safety_incidents.reported_by (FK) | renamed | Rex OS uses FK | P0 |
| safety_incidents.quarter / year | DB | Time bucket | -- | derived | Compute from incident_date | P2 |
| safety_incidents.vp_reviewed / vp_decision / vp_notes | DB | VP review | -- | missing | Scorecard integration not in Rex OS | P2 |
| -- | -- | -- | safety_incidents.incident_number | extra in Rex OS | Sequential ID | P0 |
| -- | -- | -- | safety_incidents.title | extra in Rex OS | Title | P0 |
| -- | -- | -- | safety_incidents.severity | extra in Rex OS | Severity enum | P0 |
| -- | -- | -- | safety_incidents.status | extra in Rex OS | Workflow status | P0 |
| -- | -- | -- | safety_incidents.incident_time | extra in Rex OS | Time of incident | P1 |
| -- | -- | -- | safety_incidents.root_cause | extra in Rex OS | Root cause analysis | P1 |
| -- | -- | -- | safety_incidents.corrective_action | extra in Rex OS | Corrective action | P1 |
| -- | -- | -- | safety_incidents.is_osha_recordable | extra in Rex OS | OSHA flag | P0 |
| -- | -- | -- | safety_incidents.lost_time_days | extra in Rex OS | Lost time tracking | P1 |
| -- | -- | -- | safety_incidents.affected_company_id | extra in Rex OS | Company link | P1 |

### 3.10 Meetings

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| meetings.title | DB | Title | meetings.title | exact match | | P0 |
| meetings.meeting_type | DB | Type | meetings.meeting_type | exact match | | P0 |
| meetings.meeting_date / scheduled_at | DB | Date | meetings.meeting_date | renamed | | P0 |
| meetings.location | DB | Location | meetings.location | exact match | | P1 |
| meetings.attendees (JSONB) | DB | Attendees | meetings.attendees (JSONB) | exact match | | P1 |
| meetings.total_agenda_items | DB | Agenda count | -- | derived | | P2 |
| meetings.total_action_items / open_action_items | DB | Actions | -- | derived | Count from meeting_action_items | P1 |
| meetings.minutes_status / minutes_published_at | DB | Minutes status | -- | missing | Not in Rex OS | P2 |
| meetings.is_recurring / is_private / is_draft | DB | Flags | -- | missing | Not in Rex OS | P2 |
| -- | -- | -- | meetings.start_time / end_time | extra in Rex OS | Time range | P1 |
| -- | -- | -- | meetings.agenda | extra in Rex OS | Agenda text | P1 |
| -- | -- | -- | meetings.minutes | extra in Rex OS | Minutes text | P1 |
| -- | -- | -- | meetings.packet_url | extra in Rex OS | Packet link | P1 |
| -- | -- | -- | meeting_action_items (full table) | extra in Rex OS | Normalized action items | P0 |

### 3.11 Photos

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| photos.filename | DB | Filename | photos.filename | exact match | | P0 |
| photos.image_url | DB | URL | photos.storage_url | renamed | | P0 |
| photos.album_id / album_name | DB | Album | photos.photo_album_id (FK) | renamed | | P1 |
| photos.taken_at | DB | Taken date | photos.taken_at | exact match | | P1 |
| photos.description | DB | Description | photos.description | exact match | | P1 |
| photos.location_name / location_id | DB | Location | photos.location | renamed | | P1 |
| photos.trade / image_category | DB | Category | photos.tags (JSONB) | renamed | | P2 |
| photos.is_private / starred | DB | Flags | -- | missing | Not in Rex OS | P2 |
| -- | -- | -- | photos.file_size | extra in Rex OS | File size tracking | P1 |
| -- | -- | -- | photos.content_type | extra in Rex OS | MIME type | P1 |
| -- | -- | -- | photos.storage_key | extra in Rex OS | Storage reference | P0 |
| -- | -- | -- | photos.thumbnail_url | extra in Rex OS | Thumbnail | P1 |
| -- | -- | -- | photos.latitude / longitude | extra in Rex OS | Geolocation | P2 |
| -- | -- | -- | photos.source_type / source_id | extra in Rex OS | Polymorphic link | P1 |

---

## 4. Financials

### 4.1 Cost Codes

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| cost_codes.code | DB | Code | cost_codes.code | exact match | | P0 |
| cost_codes.description | DB | Description | cost_codes.name | renamed | | P0 |
| cost_codes.full_code | DB | Full path | -- | derived | Can compute from hierarchy | P2 |
| cost_codes.parent_id | DB | Hierarchy | cost_codes.parent_id | exact match | | P0 |
| cost_codes.sortable_code | DB | Sort key | cost_codes.sort_order | renamed | | P1 |
| -- | -- | -- | cost_codes.cost_type | extra in Rex OS | Type classification | P0 |
| -- | -- | -- | cost_codes.is_active | extra in Rex OS | Active flag | P1 |

### 4.2 Budgets

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| budgets.cost_code / cost_code_description | DB/UI | Code | budget_line_items.cost_code_id (FK) | renamed | Rex OS normalizes | P0 |
| budgets.original_budget | DB/UI | Original | budget_line_items.original_budget | exact match | | P0 |
| budgets.budget_modifications | DB | Modifications | budget_line_items.approved_changes | renamed | | P0 |
| budgets.revised_budget | DB/UI | Revised | budget_line_items.revised_budget | exact match | | P0 |
| budgets.committed_costs | DB/UI | Committed | budget_line_items.committed_costs | exact match | | P0 |
| budgets.direct_costs | DB/UI | Direct costs | budget_line_items.direct_costs | exact match | | P0 |
| budgets.projected_cost | DB/UI | Projected | budget_line_items.projected_cost | exact match | | P0 |
| budgets.variance / over_under | DB/UI | Variance | budget_line_items.over_under | renamed | | P0 |
| budgets.forecast_to_complete | DB | Forecast | -- | derived | Can compute: projected - (committed + direct) | P1 |
| budgets.total_billings | DB | Billings | -- | derived | Sum from payment_applications | P1 |
| budgets.cost_type | DB | Type | -- | derived | Via cost_code_id -> cost_codes.cost_type | P1 |
| budgets.category / wbs_code | DB | Category | -- | deprecated | Procore-specific | P2 |
| -- | -- | -- | budget_line_items.pending_changes | extra in Rex OS | Pending CO tracking | P0 |
| -- | -- | -- | budget_line_items.notes | extra in Rex OS | Notes | P1 |
| -- | -- | -- | budget_snapshots (full table) | extra in Rex OS | Point-in-time tracking | P1 |

### 4.3 Prime Contracts

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| prime_contracts.number | DB | Number | prime_contracts.contract_number | renamed | | P0 |
| prime_contracts.title | DB | Title | prime_contracts.title | exact match | | P0 |
| prime_contracts.status | DB | Status | prime_contracts.status | exact match | | P0 |
| prime_contracts.grand_total / original_value | DB | Original value | prime_contracts.original_value | renamed | | P0 |
| prime_contracts.approved_co_amount / approved_cos | DB | Approved COs | prime_contracts.approved_cos | exact match | | P0 |
| prime_contracts.revised_amount | DB | Revised value | prime_contracts.revised_value | renamed | | P0 |
| prime_contracts.contract_amount | DB | Contract $ | -- | deprecated | Redundant with original_value | P2 |
| prime_contracts.contract_date | DB | Date | prime_contracts.executed_date | renamed | | P1 |
| prime_contracts.executed | DB | Executed flag | prime_contracts.status='executed' | renamed | Rex OS uses status | P1 |
| prime_contracts.contractor / contractor_id | DB | Contractor | prime_contracts.owner_company_id | renamed | | P1 |
| -- | -- | -- | prime_contracts.billed_to_date | extra in Rex OS | Billing progress | P0 |
| -- | -- | -- | prime_contracts.retention_rate | extra in Rex OS | Retention % | P0 |

### 4.4 Commitments

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| commitments.commitment_number / number | DB | Number | commitments.commitment_number | exact match | | P0 |
| commitments.title | DB | Title | commitments.title | exact match | | P0 |
| commitments.status | DB | Status | commitments.status | exact match | Rex OS has richer enum | P0 |
| commitments.commitment_type / contract_type | DB | Type | commitments.contract_type | renamed | | P0 |
| commitments.vendor_id / vendor_name | DB | Vendor | commitments.vendor_id (FK) | renamed | Rex OS normalizes | P0 |
| commitments.contract_value / grand_total / original_value | DB | Value | commitments.original_value | renamed | Multiple names in Procore | P0 |
| commitments.approved_cos_value / approved_cos | DB | Approved COs | commitments.approved_cos | exact match | | P0 |
| commitments.revised_value / revised_amount | DB | Revised | commitments.revised_value | exact match | | P0 |
| commitments.invoiced_to_date / billed_amount | DB | Invoiced | commitments.invoiced_to_date | exact match | | P0 |
| commitments.retainage_held | DB | Retention $ | commitments.retention_held | renamed | | P0 |
| commitments.balance_to_finish | DB | Balance | commitments.remaining_to_invoice | renamed | | P0 |
| commitments.executed / executed_on | DB | Executed | commitments.executed_date | renamed | Rex OS stores date | P1 |
| commitments.description | DB | Description | commitments.scope_of_work | renamed | | P1 |
| commitments.estimated_completion_date | DB | End date | -- | missing | Not in Rex OS | P1 |
| commitments.signed_contract_amount | DB | Signed amount | -- | deprecated | Redundant with original_value | P2 |
| commitments.pending_changes_amount | DB | Pending COs | -- | derived | Sum from PCOs where status=pending | P1 |
| -- | -- | -- | commitments.retention_rate | extra in Rex OS | Retention % | P0 |
| -- | -- | -- | commitments.notes | extra in Rex OS | Notes | P1 |
| -- | -- | -- | commitments.created_by | extra in Rex OS | Creator | P1 |
| -- | -- | -- | commitment_line_items (full table) | extra in Rex OS | Detailed line items | P0 |

### 4.5 Change Events

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| change_events.title | DB/UI | Title | change_events.title | exact match | | P0 |
| change_events.number / alphanumeric_number | DB | Number | change_events.event_number | renamed | | P0 |
| change_events.description | DB | Description | change_events.description | exact match | | P0 |
| change_events.status | DB/UI | Status | change_events.status | exact match | | P0 |
| change_events.scope | DB | Scope | change_events.scope | exact match | | P0 |
| change_events.change_type / event_type | DB | Type | change_events.event_type | renamed | | P0 |
| change_events.change_reason | DB | Reason | change_events.change_reason | exact match | | P0 |
| change_events.rfi_id | DB | RFI link | change_events.rfi_id | exact match | | P1 |
| change_events.prime_contract_id | DB | Contract link | change_events.prime_contract_id | exact match | | P1 |
| change_events.change_items (JSONB) | DB | Line items | -- | missing | Rex OS lacks CE line items | P1 |
| change_events.change_event_line_items (JSONB) | DB | Details | -- | missing | | P1 |
| change_events.rfqs (JSONB) | DB | RFQs | -- | missing | RFQ workflow not in Rex OS | P2 |
| change_events.attachments (JSONB) | DB | Attachments | attachments (table) | renamed | Rex OS uses polymorphic attachments | P1 |
| change_events.status_id / status_mapped_to_status / change_event_status_* | DB | Status metadata | -- | deprecated | Procore-specific status mapping | P2 |
| change_events.change_type_id / change_type_abbreviation | DB | Type metadata | -- | deprecated | Procore ID fields | P2 |
| change_events.change_reason_id / change_reason_company_id | DB | Reason metadata | -- | deprecated | Procore ID fields | P2 |
| -- | -- | -- | change_events.estimated_amount | extra in Rex OS | Estimated cost | P0 |

### 4.6 PCOs, CCOs, Pay Apps, Lien Waivers

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| pcos.number | DB | PCO # | potential_change_orders.pco_number | renamed | | P0 |
| pcos.title | DB | Title | potential_change_orders.title | exact match | | P0 |
| pcos.status | DB | Status | potential_change_orders.status | exact match | | P0 |
| pcos.grand_total | DB | Amount | potential_change_orders.amount | renamed | | P0 |
| pcos.contract_id | DB | Commitment | potential_change_orders.commitment_id | renamed | | P0 |
| pcos.prime_change_event_id | DB | CE link | potential_change_orders.change_event_id | renamed | | P0 |
| change_order_packages.* | DB | CCOs | commitment_change_orders.* | renamed | Rex OS has fuller model | P0 |
| requisitions / payment_applications | DB | Pay apps | payment_applications (table) | renamed | Rex OS has cleaner model | P0 |
| lien_waivers.* | DB | Waivers | lien_waivers.* | exact match | Very similar | P0 |
| -- | -- | -- | pco_cco_links (table) | extra in Rex OS | PCO-to-CCO many-to-many | P0 |
| -- | -- | -- | billing_periods (table) | extra in Rex OS | Billing period management | P0 |
| -- | -- | -- | direct_costs (full table) | extra in Rex OS | Direct cost tracking | P0 |

---

## 5. Document Management

### 5.1 Drawings

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| drawings.drawing_number / number | DB | Number | drawings.drawing_number | exact match | | P0 |
| drawings.title | DB | Title | drawings.title | exact match | | P0 |
| drawings.discipline | DB | Discipline | drawings.discipline | exact match | | P0 |
| drawings.revision / revision_number | DB | Revision | drawings.current_revision | renamed | | P0 |
| drawings.drawing_area_id / drawing_area_name | DB | Area | drawings.drawing_area_id (FK) | renamed | | P1 |
| drawings.status | DB | Status | drawings.is_current | renamed | Rex OS uses boolean | P1 |
| drawings.pdf_url / image_url | DB | File URL | drawings.image_url | renamed | | P1 |
| drawings.spec_section | DB | Spec section | -- | missing | Not in Rex OS | P2 |
| drawings.set_name / set_id | DB | Drawing set | -- | missing | Not in Rex OS | P2 |
| drawings.revision_count | DB | Rev count | -- | derived | Count from drawing_revisions | P1 |
| -- | -- | -- | drawings.current_revision_date | extra in Rex OS | Revision date | P1 |
| -- | -- | -- | drawing_revisions (full table) | extra in Rex OS | Revision history | P1 |
| -- | -- | -- | drawing_areas (full table) | extra in Rex OS | Area management | P1 |

### 5.2 Specifications

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| specifications.number | DB | Section # | specifications.section_number | renamed | | P0 |
| specifications.title | DB | Title | specifications.title | exact match | | P0 |
| specifications.division | DB | Division | specifications.division | exact match | | P0 |
| specifications.revision_number | DB | Revision | specifications.current_revision | renamed | | P0 |
| specifications.set_name / set_id | DB | Spec set | -- | missing | Not in Rex OS | P2 |
| -- | -- | -- | specifications.revision_date | extra in Rex OS | Revision date | P1 |
| -- | -- | -- | specifications.attachment_id | extra in Rex OS | File link | P1 |

### 5.3 Attachments

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| (JSONB on various tables) | DB | File data | attachments (normalized table) | renamed | Rex OS properly normalizes | P0 |
| -- | -- | -- | attachments.source_type / source_id | extra in Rex OS | Polymorphic link | P0 |
| -- | -- | -- | attachments.storage_key | extra in Rex OS | Cloud storage key | P0 |

### 5.4 Correspondence

Rex Procore has no correspondence table (uses email_log + sub_communications). Rex OS adds:

| Rex OS Field | Status | Notes | Priority |
|---|---|---|---|
| correspondence (full table) | extra in Rex OS | Formal project correspondence | P2 |

---

## 6. Closeout & Warranty

### 6.1 Closeout Checklists

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| closeout_checklists.item_category | DB | Category | closeout_checklist_items.category | renamed | Rex OS normalizes | P0 |
| closeout_checklists.item_name | DB/UI | Item name | closeout_checklist_items.name | renamed | | P0 |
| closeout_checklists.status | DB/UI | Status | closeout_checklist_items.status | exact match | | P0 |
| closeout_checklists.due_date | DB | Due date | closeout_checklist_items.due_date | exact match | | P0 |
| closeout_checklists.completed_at | DB | Completed | closeout_checklist_items.completed_date | renamed | | P0 |
| closeout_checklists.completed_by | DB | Completed by | closeout_checklist_items.completed_by | exact match | | P0 |
| closeout_checklists.notes | DB | Notes | closeout_checklist_items.notes | exact match | | P1 |
| closeout_checklist (extended).spec_division / spec_section / spec_title | DB | Spec data | -- | missing | Rex OS lacks spec linkage on items | P1 |
| closeout_checklist (extended).item_type | DB | Type | -- | missing | Category is similar but different | P2 |
| closeout_checklist (extended).responsible_vendor / responsible_vendor_id | DB | Vendor | closeout_checklist_items.assigned_company_id | renamed | | P0 |
| closeout_checklist (extended).assigned_to | DB | Assignee | closeout_checklist_items.assigned_person_id | renamed | | P0 |
| closeout_checklist (extended).procore_document_id / procore_submittal_id | DB | Procore links | -- | deprecated | Rex OS is standalone | P2 |
| -- | -- | -- | closeout_checklists (container table) | extra in Rex OS | Checklist-level entity | P0 |
| -- | -- | -- | closeout_checklists.substantial_completion_date | extra in Rex OS | SC date | P0 |
| -- | -- | -- | closeout_checklists.total_items / completed_items / percent_complete | extra in Rex OS | Aggregate counters | P0 |
| -- | -- | -- | closeout_templates / closeout_template_items | extra in Rex OS | Template system | P0 |

### 6.2 Warranties

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| warranty_items.spec_section | DB | Spec section | -- | missing | Rex OS uses cost_code_id instead | P1 |
| warranty_items.description | DB | Description | warranties.scope_description | renamed | | P0 |
| warranty_items.system_or_product | DB | System/product | -- | missing | Not in Rex OS | P1 |
| warranty_items.warranty_type | DB | Type | warranties.warranty_type | exact match | Rex OS has richer enum | P0 |
| warranty_items.duration_years / duration_months | DB | Duration | warranties.duration_months | renamed | Rex OS stores months only | P0 |
| warranty_items.start_date / expiration_date | DB | Dates | warranties.start_date / expiration_date | exact match | | P0 |
| warranty_items.manufacturer | DB | Manufacturer | -- | missing | Not in Rex OS | P1 |
| warranty_items.vendor_name / vendor_id | DB | Vendor | warranties.company_id | renamed | | P0 |
| warranty_items.document_status | DB | Doc status | warranties.is_letter_received / is_om_received | renamed | Rex OS has explicit booleans | P0 |
| warranty_items.active_claims / last_claim_date / claim_notes | DB | Claims | warranty_claims (table) | renamed | Rex OS normalizes claims | P0 |
| warranty_items.alert_at_days_before | DB | Alert config | warranty_alerts.alert_type | renamed | Rex OS has alert table | P1 |
| warranty_items.alert_sent | DB | Alert status | warranty_alerts.is_sent | renamed | | P1 |
| -- | -- | -- | warranties.commitment_id | extra in Rex OS | Commitment link | P1 |
| -- | -- | -- | warranties.cost_code_id | extra in Rex OS | Cost code link | P1 |
| -- | -- | -- | warranty_claims (full table) | extra in Rex OS | Formal claims tracking | P0 |
| -- | -- | -- | warranty_alerts (full table) | extra in Rex OS | Alert management | P1 |

### 6.3 Completion Milestones

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| milestone_tracking.milestone_name | DB/UI | Name | completion_milestones.milestone_name | exact match | | P0 |
| milestone_tracking.milestone_type | DB | Type | completion_milestones.milestone_type | exact match | Rex OS has richer enum | P0 |
| milestone_tracking.phase | DB | Phase | -- | deprecated | Rex OS uses milestone_type for phasing | P1 |
| milestone_tracking.baseline_date | DB | Baseline | completion_milestones.scheduled_date | renamed | | P0 |
| milestone_tracking.forecast_date | DB | Forecast | -- | missing | Not in Rex OS | P1 |
| milestone_tracking.actual_date | DB | Actual | completion_milestones.actual_date | exact match | | P0 |
| milestone_tracking.slippage_days (generated) | DB | Slippage | completion_milestones.variance_days | renamed | | P0 |
| milestone_tracking.percent_complete | DB | Progress | -- | missing | Not in Rex OS milestones | P1 |
| milestone_tracking.status | DB/UI | Status | completion_milestones.status | exact match | | P0 |
| milestone_tracking.responsible_party | DB | Owner | completion_milestones.certified_by | renamed | Different semantics | P1 |
| milestone_tracking.notes | DB | Notes | completion_milestones.notes | exact match | | P1 |
| -- | -- | -- | completion_milestones.is_evidence_complete | extra in Rex OS | Evidence tracking | P0 |
| -- | -- | -- | completion_milestones.evidence_requirements (JSONB) | extra in Rex OS | Evidence items list | P0 |
| -- | -- | -- | completion_milestones.sort_order | extra in Rex OS | Display order | P1 |

### 6.4 O&M Manual Tracker

| Rex Procore Field | Source Type | Purpose | Rex OS Equivalent | Status | Notes | Priority |
|---|---|---|---|---|---|---|
| om_manual_tracker.spec_section / spec_title | DB | Section | -- | missing | Not in Rex OS | P1 |
| om_manual_tracker.required_count / received_count | DB | Tracking | -- | missing | Rex OS uses warranties.is_om_received boolean | P1 |
| om_manual_tracker.status | DB | Status | -- | missing | No dedicated O&M tracker in Rex OS | P1 |
| om_manual_tracker.vendor_name / vendor_id | DB | Vendor | -- | missing | | P1 |

---

## 7. Rex Procore Features NOT in Rex OS (by design or not yet)

### 7.1 Procore Sync Infrastructure (by design - deprecated)
All `procore_id`, `synced_at`, `sync_source`, `is_deleted`, `deleted_at`, `sync_log`, `webhook_events` fields are intentionally excluded. Rex OS is the source of truth.

### 7.2 AI/Intelligence Features (not yet)
- Risk predictions, photo analysis, voice transcription, safety scans, NLP commands, delay claims engine, BIM integration, document generation, drawing AI, cost benchmarks, weather forecasts

### 7.3 Bonus/Performance System (not yet)
- Quarterly scorecards, milestone bonus, buyout savings, EBITDA growth, team bonus summary, bonus engine, leaderboard metrics, achievements

### 7.4 Communication Features (not yet)
- Email log, sub communications, notification preferences, notification digests, daily narratives

### 7.5 Compliance/Alert Features (not yet)
- Inspection templates, inspection compliance, daily log compliance, RFI alert log, punch alert log, insurance alert log, closeout alert log, evidence cure log

### 7.6 Preconstruction Features (not yet)
- Bid packages, bid submissions, bid comparison reports, permits, permit inspections, material tracking

### 7.7 Portal / External Access (not yet)
- Portal users, portal activity log

### 7.8 Process Features (not yet)
- Action queue, command history, entity aliases, writeback log, trend baselines, recovery plans, lookahead configs, schedule commitment maps

---

## Summary Statistics

| Metric | Rex Procore | Rex OS | Notes |
|---|---|---|---|
| Total tables | ~113 | 57 | Rex OS is normalized and focused |
| Frontend screens | 43+ | 8 | Rex OS covers closeout slice only |
| Core domain tables | ~40 | 57 | Rex OS has MORE core domain tables |
| AI/Intelligence tables | ~25 | 0 | Phase 2+ feature |
| Sync/Infrastructure tables | ~15 | 1 (connector_mappings) | Intentional simplification |
| Bonus/Performance tables | ~12 | 0 | Phase 2+ feature |
| Fields per core entity | ~15-60 (denormalized) | ~10-25 (normalized) | Rex OS is cleaner |
