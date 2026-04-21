# Phase 4a — Procore Resource Rollout (projects, users, vendors) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the Procore connector (already live for RFIs) to cover the three Rex App resources that currently have real data: `projects` (8 rows), `users` (615 rows), `vendors` (619 rows). Also lands the `_upsert_canonical` registry refactor that the Phase 4 final review flagged as a pre-requisite for scaling to more resources.

**Architecture:** Same pattern as the Phase 4 RFI reference pipeline. The orchestrator iterates project mappings in `rex.connector_mappings` — for `projects` resource this is different (no parent project scope; it's the thing being mapped), so the orchestrator's project-iteration logic gains a conditional branch. The `_upsert_canonical` function becomes a dispatch registry keyed by resource_type, each entry naming the canonical table + natural key + insert template.

**Tech Stack:** Python 3.11+, FastAPI, asyncpg, SQLAlchemy Async, pytest. No new dependencies.

**Deferred to Phase 4b:** `submittals`, `daily_logs`, `schedule_tasks` (tasks), `change_events`, `commitments`, `budget_line_items`, `documents` — all currently empty in Rex App (old-app cron silently failing). Unblocks once that sync is fixed OR direct Procore API is wired.

---

## File structure

**New / modified:**
- `backend/app/services/connectors/procore/payloads.py` — add `build_project_payload`, `build_user_payload`, `build_vendor_payload`
- `backend/app/services/connectors/procore/mapper.py` — replace stub `map_project`; add `map_user`, `map_vendor`
- `backend/app/services/connectors/procore/adapter.py` — wire `list_projects`, `list_users`, `fetch_vendors` for real
- `backend/app/services/connectors/procore/orchestrator.py` — refactor `_upsert_canonical` to a registry; add 3 new `_RESOURCE_CONFIG` entries; handle the "resource_type = 'projects' (no parent-project scope)" case
- Potentially: `migrations/0XX_*.sql` — unique constraints on `rex.people (email)`, `rex.companies (procore-source natural key)` if they don't already exist
- Tests per resource: `test_adapter_fetch_<resource>.py`, extend `test_orchestrator.py` with smokes for each.

**Plan follows the Phase 4 RFI reference pattern for all mechanics.** Each resource task is a delta from the RFI baseline documented in `docs/superpowers/plans/2026-04-20-phase4-procore-rex-app-connector.md`. Refer to that plan for the pool / client / staging shape. This plan only documents the per-resource deltas.

---

## Task 1: `_upsert_canonical` registry refactor

**Files:**
- Modify: `backend/app/services/connectors/procore/orchestrator.py`

**Context:** Phase 4's final review flagged that `_upsert_canonical` hard-codes `canonical_table == "rfis"` and raises NotImplementedError otherwise. With 3 more resources arriving, this becomes a dispatch ladder; refactor to a per-resource registry now.

- [ ] **Step 1: Read current `_upsert_canonical`.** It's at the bottom of `orchestrator.py`. Note the INSERT shape, the ON CONFLICT key, and the `RETURNING id` pattern.

- [ ] **Step 2: Introduce `_CANONICAL_WRITERS` registry**

Extract the inline RFI INSERT into a per-resource writer function, and register it:

```python
# near the top of orchestrator.py, after _RESOURCE_CONFIG

# Per-canonical-table writer. Takes db + mapped row dict, returns the new
# canonical id. New resources add an entry here.
async def _write_rfis(db: AsyncSession, row: dict[str, Any]) -> UUID:
    cols = list(row.keys())
    col_sql = ", ".join(cols)
    val_sql = ", ".join(f":{c}" for c in cols)
    update_sql = ", ".join(
        f"{c} = EXCLUDED.{c}"
        for c in cols
        if c not in ("project_id", "rfi_number")
    )
    sql = text(f"""
        INSERT INTO rex.rfis (id, {col_sql})
        VALUES (gen_random_uuid(), {val_sql})
        ON CONFLICT (project_id, rfi_number) DO UPDATE SET {update_sql}
        RETURNING id
    """)
    res = await db.execute(sql, row)
    return res.scalar_one()


_CANONICAL_WRITERS: dict[str, Callable[[AsyncSession, dict[str, Any]], Awaitable[UUID]]] = {
    "rfis": _write_rfis,
}


async def _upsert_canonical(
    db: AsyncSession,
    canonical_table: str,
    row: dict[str, Any],
) -> UUID:
    writer = _CANONICAL_WRITERS.get(canonical_table)
    if writer is None:
        raise NotImplementedError(
            f"no canonical writer registered for rex.{canonical_table}"
        )
    return await writer(db, row)
```

Add imports: `from typing import Any, Callable, Awaitable`.

- [ ] **Step 3: Run the existing RFI orchestrator tests**

```
cd backend && py -m pytest tests/services/connectors/procore/test_orchestrator.py -v
```

All 4 existing tests must still pass — the refactor is behavior-preserving.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/connectors/procore/orchestrator.py
git commit -m "refactor(connectors): per-resource canonical-writer registry in orchestrator"
```

---

## Task 2: `projects` sync

**Why projects first:** The orchestrator currently iterates `rex.connector_mappings` to find projects to sync. For the `projects` resource itself, we can't iterate existing mappings — we discover projects by fetching them. So projects gets a different branch in the orchestrator: fetch all procore projects, upsert each into `rex.projects` if a mapping doesn't exist, then write the source_link.

**Files:**
- Modify: `payloads.py` — add `build_project_payload`
- Modify: `mapper.py` — replace stub `map_project`
- Modify: `adapter.py` — wire `list_projects` for real
- Modify: `orchestrator.py` — add `_write_projects` and a "no parent-project scope" branch in `sync_resource`
- Test: `backend/tests/services/connectors/procore/test_adapter_list_projects.py`

### Step 1: payload builder

Append to `payloads.py`:

```python
def build_project_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Procore procore.projects row -> Rex canonical-friendly payload.

    See rex-procore/schema_procore_all_tables.sql lines 714-730 for the
    source columns: procore_id, company_id, project_name, project_number,
    status, start_date, completion_date, address, city, state_code,
    zip_code, created_at, updated_at, synced_at.
    """
    return {
        "id": str(row["procore_id"]),
        "project_source_id": None,  # project IS the scope; no parent scope
        "project_name": row.get("project_name"),
        "project_number": row.get("project_number"),
        "status": row.get("status"),
        "city": row.get("city"),
        "state_code": row.get("state_code"),
        "zip_code": row.get("zip_code"),
        "start_date": _iso(row.get("start_date")),
        "completion_date": _iso(row.get("completion_date")),
        "address": row.get("address"),
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }
```

### Step 2: mapper

In `mapper.py`, replace the stub `map_project`:

```python
def map_project(raw: dict[str, Any]) -> dict[str, Any]:
    """Procore payload -> canonical rex.projects row dict.

    rex.projects NOT NULL fields: name, status. project_number is unique
    nullable. No FK resolution needed — projects are top-level.
    """
    status_raw = (raw.get("status") or "").lower()
    # Procore statuses: Active / Inactive / Archived. Map to rex.projects enum.
    canonical_status = {
        "active": "active", "inactive": "inactive",
        "archived": "archived", "": "active",
    }.get(status_raw, "active")

    return {
        "name": raw.get("project_name") or "Untitled Project",
        "project_number": raw.get("project_number"),
        "status": canonical_status,
        "city": raw.get("city"),
        "state": raw.get("state_code"),  # canonical col is `state`, not `state_code`
        "start_date": _iso_date(raw.get("start_date")),
        "end_date": _iso_date(raw.get("completion_date")),
    }
```

(Reuse `_iso_date` already defined in mapper.py; if it handles only ISO-timestamp strings, extend it to accept date-only strings.)

### Step 3: adapter.list_projects

In `adapter.py`, replace the stub `list_projects`:

```python
async def list_projects(self, cursor: str | None = None) -> ConnectorPage:
    client = await self._get_client()
    rows = await client.fetch_rows(
        schema="procore",
        table="projects",
        cursor_col="procore_id",  # projects lack updated_at; use procore_id as monotonic cursor
        cursor_value=cursor,
        limit=DEFAULT_PAGE_SIZE,
    )
    items = [build_project_payload(r) for r in rows]
    next_cursor: str | None = None
    if items:
        next_cursor = items[-1]["id"]
    return ConnectorPage(items=items, next_cursor=next_cursor)
```

**IMPORTANT:** `projects.procore_id` is `bigint` not `timestamptz`. The `RexAppDbClient.fetch_rows` helper currently casts the cursor as `::text::timestamptz`. That will fail for a bigint cursor. **Update `rex_app_client.py` to accept a `cursor_col_type` kwarg** (default "timestamptz", override to "bigint" here), OR add a new helper `fetch_rows_by_id_cursor` that uses `bigint` casts. Pick whichever is smaller.

### Step 4: canonical writer

In `orchestrator.py`, add:

```python
async def _write_projects(db: AsyncSession, row: dict[str, Any]) -> UUID:
    cols = list(row.keys())
    col_sql = ", ".join(cols)
    val_sql = ", ".join(f":{c}" for c in cols)
    update_sql = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in cols
        if c not in ("project_number",)
    )
    sql = text(f"""
        INSERT INTO rex.projects (id, {col_sql})
        VALUES (gen_random_uuid(), {val_sql})
        ON CONFLICT (project_number) DO UPDATE SET {update_sql}
        RETURNING id
    """)
    res = await db.execute(sql, row)
    return res.scalar_one()

_CANONICAL_WRITERS["projects"] = _write_projects
```

**Prerequisite:** `rex.projects.project_number` must have a unique constraint. Check `migrations/rex2_canonical_ddl.sql`. If not present, add migration `02X_rex_projects_project_number_unique.sql`.

### Step 5: orchestrator branch for projects

`sync_resource` currently iterates `rex.connector_mappings WHERE source_table = 'procore.projects'` to find projects to scope to. For the `projects` resource itself, do the opposite — fetch procore projects, upsert them, create the mapping.

Add a new branch at the top of `sync_resource`:

```python
async def sync_resource(db, *, account_id, resource_type):
    cfg = _RESOURCE_CONFIG.get(resource_type)
    if cfg is None:
        raise NotImplementedError(...)

    # ... existing: start_sync_run, get_cursor ...

    if resource_type == "projects":
        # Projects have no parent-project scope — fetch all procore
        # projects and upsert into rex.projects + rex.connector_mappings.
        adapter = ProcoreAdapter(account_id=str(account_id))
        page = await adapter.list_projects(cursor=cursor)
        # ... staging + canonical + source_link as usual ...
        # ... finish_sync_run ...
        return {"rows_fetched": len(page.items), "rows_upserted": total_upserted}

    # existing: iterate connector_mappings for project-scoped resources
    ...
```

### Step 6: Resource config entry

```python
_RESOURCE_CONFIG["projects"] = {
    "raw_table": "projects_raw",
    "map_fn": mapper.map_project,
    "canonical_table": "projects",
    "source_table": "procore.projects",
    "fetch_fn_name": "list_projects",
}
```

### Step 7: Test

Write `backend/tests/services/connectors/procore/test_adapter_list_projects.py` mirroring the RFI test structure — seed `procore.projects` on the local dev DB with 3 rows, call `adapter.list_projects`, assert payloads.

Extend `test_orchestrator.py` with `test_sync_resource_projects_end_to_end` that:
1. Seeds 2 procore.projects rows (with distinct procore_id + project_number).
2. Calls `sync_resource(db, account_id=<procore_account>, resource_type="projects")`.
3. Asserts `rex.projects` has 2 new rows with matching project_number, and `rex.connector_mappings` has 2 new rows with `source_table='procore.projects'`.

### Step 8: Run the new + existing orchestrator tests, commit.

```bash
git add backend/app/services/connectors/procore/payloads.py \
        backend/app/services/connectors/procore/mapper.py \
        backend/app/services/connectors/procore/adapter.py \
        backend/app/services/connectors/procore/orchestrator.py \
        backend/app/services/connectors/procore/rex_app_client.py \
        backend/tests/services/connectors/procore/test_adapter_list_projects.py \
        backend/tests/services/connectors/procore/test_orchestrator.py \
        migrations/  # include migration if added
git commit -m "feat(connectors): projects resource sync (procore.projects -> rex.projects)"
```

---

## Task 3: `users` sync (procore.users -> rex.people)

**Why this is tricky:** Procore users map to `rex.people`, but Rex OS also has `rex.user_accounts` (login credentials). The sync only populates `rex.people` — login accounts are a separate manual provisioning step. The source_link is `(rex.people, procore.users, external_id=procore_id)`.

**Files:**
- Modify: `payloads.py` — add `build_user_payload`
- Modify: `mapper.py` — add `map_user`
- Modify: `adapter.py` — wire `list_users`
- Modify: `orchestrator.py` — `_write_users` + `_RESOURCE_CONFIG["users"]` + company-level (no parent-project) branch similar to projects
- Test: mirror Task 2's test shape

### Step 1: payload builder

```python
def build_user_payload(row: dict[str, Any]) -> dict[str, Any]:
    """procore.users row -> staging payload.
    procore.users has 53 fields; we use only the subset mapper needs."""
    return {
        "id": str(row["procore_id"]),
        "project_source_id": None,  # users are company-level
        "first_name": row.get("first_name"),
        "last_name": row.get("last_name"),
        "full_name": row.get("full_name"),
        "email": row.get("email_address"),
        "phone": row.get("mobile_phone") or row.get("business_phone"),
        "job_title": _stringify_jsonb(row.get("job_title")),
        "is_active": row.get("is_active"),
        "is_employee": row.get("is_employee"),
        "city": row.get("city"),
        "state_code": row.get("state_code"),
        "vendor_procore_id": row.get("vendor_id"),
        "employee_id": row.get("employee_id"),
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
        "last_login_at": _iso(row.get("last_login_at")),
    }


def _stringify_jsonb(value: Any) -> str | None:
    """procore.users.job_title is jsonb (multiselect). Coerce to a
    human-readable string ('Foreman, Carpenter') or None."""
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else None
    return str(value)
```

### Step 2: mapper

```python
def map_user(raw: dict[str, Any]) -> dict[str, Any]:
    """Procore user -> canonical rex.people row dict.
    
    rex.people NOT NULL fields: first_name, last_name, email, role_type.
    role_type enum includes 'internal' (Rex employees) and 'external'.
    We can't distinguish with perfect accuracy from Procore — we default
    to 'external' (subs/vendors/etc) and let an admin re-classify
    Rex employees manually."""
    first = raw.get("first_name") or ""
    last = raw.get("last_name") or ""
    full = raw.get("full_name") or f"{first} {last}".strip()
    if not first and not last and full:
        # split full_name as last-resort fallback
        parts = full.split(" ", 1)
        first, last = parts[0], (parts[1] if len(parts) > 1 else "")
    if not first: first = "(unknown)"
    if not last: last = "(unknown)"

    # email is NOT NULL + UNIQUE; synthesize a placeholder if missing.
    email = raw.get("email")
    if not email:
        email = f"procore-user-{raw.get('id')}@placeholder.invalid"

    return {
        "first_name": first,
        "last_name": last,
        "email": email,
        "phone": raw.get("phone"),
        "title": raw.get("job_title"),
        "role_type": "external",  # default; admin re-classifies internals
    }
```

### Step 3: adapter

```python
async def list_users(self, cursor: str | None = None) -> ConnectorPage:
    client = await self._get_client()
    rows = await client.fetch_rows(
        schema="procore",
        table="users",
        cursor_col="procore_id",  # users lack updated_at too
        cursor_value=cursor,
        limit=DEFAULT_PAGE_SIZE,
    )
    items = [build_user_payload(r) for r in rows]
    next_cursor = items[-1]["id"] if items else None
    return ConnectorPage(items=items, next_cursor=next_cursor)
```

### Step 4: canonical writer

```python
async def _write_users(db: AsyncSession, row: dict[str, Any]) -> UUID:
    cols = list(row.keys())
    col_sql = ", ".join(cols)
    val_sql = ", ".join(f":{c}" for c in cols)
    update_sql = ", ".join(
        f"{c} = EXCLUDED.{c}" for c in cols
        if c not in ("email",)  # email is the natural key
    )
    sql = text(f"""
        INSERT INTO rex.people (id, {col_sql})
        VALUES (gen_random_uuid(), {val_sql})
        ON CONFLICT (email) DO UPDATE SET {update_sql}
        RETURNING id
    """)
    res = await db.execute(sql, row)
    return res.scalar_one()

_CANONICAL_WRITERS["users"] = _write_users

_RESOURCE_CONFIG["users"] = {
    "raw_table": "users_raw",
    "map_fn": mapper.map_user,
    "canonical_table": "people",
    "source_table": "procore.users",
    "fetch_fn_name": "list_users",
}
```

**Prerequisite:** `rex.people.email` must have a unique constraint. Check rex2_canonical_ddl.sql. Most likely already does — verify.

### Step 5: Orchestrator branch

The same "no parent-project scope" branch added for projects applies here. Keep the branch generic:

```python
if resource_type in ("projects", "users", "vendors"):
    # Resources not scoped by parent project — fetch all, upsert.
    adapter = ProcoreAdapter(...)
    fetch_fn = getattr(adapter, cfg["fetch_fn_name"])
    page = await fetch_fn(cursor=cursor)
    ...
```

### Step 6: Test + commit

Test asserts 3 seeded procore.users land in rex.people with matching emails. Commit:

```bash
git commit -m "feat(connectors): users resource sync (procore.users -> rex.people)"
```

---

## Task 4: `vendors` sync (procore.vendors -> rex.companies)

**Why vendors:** 619 rows of real data + insurance expiration columns that feed the Wave 1 `vendor_compliance` action (currently live but reading from Rex OS's own seeded data).

**Files:**
- Modify: `payloads.py` — add `build_vendor_payload`
- Modify: `mapper.py` — add `map_vendor`
- Modify: `adapter.py` — add `list_vendors` (currently doesn't exist as a base method — may need to extend `ConnectorAdapter` ABC, or treat as a non-standard method. Simplest: add a `list_vendors` method to `ProcoreAdapter` only, and route through it via the orchestrator's `cfg["fetch_fn_name"]` which is duck-typed.)
- Modify: `orchestrator.py` — `_write_vendors` + `_RESOURCE_CONFIG["vendors"]`
- Test: same shape

### Step 1: payload builder (compact subset of the 57 fields)

```python
def build_vendor_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row["procore_id"]),
        "project_source_id": None,
        "vendor_name": row.get("vendor_name") or row.get("company_name"),
        "trade_name": row.get("trade_name"),
        "email": row.get("email_address"),
        "phone": row.get("business_phone") or row.get("mobile_phone"),
        "website": row.get("website"),
        "address": row.get("address"),
        "city": row.get("city"),
        "state_code": row.get("state_code"),
        "zip_code": row.get("zip_code"),
        "is_active": row.get("is_active"),
        "license_number": row.get("license_number"),
        "insurance_expiration_date": _iso(row.get("insurance_expiration_date")),
        "insurance_gl_expiration_date": _iso(row.get("insurance_gl_expiration_date")),
        "insurance_wc_expiration_date": _iso(row.get("insurance_wc_expiration_date")),
        "insurance_auto_expiration_date": _iso(row.get("insurance_auto_expiration_date")),
        "created_at": _iso(row.get("created_at")),
        "updated_at": _iso(row.get("updated_at")),
    }
```

### Step 2: mapper

```python
def map_vendor(raw: dict[str, Any]) -> dict[str, Any]:
    """procore.vendors -> rex.companies row dict.
    
    rex.companies NOT NULL: name, company_type. company_type enum:
    subcontractor|supplier|architect|engineer|owner|gc|consultant.
    We default to 'subcontractor' — admin re-classifies."""
    return {
        "name": raw.get("vendor_name") or "(unnamed vendor)",
        "company_type": "subcontractor",
        "trade": raw.get("trade_name"),
        "email": raw.get("email"),
        "phone": raw.get("phone"),
        "address": raw.get("address"),
        "city": raw.get("city"),
        "state": raw.get("state_code"),
        "website": raw.get("website"),
        "license_number": raw.get("license_number"),
        "insurance_expiry": _iso_date(raw.get("insurance_gl_expiration_date") or raw.get("insurance_expiration_date")),
        "insurance_carrier": None,  # procore.vendors doesn't carry carrier name
    }
```

### Step 3-6: follow Task 3's pattern

### Step 7: Test + commit

```bash
git commit -m "feat(connectors): vendors resource sync (procore.vendors -> rex.companies)"
```

---

## Task 5: Full regression + PR + deploy + smoke

### Step 1: Run full backend suite

```
cd backend && py -m pytest tests/ -q --tb=no
```

Expected: previous 794 + new tests for projects/users/vendors + registry-refactor regression. Target: ~810-815 passing.

### Step 2: Push branch + PR

```
git push -u origin feat/phase4a-resource-rollout
gh pr create --base main --title "feat: Phase 4a — Procore resource rollout (projects, users, vendors)" --body <heredoc>
```

PR description should note:
- Depends on Phase 4 RFI pipeline (merged).
- Adds 3 resources with real Rex App data: projects (8), users (615), vendors (619).
- Registry refactor to `_upsert_canonical` unblocks Phase 4b.
- Deferred: submittals, daily_logs, tasks, change_events, commitments, budget, documents (empty in Rex App).

### Step 3: CI → merge → demo redeploy → prod auto-deploy → smoke all 3 resources

Follow the Phase 5 playbook:
1. `gh pr checks --watch`
2. `gh pr merge <n> --merge`
3. `railway link --environment demo --service rex-os && railway redeploy --yes --service rex-os`
4. Poll `/api/version` until both demo + prod reflect the merge commit.
5. Smoke: trigger `POST /api/connectors/<procore_account>/sync/projects` on demo, verify 8 rows land in `rex.projects`. Repeat for `users` (615 rows) and `vendors` (619 rows).
6. Railway logs two passes, confirm clean startup.
7. Update `docs/SESSION_HANDOFF_2026_04_21.md` (or create `SESSION_HANDOFF_2026_04_22.md`) noting Phase 4a shipped + what's deferred to Phase 4b.

---

## Follow-ups (Phase 4b — separate plan)

- **Remaining 6 resources:** submittals, daily_logs, schedule_tasks (tasks), change_events, commitments, budget_line_items, documents. Blocked until the old rex-procore cron populates them OR Rex OS gets direct Procore API access.
- **People-FK resolution enrichment:** once `rex.people` is populated from procore.users, a one-time script can back-fill `rex.rfis.assigned_to` / `ball_in_court` by matching the raw payload's name strings. Can run as a cron or an admin endpoint.
- **Per-project transaction wrapping** (Phase 4 final-review item #2): still outstanding — bundle with Phase 4b.
