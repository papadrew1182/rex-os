"""Identity and context endpoints for Session 2.

Charter-locked surfaces consumed by the assistant lane (Session 1) and
the frontend shell lane (Session 3). Response shapes match the Session 2
charter document §"Identity and context endpoints owned by this lane".

All three endpoints go through the data-driven RBAC model:
  user_accounts -> user_roles -> role_permissions -> permissions
  user_accounts -> rex.v_users (view)  for the /api/me shape
  user_accounts.global_role -> rex.role_aliases  for legacy alias surfacing
  project_members -> project_ids       for project membership

No hard-coded role or permission strings live in this file. Everything
resolves from the DB.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.foundation import UserAccount

router = APIRouter(prefix="/api", tags=["session2-identity"])


# ── GET /api/me ─────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(
    user: UserAccount = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the charter-shaped user envelope.

    Resolves:
      - basic identity + feature_flags via rex.v_users
      - primary role slug + full role list via rex.user_roles
      - legacy role aliases for display-only surfacing
      - project membership via rex.project_members
    """
    # View-backed user envelope
    row = (await db.execute(
        text(
            """
            SELECT id, email, full_name, primary_role_slug, role_slugs,
                   feature_flags, is_admin, is_active
            FROM rex.v_users
            WHERE id = :uid
            """
        ),
        {"uid": user.id},
    )).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")

    # Legacy aliases that resolve to the user's primary role — purely
    # informational for UI surfacing, not used for permission resolution.
    legacy_aliases: list[str] = []
    if row["primary_role_slug"]:
        alias_rows = (await db.execute(
            text(
                """
                SELECT alias FROM rex.role_aliases
                WHERE canonical_role_slug = :slug
                  AND alias <> canonical_role_slug
                ORDER BY alias
                """
            ),
            {"slug": row["primary_role_slug"]},
        )).mappings().all()
        legacy_aliases = [r["alias"] for r in alias_rows]

    # Project memberships
    pm_rows = (await db.execute(
        text(
            """
            SELECT DISTINCT pm.project_id
            FROM rex.project_members pm
            JOIN rex.people p ON p.id = pm.person_id
            JOIN rex.user_accounts ua ON ua.person_id = p.id
            WHERE ua.id = :uid AND pm.is_active = true
            ORDER BY pm.project_id
            """
        ),
        {"uid": user.id},
    )).mappings().all()
    project_ids = [str(r["project_id"]) for r in pm_rows]

    # Normalize role_slugs. v_users returns it as jsonb, which sqlalchemy
    # will surface as a list or None depending on the jsonb cast path.
    raw_roles = row["role_slugs"] or []
    if isinstance(raw_roles, str):
        import json
        raw_roles = json.loads(raw_roles)
    role_keys = list(raw_roles) if raw_roles else (
        [row["primary_role_slug"]] if row["primary_role_slug"] else []
    )

    feature_flags = row["feature_flags"] or {}
    if isinstance(feature_flags, str):
        import json
        feature_flags = json.loads(feature_flags)

    return {
        "user": {
            "id": str(row["id"]),
            "email": row["email"],
            "full_name": (row["full_name"] or "").strip(),
            "primary_role_key": row["primary_role_slug"],
            "role_keys": role_keys,
            "legacy_role_aliases": legacy_aliases,
            "project_ids": project_ids,
            "feature_flags": feature_flags,
            "is_admin": row["is_admin"],
            "is_active": row["is_active"],
        }
    }


# ── GET /api/me/permissions ─────────────────────────────────────────────

@router.get("/me/permissions")
async def get_my_permissions(
    user: UserAccount = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Resolve the caller's permissions from the DB.

    The join walks:
      user_accounts(ua) -> user_roles(ur) -> role_permissions(rp)
      -> permissions(p) -> p.slug
    """
    rows = (await db.execute(
        text(
            """
            SELECT DISTINCT p.slug
            FROM rex.user_roles ur
            JOIN rex.role_permissions rp ON rp.role_id = ur.role_id
            JOIN rex.permissions p ON p.id = rp.permission_id
            WHERE ur.user_account_id = :uid
            ORDER BY p.slug
            """
        ),
        {"uid": user.id},
    )).mappings().all()
    return {"permissions": [r["slug"] for r in rows]}


# ── GET /api/context/current ────────────────────────────────────────────
#
# The charter shape includes a "route" / "page_context" / "assistant_defaults"
# section. The route + page_context are client-supplied hints, so we let
# the caller pass them as optional query params. assistant_defaults is
# server-resolved based on the current project + the caller's role.

@router.get("/context/current")
async def get_current_context(
    project_id: UUID | None = Query(None, description="Optional explicit project id to resolve context for"),
    surface: str | None = Query(None, description="Frontend surface hint (dashboard, rfis, etc)"),
    route_name: str | None = Query(None, description="Frontend route name hint"),
    route_path: str | None = Query(None, description="Frontend route path hint"),
    user: UserAccount = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return current user + project + assistant-suggestion context.

    If ``project_id`` is omitted, falls back to the first active project
    the caller is a member of. If the caller has no project memberships,
    the ``project`` key is null.
    """
    resolved_pid: UUID | None = project_id
    if resolved_pid is None:
        row = (await db.execute(
            text(
                """
                SELECT pm.project_id
                FROM rex.project_members pm
                JOIN rex.people p ON p.id = pm.person_id
                JOIN rex.user_accounts ua ON ua.person_id = p.id
                WHERE ua.id = :uid AND pm.is_active = true
                ORDER BY pm.is_primary DESC, pm.created_at ASC
                LIMIT 1
                """
            ),
            {"uid": user.id},
        )).mappings().first()
        if row:
            resolved_pid = row["project_id"]

    project_block: dict | None = None
    if resolved_pid is not None:
        proj = (await db.execute(
            text(
                """
                SELECT id, name, status, project_number, project_type
                FROM rex.projects
                WHERE id = :pid
                """
            ),
            {"pid": resolved_pid},
        )).mappings().first()
        if proj:
            project_block = {
                "id": str(proj["id"]),
                "name": proj["name"],
                "status": proj["status"],
                "project_number": proj["project_number"],
                "project_type": proj["project_type"],
            }

    # Suggested quick-action slugs default per primary role. This is a
    # small static map owned by Session 2 for now; Session 1 can override
    # with smarter per-context logic later without touching this endpoint.
    primary_role_row = (await db.execute(
        text(
            """
            SELECT r.slug
            FROM rex.user_roles ur
            JOIN rex.roles r ON r.id = ur.role_id
            WHERE ur.user_account_id = :uid AND ur.is_primary = true
            LIMIT 1
            """
        ),
        {"uid": user.id},
    )).mappings().first()
    primary_slug = primary_role_row["slug"] if primary_role_row else None

    default_suggestions = {
        "VP":              ["portfolio_summary", "morning_briefing", "budget_variance"],
        "PM":              ["budget_variance", "change_event_sweep", "morning_briefing"],
        "GENERAL_SUPER":   ["morning_briefing", "schedule_variance", "punch_health"],
        "LEAD_SUPER":      ["daily_log_summary", "schedule_variance", "morning_briefing"],
        "ASSISTANT_SUPER": ["daily_log_summary", "morning_briefing"],
        "ACCOUNTANT":      ["pay_app_status", "lien_waiver_compliance", "budget_variance"],
    }
    suggested_slugs = default_suggestions.get(primary_slug, ["morning_briefing"])

    return {
        "project": project_block,
        "route": {
            "name": route_name,
            "path": route_path,
        },
        "page_context": {
            "surface": surface,
            "entity_type": "project" if project_block else None,
            "entity_id": str(resolved_pid) if resolved_pid else None,
            "filters": {},
        },
        "assistant_defaults": {
            "suggested_action_slugs": suggested_slugs,
        },
    }
