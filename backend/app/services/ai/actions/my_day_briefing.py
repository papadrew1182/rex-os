"""my_day_briefing — personalized digest from rex.v_myday.

Always user-scoped (v_myday is already keyed by user_account_id).
project_id (if set) narrows the digest to that project.
"""
from __future__ import annotations

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    _render_fragment,
)


class Handler:
    slug = "my_day_briefing"

    async def run(self, ctx: ActionContext) -> ActionResult:
        row = await ctx.conn.fetchrow(
            """
            SELECT
                COUNT(*)                                                   AS total_items,
                COUNT(*) FILTER (WHERE due_date::date < CURRENT_DATE)      AS overdue,
                COUNT(*) FILTER (WHERE due_date::date = CURRENT_DATE)      AS due_today,
                COUNT(*) FILTER (WHERE item_type = 'rfi')                  AS rfis_count,
                COUNT(*) FILTER (WHERE item_type = 'task')                 AS tasks_count,
                COUNT(*) FILTER (WHERE item_type = 'pending_decision')     AS pending_decisions_count,
                COUNT(*) FILTER (WHERE item_type = 'meeting_action_item')  AS meeting_action_items_count
            FROM rex.v_myday
            WHERE user_account_id = $1::uuid
              AND ($2::uuid IS NULL OR project_id = $2::uuid)
            """,
            ctx.user_account_id, ctx.project_id,
        )
        sample = await ctx.conn.fetch(
            """
            SELECT
                v.item_type                 AS item_type,
                v.title                     AS title,
                v.priority                  AS priority,
                v.status                    AS status,
                v.due_date                  AS due_date,
                p.name                      AS project_name
            FROM rex.v_myday v
            JOIN rex.projects p ON p.id = v.project_id
            WHERE v.user_account_id = $1::uuid
              AND ($2::uuid IS NULL OR v.project_id = $2::uuid)
            ORDER BY v.due_date ASC NULLS LAST
            LIMIT 10
            """,
            ctx.user_account_id, ctx.project_id,
        )
        sample_rows = [dict(r) for r in sample]
        display_rows = [
            {
                **r,
                "due_date": (
                    r["due_date"].isoformat() if r.get("due_date") else "(no due date)"
                ),
            }
            for r in sample_rows
        ]

        total = int(row["total_items"] or 0)
        stats = {
            "total_items": total,
            "overdue": int(row["overdue"] or 0),
            "due_today": int(row["due_today"] or 0),
            "by_type": {
                "rfi":                 int(row["rfis_count"] or 0),
                "task":                int(row["tasks_count"] or 0),
                "pending_decision":    int(row["pending_decisions_count"] or 0),
                "meeting_action_item": int(row["meeting_action_items_count"] or 0),
            },
        }

        summary = [
            f"Items on your plate: {total}",
            f"Overdue: {stats['overdue']}, Due today: {stats['due_today']}",
            f"By type: {stats['by_type']['rfi']} RFI(s), "
            f"{stats['by_type']['task']} task(s), "
            f"{stats['by_type']['pending_decision']} decision(s), "
            f"{stats['by_type']['meeting_action_item']} meeting item(s)",
        ]

        return ActionResult(
            stats=stats,
            sample_rows=sample_rows,
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=(
                    "your items (project-scoped)" if ctx.project_id
                    else "your items across all your projects"
                ),
                summary_lines=summary,
                table_header=["project_name", "item_type", "title", "priority", "status", "due_date"],
                rows=display_rows,
                empty_message="Nothing on your plate right now — inbox zero.",
            ),
        )


__all__ = ["Handler"]
