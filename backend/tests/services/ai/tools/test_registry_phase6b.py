"""Phase 6b: registry includes all 9 tools (4 from 6a + 5 new)."""
from __future__ import annotations

from app.services.ai.tools import registry


def test_registry_contains_phase6b_wave1_tools():
    slugs = [s.slug for s in registry.all_specs()]
    for slug in [
        "create_task", "update_task_status", "create_note", "answer_rfi",
        "save_meeting_packet", "save_draft", "create_alert",
        "delete_task", "delete_note",
    ]:
        assert slug in slugs, f"{slug} not registered"


def test_registry_all_wave1_tools_are_auto_pass():
    for slug in ["save_meeting_packet", "save_draft", "create_alert",
                  "delete_task", "delete_note"]:
        spec = registry.get(slug)
        assert spec is not None
        assert spec.fires_external_effect is False
        assert spec.compensator is not None


def test_registry_phase6a_retrofits_have_compensators():
    for slug in ["create_task", "update_task_status", "create_note"]:
        spec = registry.get(slug)
        assert spec is not None
        assert spec.compensator is not None


def test_registry_answer_rfi_has_no_compensator():
    spec = registry.get("answer_rfi")
    assert spec is not None
    assert spec.compensator is None
