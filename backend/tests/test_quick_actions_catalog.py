"""Catalog coverage and normalization-rule tests (Work Packet C).

These tests read the Python source of truth at
``backend/app/data/quick_actions_catalog.py`` and verify every invariant
the charter demands. They run without a DB, so they are cheap to keep
green on every push.
"""

from __future__ import annotations

import pytest

from app.data.quick_actions_catalog import (
    CANONICAL_SLUG_COUNT,
    LEGACY_ALIAS_COUNT,
    QUICK_ACTIONS_CATALOG,
)
from app.services.ai.catalog_import import (
    CANONICAL_ROLE_KEYS,
    CatalogValidationError,
    VALID_READINESS_STATES,
    VALID_RISK_TIERS,
    build_catalog_response_from_source,
    resolve_alias,
    validate_catalog,
)

EXPECTED_SLUG_COUNT = 77
EXPECTED_ALIAS_COUNT = 80


def test_canonical_slug_count_is_77():
    assert CANONICAL_SLUG_COUNT == EXPECTED_SLUG_COUNT


def test_legacy_alias_count_is_80():
    assert LEGACY_ALIAS_COUNT == EXPECTED_ALIAS_COUNT


def test_every_legacy_c_id_from_the_csv_inventory_is_covered():
    """All of C-1..C-79 + C-104 must appear as a legacy alias."""
    expected = {f"C-{i}" for i in range(1, 80)} | {"C-104"}
    actual = {
        alias for entry in QUICK_ACTIONS_CATALOG for alias in entry["legacy_aliases"]
    }
    missing = expected - actual
    extra = actual - expected
    assert not missing, f"missing legacy aliases: {sorted(missing)}"
    assert not extra, f"unexpected legacy aliases: {sorted(extra)}"


def test_slug_uniqueness_across_catalog():
    slugs = [e["slug"] for e in QUICK_ACTIONS_CATALOG]
    assert len(slugs) == len(set(slugs))


def test_legacy_alias_uniqueness_across_catalog():
    aliases = [a for e in QUICK_ACTIONS_CATALOG for a in e["legacy_aliases"]]
    assert len(aliases) == len(set(aliases))


def test_no_legacy_c_id_is_used_as_a_primary_slug():
    """C-* labels must never leak into the slug column."""
    for entry in QUICK_ACTIONS_CATALOG:
        assert not entry["slug"].upper().startswith("C-"), entry["slug"]


def test_submittal_sla_dedupes_C_8_and_C_28():
    entry = _by_slug("submittal_sla")
    assert set(entry["legacy_aliases"]) == {"C-8", "C-28"}


def test_monthly_owner_report_dedupes_C_15_and_C_60():
    entry = _by_slug("monthly_owner_report")
    assert set(entry["legacy_aliases"]) == {"C-15", "C-60"}


def test_rfi_aging_dedupes_C_5_and_C_29():
    """Session 3 mockCatalog parity — documented contract decision."""
    entry = _by_slug("rfi_aging")
    assert set(entry["legacy_aliases"]) == {"C-5", "C-29"}


def test_every_role_visibility_entry_is_a_canonical_role_key():
    for entry in QUICK_ACTIONS_CATALOG:
        for role in entry["role_visibility"]:
            assert role in CANONICAL_ROLE_KEYS, f"{entry['slug']}: {role}"


def test_every_readiness_state_is_in_vocabulary():
    for entry in QUICK_ACTIONS_CATALOG:
        assert entry["readiness_state"] in VALID_READINESS_STATES, entry["slug"]


def test_every_risk_tier_is_in_vocabulary():
    for entry in QUICK_ACTIONS_CATALOG:
        assert entry["risk_tier"] in VALID_RISK_TIERS, entry["slug"]


def test_validate_catalog_accepts_the_source_of_truth():
    validate_catalog()


def test_validate_catalog_rejects_a_duplicate_slug():
    bad = list(QUICK_ACTIONS_CATALOG) + [dict(QUICK_ACTIONS_CATALOG[0])]
    with pytest.raises(CatalogValidationError) as err:
        validate_catalog(bad)
    assert err.value.code == "duplicate_slug"


def test_validate_catalog_rejects_a_non_canonical_role():
    entry = dict(QUICK_ACTIONS_CATALOG[0])
    entry["role_visibility"] = ["VP", "CEO"]  # CEO not canonical
    with pytest.raises(CatalogValidationError) as err:
        validate_catalog([entry])
    assert err.value.code == "non_canonical_role"


def test_validate_catalog_rejects_bad_alias_format():
    entry = dict(QUICK_ACTIONS_CATALOG[0])
    entry["legacy_aliases"] = ["D-99"]  # wrong prefix
    with pytest.raises(CatalogValidationError) as err:
        validate_catalog([entry])
    assert err.value.code == "invalid_alias_format"


def test_resolve_alias_returns_canonical_slug_for_all_dedupe_cases():
    assert resolve_alias("C-8") == "submittal_sla"
    assert resolve_alias("C-28") == "submittal_sla"
    assert resolve_alias("C-15") == "monthly_owner_report"
    assert resolve_alias("C-60") == "monthly_owner_report"
    assert resolve_alias("C-5") == "rfi_aging"
    assert resolve_alias("C-29") == "rfi_aging"


def test_resolve_alias_on_a_canonical_slug_returns_itself():
    assert resolve_alias("budget_variance") == "budget_variance"


def test_resolve_alias_on_an_unknown_identifier_returns_none():
    assert resolve_alias("not_a_real_slug") is None
    assert resolve_alias("C-99999") is None


def test_build_catalog_response_exposes_all_77_entries_for_vp():
    resp = build_catalog_response_from_source(role_keys=["VP"])
    assert len(resp["actions"]) == EXPECTED_SLUG_COUNT


def test_build_catalog_response_filters_by_role_for_accountant():
    resp = build_catalog_response_from_source(role_keys=["ACCOUNTANT"])
    assert len(resp["actions"]) < EXPECTED_SLUG_COUNT
    # Every returned action must be visible to ACCOUNTANT (either explicit
    # or no role restriction at all).
    for a in resp["actions"]:
        if a["role_visibility"]:
            assert "ACCOUNTANT" in a["role_visibility"], a["slug"]


def test_can_run_reflects_readiness_and_enabled_only():
    """Contract decision: can_run is not yet connector-aware."""
    resp = build_catalog_response_from_source()
    for action in resp["actions"]:
        if action["enabled"] and action["readiness_state"] in {"live", "alpha"}:
            assert action["can_run"] is True, action["slug"]
        else:
            assert action["can_run"] is False, action["slug"]


def _by_slug(slug: str) -> dict:
    for entry in QUICK_ACTIONS_CATALOG:
        if entry["slug"] == slug:
            return entry
    raise KeyError(slug)
