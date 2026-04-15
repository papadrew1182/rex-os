"""Session 2 RBAC alias mapping tests.

Covers:
  - all six canonical roles seeded with correct slug/display_name
  - VP_PM -> PM ambiguity resolution documented in
    baseline-reconciliation.md section 6
  - legacy alias mapping for General_Superintendent, Lead_Superintendent,
    Asst_Superintendent, lowercase vp, etc.
  - role_permissions grants land per role (VP has all, PM has all-except-admin)
"""

from __future__ import annotations

import pytest
from sqlalchemy import text


CANONICAL_ROLES = [
    ("VP",              "Vice President"),
    ("PM",              "Project Manager"),
    ("GENERAL_SUPER",   "General Superintendent"),
    ("LEAD_SUPER",      "Lead Superintendent"),
    ("ASSISTANT_SUPER", "Assistant Superintendent"),
    ("ACCOUNTANT",      "Project Accountant"),
]

LEGACY_ALIAS_EXPECTATIONS = [
    ("General_Superintendent", "GENERAL_SUPER"),
    ("Lead_Superintendent",    "LEAD_SUPER"),
    ("Asst_Superintendent",    "ASSISTANT_SUPER"),
    ("vp",                     "VP"),
    ("Vice_President",         "VP"),
    ("Project_Manager",        "PM"),
    ("Project_Accountant",     "ACCOUNTANT"),
    # The critical ambiguity decision — VP_PM MUST resolve to PM, not VP.
    ("VP_PM",                  "PM"),
    ("VP/PM",                  "PM"),
]


async def test_all_canonical_roles_seeded(rollback_client):
    from app.database import async_session_factory
    async with async_session_factory() as db:
        rows = (await db.execute(
            text(
                "SELECT slug, display_name, is_system FROM rex.roles "
                "ORDER BY sort_order"
            )
        )).mappings().all()
        slugs = [r["slug"] for r in rows]
        for slug, display in CANONICAL_ROLES:
            assert slug in slugs, f"canonical role {slug} not seeded"
        for r in rows:
            if r["slug"] in {s for s, _ in CANONICAL_ROLES}:
                assert r["is_system"] is True, f"{r['slug']} should be is_system=true"


async def test_legacy_aliases_resolve_correctly(rollback_client):
    from app.database import async_session_factory
    async with async_session_factory() as db:
        for alias, expected in LEGACY_ALIAS_EXPECTATIONS:
            row = (await db.execute(
                text("SELECT canonical_role_slug FROM rex.role_aliases WHERE alias = :a"),
                {"a": alias},
            )).mappings().first()
            assert row is not None, f"alias {alias!r} not seeded"
            assert row["canonical_role_slug"] == expected, (
                f"alias {alias!r} should resolve to {expected}, got {row['canonical_role_slug']}"
            )


async def test_vp_pm_ambiguity_documented(rollback_client):
    """VP_PM alias must carry a notes entry explaining the ambiguity decision."""
    from app.database import async_session_factory
    async with async_session_factory() as db:
        row = (await db.execute(
            text(
                "SELECT canonical_role_slug, notes FROM rex.role_aliases WHERE alias = 'VP_PM'"
            )
        )).mappings().first()
        assert row is not None
        assert row["canonical_role_slug"] == "PM"
        assert row["notes"] and len(row["notes"]) > 20, (
            f"VP_PM alias must have documented notes, got {row['notes']!r}"
        )


async def test_vp_role_has_all_permissions(rollback_client):
    """VP role gets all 15 canonical permissions."""
    from app.database import async_session_factory
    async with async_session_factory() as db:
        total = (await db.execute(
            text("SELECT COUNT(*) FROM rex.permissions")
        )).scalar_one()
        vp_count = (await db.execute(
            text(
                "SELECT COUNT(*) FROM rex.role_permissions rp "
                "JOIN rex.roles r ON r.id = rp.role_id "
                "WHERE r.slug = 'VP'"
            )
        )).scalar_one()
        assert vp_count == total, (
            f"VP should have all {total} permissions, got {vp_count}"
        )


async def test_pm_role_excludes_admin(rollback_client):
    """PM has everything EXCEPT admin.*. This is how VP_PM ambiguity stays safe."""
    from app.database import async_session_factory
    async with async_session_factory() as db:
        perms = (await db.execute(
            text(
                "SELECT p.slug FROM rex.role_permissions rp "
                "JOIN rex.roles r ON r.id = rp.role_id "
                "JOIN rex.permissions p ON p.id = rp.permission_id "
                "WHERE r.slug = 'PM'"
            )
        )).scalars().all()
        assert perms, "PM has no permissions"
        admins = [p for p in perms if p.startswith("admin.")]
        assert not admins, f"PM should not have admin.* permissions, got {admins}"
        assert "portfolio.view" in perms, "PM must have portfolio.view (VP_PM fallback)"
        assert "financials.view" in perms


async def test_accountant_role_has_financial_permissions(rollback_client):
    from app.database import async_session_factory
    async with async_session_factory() as db:
        perms = (await db.execute(
            text(
                "SELECT p.slug FROM rex.role_permissions rp "
                "JOIN rex.roles r ON r.id = rp.role_id "
                "JOIN rex.permissions p ON p.id = rp.permission_id "
                "WHERE r.slug = 'ACCOUNTANT'"
            )
        )).scalars().all()
        assert "financials.view" in perms
        assert "portfolio.view" in perms
        # Accountant should NOT have schedule.view (not their surface)
        assert "schedule.view" not in perms, (
            "Accountant should not have schedule.view — finance-only role"
        )
