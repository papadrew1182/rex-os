"""daily_log_summary — last 7 days of daily logs + today's manpower rollup.

Reads rex.daily_logs scoped to the user's accessible projects (or a single
project_id when invoked in page scope) and joins rex.manpower_entries for
today's headcount and trade-count rollups.
"""
from __future__ import annotations

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    resolve_scope_project_ids,
    render_fragment,
)


class Handler:
    slug = "daily_log_summary"

    async def run(self, ctx: ActionContext) -> ActionResult:
        project_ids = await resolve_scope_project_ids(
            ctx.conn,
            user_account_id=ctx.user_account_id,
            project_id=ctx.project_id,
        )
        if not project_ids:
            return self._empty(ctx, 0)

        stats_row = await ctx.conn.fetchrow(
            """
            WITH logs7 AS (
                SELECT * FROM rex.daily_logs
                WHERE project_id = ANY($1::uuid[])
                  AND log_date >= CURRENT_DATE - INTERVAL '7 days'
            ), todays AS (
                SELECT * FROM rex.daily_logs
                WHERE project_id = ANY($1::uuid[])
                  AND log_date = CURRENT_DATE
            )
            SELECT
                (SELECT COUNT(*) FROM logs7)                                         AS logs_last_7_days,
                COALESCE((SELECT SUM(me.worker_count)
                    FROM todays t JOIN rex.manpower_entries me ON me.daily_log_id = t.id), 0) AS today_total_manpower,
                COALESCE((SELECT COUNT(DISTINCT me.company_id)
                    FROM todays t JOIN rex.manpower_entries me ON me.daily_log_id = t.id), 0) AS today_trades_on_site,
                (
                    array_length($1::uuid[], 1)
                    - (SELECT COUNT(DISTINCT project_id) FROM todays)
                )                                                                   AS projects_without_today_log
            """,
            project_ids,
        )

        sample = await ctx.conn.fetch(
            """
            SELECT
                p.name                                               AS project_name,
                dl.log_date                                          AS log_date,
                dl.weather_summary                                   AS weather,
                COALESCE(SUM(me.worker_count), 0)                    AS total_headcount,
                COUNT(DISTINCT me.company_id)                        AS trade_count
            FROM rex.daily_logs dl
            JOIN rex.projects p ON p.id = dl.project_id
            LEFT JOIN rex.manpower_entries me ON me.daily_log_id = dl.id
            WHERE dl.project_id = ANY($1::uuid[])
              AND dl.log_date >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY p.name, dl.log_date, dl.weather_summary
            ORDER BY dl.log_date DESC, p.name
            LIMIT 10
            """,
            project_ids,
        )
        sample_rows = [dict(r) for r in sample]
        display_rows = [
            {**r, "log_date": r["log_date"].isoformat() if r.get("log_date") else ""}
            for r in sample_rows
        ]

        stats = {
            "logs_last_7_days": int(stats_row["logs_last_7_days"] or 0),
            "today_total_manpower": int(stats_row["today_total_manpower"] or 0),
            "today_trades_on_site": int(stats_row["today_trades_on_site"] or 0),
            "projects_without_today_log": int(stats_row["projects_without_today_log"] or 0),
        }
        summary = [
            f"Logs submitted last 7 days: {stats['logs_last_7_days']}",
            f"Today total manpower: {stats['today_total_manpower']} across {stats['today_trades_on_site']} trade(s)",
            f"Projects without a log today: {stats['projects_without_today_log']}",
        ]

        return ActionResult(
            stats=stats,
            sample_rows=sample_rows,
            prompt_fragment=render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, len(project_ids)),
                summary_lines=summary,
                table_header=["project_name", "log_date", "weather", "total_headcount", "trade_count"],
                rows=display_rows,
                empty_message="No daily logs in the last 7 days in the selected scope.",
            ),
        )

    def _empty(self, ctx: ActionContext, n_projects: int) -> ActionResult:
        return ActionResult(
            stats={
                "logs_last_7_days": 0,
                "today_total_manpower": 0,
                "today_trades_on_site": 0,
                "projects_without_today_log": 0,
            },
            sample_rows=[],
            prompt_fragment=render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, n_projects),
                summary_lines=["Logs submitted last 7 days: 0"],
                table_header=[],
                rows=[],
                empty_message="No daily logs in the last 7 days in the selected scope.",
            ),
        )

    @staticmethod
    def _scope_label(ctx: ActionContext, n_projects: int) -> str:
        if ctx.project_id is not None:
            return "single project (page scope)"
        return f"portfolio across {n_projects} projects the user has access to"


__all__ = ["Handler"]
