"""two_week_lookahead — schedule_activities starting in [today, today+14d]."""
from __future__ import annotations

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    resolve_scope_project_ids,
    _render_fragment,
)


class Handler:
    slug = "two_week_lookahead"

    async def run(self, ctx: ActionContext) -> ActionResult:
        project_ids = await resolve_scope_project_ids(
            ctx.conn, user_account_id=ctx.user_account_id, project_id=ctx.project_id,
        )
        if not project_ids:
            return self._empty(ctx, 0)

        row = await ctx.conn.fetchrow(
            """
            SELECT
                COUNT(*)                                     AS tasks_starting_next_14d,
                COUNT(DISTINCT s.project_id)                 AS projects_with_starts,
                MIN(sa.start_date)                           AS earliest_start
            FROM rex.schedule_activities sa
            JOIN rex.schedules s ON s.id = sa.schedule_id
            WHERE s.project_id = ANY($1::uuid[])
              AND sa.start_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '14 days'
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
                sa.percent_complete AS percent_complete
            FROM rex.schedule_activities sa
            JOIN rex.schedules s ON s.id = sa.schedule_id
            JOIN rex.projects p ON p.id = s.project_id
            WHERE s.project_id = ANY($1::uuid[])
              AND sa.start_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '14 days'
            ORDER BY sa.start_date ASC, p.name
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
                "percent_complete": f"{float(r['percent_complete'] or 0):.0f}%",
            }
            for r in sample_rows
        ]

        stats = {
            "tasks_starting_next_14d": int(row["tasks_starting_next_14d"] or 0),
            "projects_with_starts": int(row["projects_with_starts"] or 0),
            "earliest_start_date": (
                row["earliest_start"].isoformat() if row["earliest_start"] else None
            ),
        }

        summary = [
            f"Tasks starting in next 14 days: {stats['tasks_starting_next_14d']}",
            f"Projects with starts: {stats['projects_with_starts']}",
        ]
        if stats["earliest_start_date"]:
            summary.append(f"Earliest start: {stats['earliest_start_date']}")

        return ActionResult(
            stats=stats,
            sample_rows=sample_rows,
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, len(project_ids)),
                summary_lines=summary,
                table_header=["project_name", "task_name", "start_date", "end_date", "percent_complete"],
                rows=display_rows,
                empty_message="No tasks starting in the next 14 days in the selected scope.",
            ),
        )

    def _empty(self, ctx, n_projects):
        return ActionResult(
            stats={"tasks_starting_next_14d": 0, "projects_with_starts": 0, "earliest_start_date": None},
            sample_rows=[],
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, n_projects),
                summary_lines=["Tasks starting in next 14 days: 0"],
                table_header=[],
                rows=[],
                empty_message="No tasks starting in the next 14 days in the selected scope.",
            ),
        )

    @staticmethod
    def _scope_label(ctx, n_projects):
        if ctx.project_id is not None:
            return "single project (page scope)"
        return f"portfolio across {n_projects} projects the user has access to"


__all__ = ["Handler"]
