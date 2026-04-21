# backend/app/services/ai/tools/registry.py
"""Tool registry — aggregates all ActionSpec instances into one lookup."""
from __future__ import annotations

from app.services.ai.tools.base import ActionSpec

from app.services.ai.tools import (
    create_task as _create_task,
    update_task_status as _update_task_status,
    create_note as _create_note,
    answer_rfi as _answer_rfi,
    save_meeting_packet as _save_meeting_packet,
    save_draft as _save_draft,
    create_alert as _create_alert,
    delete_task as _delete_task,
    delete_note as _delete_note,
)

_REGISTER: list[ActionSpec] = [
    _create_task.SPEC,
    _update_task_status.SPEC,
    _create_note.SPEC,
    _answer_rfi.SPEC,
    _save_meeting_packet.SPEC,
    _save_draft.SPEC,
    _create_alert.SPEC,
    _delete_task.SPEC,
    _delete_note.SPEC,
]

_BY_SLUG: dict[str, ActionSpec] = {s.slug: s for s in _REGISTER}


def get(slug: str) -> ActionSpec | None:
    return _BY_SLUG.get(slug)


def all_specs() -> list[ActionSpec]:
    return list(_REGISTER)


def list_schemas() -> list[dict]:
    """The tool schemas to pass to Anthropic's messages.stream(tools=...)."""
    return [
        {
            "name": s.slug,
            **s.tool_schema,  # contains description + input_schema
        }
        for s in _REGISTER
    ]


__all__ = ["get", "all_specs", "list_schemas"]
