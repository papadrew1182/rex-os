"""Shared types + helpers for quick-action handlers.

A handler is a plain object implementing ``QuickActionHandler``:
just a ``slug`` class attribute and an async ``run(ctx)`` method.
Handlers MUST NOT raise — they should catch their own DB errors and
return an ``ActionResult`` with a graceful ``prompt_fragment``. The
dispatcher wraps each call in its own try/except as defense-in-depth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

import asyncpg


@dataclass
class ActionContext:
    """Everything a handler needs to run.

    Attributes:
        conn: a live asyncpg connection the handler may use for reads.
            The caller (dispatcher) owns the connection's lifecycle.
        user_account_id: rex.user_accounts.id of the requester.
        project_id: optional project scope. If None, the handler runs
            in portfolio mode and should scope to the user's accessible
            projects via ``resolve_scope_project_ids``.
        params: arbitrary handler params from the chat request; most
            handlers ignore this today.
    """
    conn: asyncpg.Connection
    user_account_id: UUID
    project_id: UUID | None = None
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    """What a handler returns.

    Attributes:
        stats: deterministic numbers the LLM should cite verbatim.
            e.g., ``{"total_open": 23, "oldest_days": 19}``.
        sample_rows: up to 10 representative rows for the markdown
            table in ``prompt_fragment``. Also exposed here for any
            future structured-return consumer.
        prompt_fragment: pre-rendered markdown block. Appended to the
            chat's system prompt as-is. MUST start with a
            ``## Quick action data: <slug>`` header for visual
            separation from the base prompt.
    """
    stats: dict[str, Any] = field(default_factory=dict)
    sample_rows: list[dict] = field(default_factory=list)
    prompt_fragment: str = ""


class QuickActionHandler(Protocol):
    """Handler contract. Each module under ``actions/`` exposes a
    ``Handler`` class implementing this protocol."""

    slug: str

    async def run(self, ctx: ActionContext) -> ActionResult:
        ...


async def resolve_scope_project_ids(
    conn: asyncpg.Connection,
    *,
    user_account_id: UUID,
    project_id: UUID | None,
) -> list[UUID]:
    """Resolve a handler's project-scope filter list.

    If ``project_id`` is given, returns ``[project_id]`` unconditionally
    — the caller upstream has already validated page-context access.
    If ``project_id`` is None, returns the active project_ids the user
    is assigned to via ``rex.v_user_project_assignments``.

    The dispatcher passes the result into handler SQL as an array
    parameter; handlers use ``WHERE project_id = ANY($N::uuid[])``.
    """
    if project_id is not None:
        return [project_id]

    rows = await conn.fetch(
        "SELECT project_id FROM rex.v_user_project_assignments "
        "WHERE user_account_id = $1::uuid AND is_active = true",
        user_account_id,
    )
    return [r["project_id"] for r in rows]


def _render_fragment(
    *,
    slug: str,
    scope_label: str,
    summary_lines: list[str],
    table_header: list[str],
    rows: list[dict],
    empty_message: str,
) -> str:
    """Render the standard prompt_fragment template.

    Layout:

        ## Quick action data: <slug>

        Scope: <scope_label>

        Summary:
        - <line 1>
        - <line 2>
        ...

        Top rows:
        | col | col | col |
        | --- | --- | --- |
        | v | v | v |

        Use these numbers verbatim in your response; do not recalculate them.

    When rows is empty, replaces the table with ``empty_message``.
    """
    parts = [
        f"## Quick action data: {slug}",
        "",
        f"Scope: {scope_label}",
        "",
        "Summary:",
        *[f"- {line}" for line in summary_lines],
        "",
    ]
    if rows:
        header_line = "| " + " | ".join(table_header) + " |"
        sep_line = "| " + " | ".join("---" for _ in table_header) + " |"
        body_lines = []
        for r in rows:
            body_lines.append(
                "| " + " | ".join(str(r.get(h, "")) for h in table_header) + " |"
            )
        parts.extend(["Top rows:", header_line, sep_line, *body_lines, ""])
    else:
        parts.extend([empty_message, ""])

    parts.append("Use these numbers verbatim in your response; do not recalculate them.")
    return "\n".join(parts)


__all__ = [
    "ActionContext",
    "ActionResult",
    "QuickActionHandler",
    "resolve_scope_project_ids",
    "_render_fragment",
]
