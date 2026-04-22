"""Phase 6b Wave 2: registry includes all 14 tools (9 prior + 5 new)."""
from __future__ import annotations

from app.services.ai.tools import registry


WAVE2_SLUGS = [
    "create_change_event", "create_pco", "pay_application",
    "lien_waiver", "create_decision",
]

WAVE2_FINANCIAL = [
    "create_change_event", "create_pco", "pay_application", "lien_waiver",
]


def test_registry_contains_wave2_tools():
    slugs = [s.slug for s in registry.all_specs()]
    for slug in WAVE2_SLUGS:
        assert slug in slugs, f"{slug} not registered"


def test_registry_financial_tools_fire_external_effect():
    for slug in WAVE2_FINANCIAL:
        spec = registry.get(slug)
        assert spec is not None
        assert spec.fires_external_effect is True, f"{slug} should fire_external_effect=True"
        assert spec.compensator is None, f"{slug} should NOT have a compensator in Wave 2"


def test_registry_create_decision_is_auto_pass():
    spec = registry.get("create_decision")
    assert spec is not None
    assert spec.fires_external_effect is False
    assert spec.compensator is not None, "create_decision must have a compensator"


def test_registry_total_tool_count_is_fourteen():
    assert len(registry.all_specs()) == 14
