"""critical_path_delays — critical schedule activities with variance_days > 2.

Queries rex.schedule_activities joined to rex.schedules (for project_id).
rex.v_schedule is a per-project rollup (provides only counts); we need
per-activity detail so we bypass the view for this handler.
"""
from __future__ import annotations

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    resolve_scope_project_ids,
    _render_fragment,
)


class Handler:
    slug = "critical_path_delays"

    async def run(self, ctx: ActionContext) -> ActionResult:
        project_ids = await resolve_scope_project_ids(
            ctx.conn, user_account_id=ctx.user_account_id, project_id=ctx.project_id,
        )
        if not project_ids:
            return self._empty(ctx, 0)

        row = await ctx.conn.fetchrow(
            """
            SELECT
                COUNT(*)                                     AS critical_tasks_delayed,
                COALESCE(MAX(sa.variance_days), 0)           AS worst_delay_days,
                COUNT(DISTINCT s.project_id)                 AS projects_with_critical_delays
            FROM rex.schedule_activities sa
            JOIN rex.schedules s ON s.id = sa.schedule_id
            WHERE s.project_id = ANY($1::uuid[])
              AND sa.is_critical = true
              AND sa.variance_days > 2
            """,
            project_ids,
        )
        sample = await ctx.conn.fetch(
            """
            SELECT
                p.name         AS project_name,
                sa.name        AS task_name,
                sa.start_date  AS start_date,
                sa.end_date    AS end_date,
                sa.variance_days AS variance_days
            FROM rex.schedule_activities sa
            JOIN rex.schedules s ON s.id = sa.schedule_id
            JOIN rex.projects p ON p.id = s.project_id
            WHERE s.project_id = ANY($1::uuid[])
              AND sa.is_critical = true
              AND sa.variance_days > 2
            ORDER BY sa.variance_days DESC
            LIMIT 10
            """,
            project_ids,
        )
        sample_rows = [dict(r) for r in sample]
        display_rows = [
            {
                **r,
                "start_date": r["start_date"].isoformat() if r.get("start_date") else "",
                "end_date": r["end_date"].isoformat() if r.get("end_date") else "",
            }
            for r in sample_rows
        ]

        stats = {
            "critical_tasks_delayed": int(row["critical_tasks_delayed"] or 0),
            "worst_delay_days": int(row["worst_delay_days"] or 0),
            "projects_with_critical_delays": int(row["projects_with_critical_delays"] or 0),
        }

        summary = [
            f"Critical path tasks delayed (>2d): {stats['critical_tasks_delayed']}",
            f"Worst delay: {stats['worst_delay_days']} day(s)",
            f"Projects affected: {stats['projects_with_critical_delays']}",
        ]

        return ActionResult(
            stats=stats,
            sample_rows=sample_rows,
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, len(project_ids)),
                summary_lines=summary,
                table_header=["project_name", "task_name", "start_date", "end_date", "variance_days"],
                rows=display_rows,
                empty_message="No critical-path tasks with variance > 2 days in the selected scope.",
            ),
        )

    def _empty(self, ctx, n_projects):
        return ActionResult(
            stats={"critical_tasks_delayed": 0, "worst_delay_days": 0, "projects_with_critical_delays": 0},
            sample_rows=[],
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, n_projects),
                summary_lines=["Critical path tasks delayed: 0"],
                table_header=[],
                rows=[],
                empty_message="No critical-path tasks with variance > 2 days in the selected scope.",
            ),
        )

    @staticmethod
    def _scope_label(ctx, n_projects):
        if ctx.project_id is not None:
            return "single project (page scope)"
        return f"portfolio across {n_projects} projects the user has access to"


__all__ = ["Handler"]
