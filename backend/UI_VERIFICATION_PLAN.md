# Rex OS — UI Verification Plan

Thin vertical slice proving the backend is usable from a real product surface.

---

## Seed data

| Entity | ID | Notes |
|--------|----|-------|
| Project "Bishop Modern" | `40000000-0000-4000-a000-000000000001` | 4 seeded members |
| Admin user (Andrew Roberts) | email `aroberts@exxircapital.com`, password `rex2026!` | admin + vp |
| Standard user (Mitch Andersen) | email `mandersen@exxircapital.com`, password `rex2026!` | standard on Bishop |
| Template "Rex Standard 34-Item" | `a0000001-0000-0000-0000-000000000001` | 34 checklist items |
| Person Roberts (for certified_by) | `10000000-0000-4000-a000-000000000001` | |

---

## Auth

All endpoints except `/api/health`, `/api/ready`, and `/api/auth/login` require a bearer token.

```
POST /api/auth/login
Body: {"email": "aroberts@exxircapital.com", "password": "rex2026!"}
Response: {"token": "...", "token_type": "bearer", ...}

# Use: Authorization: Bearer <token>
```

---

## Flow 1: Portfolio closeout readiness

**Purpose:** See all projects with their closeout status at a glance.

```
GET /api/closeout-readiness/portfolio
```

**Expected outcome:**
- Returns `summary` with `total_projects`, `pass_count`, `warning_count`, `fail_count`, `not_started_count`
- Returns `projects` array with per-project row: `project_id`, `name`, `readiness_status`, `best_checklist_percent`, `achieved_milestones`, `holdback_gate_status`

**Auth:** any authenticated user (admin/vp sees all projects; members see only their projects)

---

## Flow 2: Project closeout readiness detail

**Purpose:** Drill into a single project's closeout health.

```
GET /api/projects/40000000-0000-4000-a000-000000000001/closeout-readiness
```

**Expected outcome:**
- `overall_status`: one of `pass`, `warning`, `fail`, `not_started`
- `checklist_summary`: `total_items`, `completed_items`, `percent_complete`
- `milestone_summary`: counts of achieved/evidence-complete/certified
- `warranty_summary`: claimed and expiring-soon counts
- `open_issues`: array of severity + message

**Auth:** must be a member of Bishop (or admin/vp)

---

## Flow 3: Create closeout checklist from template

**Purpose:** Instantiate a 34-item checklist on Bishop from the standard template.

```
POST /api/closeout-checklists/from-template
Body: {
  "project_id": "40000000-0000-4000-a000-000000000001",
  "template_id": "a0000001-0000-0000-0000-000000000001",
  "substantial_completion_date": "2026-06-01"
}
```

**Expected outcome:**
- 201 with checklist response: `id`, `project_id`, `total_items` (34), `completed_items` (0), `percent_complete` (0)
- Each item has a computed `due_date` derived from `substantial_completion_date - days_before_substantial`

**Auth:** admin or vp only

---

## Flow 4: Complete checklist items + observe rollup

**Purpose:** Mark items complete and verify the parent checklist's `percent_complete` updates.

```
# List items for the checklist
GET /api/closeout-checklist-items/?checklist_id=<checklist_id>

# Mark one item complete
PATCH /api/closeout-checklist-items/<item_id>
Body: {"status": "complete", "completed_date": "2026-05-01"}

# Re-fetch checklist to verify rollup
GET /api/closeout-checklists/<checklist_id>
```

**Expected outcome:**
- After PATCH: item status = `complete`
- Parent checklist: `completed_items` incremented, `percent_complete` updated (e.g., 1/34 = ~2.94%)

**Auth:** project member with standard+ access

---

## Flow 5: Milestone evidence, certification, and gate evaluation

**Purpose:** Full milestone lifecycle: check evidence, certify, then evaluate holdback gates.

### Step 5a: Create a milestone
```
POST /api/completion-milestones/
Body: {
  "project_id": "40000000-0000-4000-a000-000000000001",
  "milestone_type": "substantial_completion",
  "milestone_name": "Substantial Completion - Bishop",
  "target_date": "2026-06-30",
  "status": "pending"
}
```

### Step 5b: View evidence checklist
```
GET /api/completion-milestones/<milestone_id>/evidence-checklist
```
Returns parsed JSONB evidence items + `payout_percent`, `holdback_percent`.

### Step 5c: Evaluate evidence
```
POST /api/completion-milestones/<milestone_id>/evaluate-evidence
Body: {"all_items_complete": true, "notes": "All docs received"}
```

### Step 5d: Certify milestone (admin/vp only)
```
POST /api/completion-milestones/<milestone_id>/certify
Body: {
  "certified_by": "10000000-0000-4000-a000-000000000001",
  "actual_date": "2026-06-15",
  "notes": "Certified by Andrew"
}
```
Returns: status = `achieved`, `variance_days` computed, `evidence_incomplete_warning` if evidence wasn't marked complete.

### Step 5e: Evaluate holdback gates (admin/vp only)
```
POST /api/completion-milestones/<milestone_id>/evaluate-gates
```
Returns: `gate_status` (pass/warning/fail), array of `gate_results` with individual checks (certified, evidence_complete, closeout_checklist threshold, warranty_status, punch_aging, time triggers).

---

## Flow 6: Attachment upload and download

**Purpose:** Upload a file to a project, then download it.

### Step 6a: Upload (multipart form)
```
POST /api/attachments/upload
Content-Type: multipart/form-data

Fields:
  project_id: 40000000-0000-4000-a000-000000000001
  source_type: rfi
  source_id: <any UUID>
  file: <binary file>
```
Returns 201 with `AttachmentResponse`: `id`, `filename`, `file_size`, `storage_key`, `storage_url`.

### Step 6b: Download
```
GET /api/attachments/<attachment_id>/download
```
Returns raw file bytes with `Content-Disposition: attachment; filename="..."`.

**Auth:**
- Upload: project member with `field_only`+ access
- Download: project member with `read_only`+ access
- Both: admin/vp bypass

---

## Permission denial verification

| Scenario | Expected |
|----------|----------|
| Unauthenticated request to any scoped endpoint | 401 |
| Non-member reads project detail | 404 |
| Non-member creates RFI on foreign project | 403 |
| `read_only` member creates punch item | 403 |
| `field_only` member creates cost code | 403 |
| Admin creates anything on any project | 201 |

---

## How to run verification

1. Start backend: `cd backend && source .venv/Scripts/activate && uvicorn main:app --reload`
2. Open Swagger: `http://localhost:8000/docs`
3. Login via `POST /api/auth/login` with admin creds
4. Copy the token and click "Authorize" in Swagger, enter `Bearer <token>`
5. Walk through flows 1-6 in order
6. For permission denial tests: login as Mitch (`mandersen@exxircapital.com`) and repeat
