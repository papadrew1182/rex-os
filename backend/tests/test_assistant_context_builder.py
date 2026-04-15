"""Unit tests for canonical role normalization in the context builder."""

from __future__ import annotations

from uuid import uuid4

from app.services.ai.context_builder import (
    CANONICAL_ROLES,
    ContextBuilder,
    normalize_role,
    normalize_roles,
)


def test_canonical_roles_are_the_exact_six():
    assert set(CANONICAL_ROLES) == {
        "VP",
        "PM",
        "GENERAL_SUPER",
        "LEAD_SUPER",
        "ASSISTANT_SUPER",
        "ACCOUNTANT",
    }


def test_normalize_vp_pm_collapses_to_vp():
    assert normalize_role("VP_PM") == "VP"
    assert normalize_role("vp_pm") == "VP"


def test_normalize_project_manager_variants():
    assert normalize_role("project_manager") == "PM"
    assert normalize_role("Project Manager") == "PM"
    assert normalize_role("PM") == "PM"


def test_normalize_general_super_variants():
    assert normalize_role("General_Superintendent") == "GENERAL_SUPER"
    assert normalize_role("general superintendent") == "GENERAL_SUPER"
    assert normalize_role("GENERAL_SUPER") == "GENERAL_SUPER"


def test_normalize_lead_super_variants():
    assert normalize_role("Lead_Superintendent") == "LEAD_SUPER"


def test_normalize_assistant_super_variants():
    assert normalize_role("Assistant_Superintendent") == "ASSISTANT_SUPER"


def test_normalize_accountant_variants():
    assert normalize_role("accounting") == "ACCOUNTANT"
    assert normalize_role("Accountant") == "ACCOUNTANT"


def test_normalize_unknown_role_returns_none():
    assert normalize_role("CEO") is None
    assert normalize_role("") is None
    assert normalize_role(None) is None


def test_normalize_roles_preserves_priority_and_dedupes():
    assert normalize_roles(["project_manager", "VP_PM", "unknown"]) == ["VP", "PM"]


def test_build_user_injects_default_pm_when_no_role_resolved():
    builder = ContextBuilder()
    user = builder.build_user(
        user_id=uuid4(),
        email="nobody@example.com",
        full_name="Test User",
        legacy_role="unknown_role",
    )
    assert user.primary_role_key == "PM"
    assert "PM" in user.role_keys


def test_build_user_normalizes_legacy_global_role():
    builder = ContextBuilder()
    user = builder.build_user(
        user_id=uuid4(),
        email="alex@example.com",
        full_name="Alex",
        legacy_role="VP_PM",
    )
    assert user.primary_role_key == "VP"
    assert user.legacy_role_aliases == ["VP_PM"]


def test_build_context_injects_role_and_project_lines_into_prompt():
    builder = ContextBuilder()
    user = builder.build_user(
        user_id=uuid4(),
        email="u@e.com",
        full_name=None,
        legacy_role="vp",
    )
    from app.schemas.assistant import PageContext

    ctx = builder.build_context(
        user=user,
        project_id=None,
        page_context=PageContext(route="/x"),
        system_prompt="BASE",
    )
    assert "BASE" in ctx.system_prompt
    assert "VP" in ctx.system_prompt
    assert "No active project context." in ctx.system_prompt
