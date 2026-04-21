"""budget_variance — flags projects with |budget_over_under/revised_budget| > 5%.

Reads rex.v_financials, computes delta_pct = budget_over_under /
revised_budget per project, and reports how many projects exceed the
5% threshold. Sample rows are sorted by |delta_pct| DESC so the worst
offenders come first.
"""
from __future__ import annotations

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    resolve_scope_project_ids,
    render_fragment,
)


class Handler:
    slug = "budget_variance"

    async def run(self, ctx: ActionContext) -> ActionResult:
        project_ids = await resolve_scope_project_ids(
            ctx.conn,
            user_account_id=ctx.user_account_id,
            project_id=ctx.project_id,
        )
        if not project_ids:
            return self._empty(ctx, 0)

        # Full-portfolio aggregate (no LIMIT) so total_projects /
        # projects_over_5pct / total_portfolio_delta are correct beyond
        # the 10-row LIMIT used for the markdown table below.
        aggregate_row = await ctx.conn.fetchrow(
            """
            SELECT
                COUNT(*) AS total_projects,
                SUM(budget_over_under) AS total_delta,
                COUNT(*) FILTER (
                    WHERE revised_budget IS NOT NULL
                      AND revised_budget <> 0
                      AND ABS(budget_over_under / revised_budget) > 0.05
                ) AS projects_over_5pct
            FROM rex.v_financials
            WHERE project_id = ANY($1::uuid[])
            """,
            project_ids,
        )
        total_projects = int(aggregate_row["total_projects"] or 0)
        if total_projects == 0:
            return self._empty(ctx, len(project_ids))
        projects_over_5pct = int(aggregate_row["projects_over_5pct"] or 0)
        total_delta = float(aggregate_row["total_delta"] or 0)

        rows = await ctx.conn.fetch(
            """
            SELECT
                project_id,
                project_name,
                revised_budget,
                budget_over_under,
                CASE
                    WHEN revised_budget = 0 OR revised_budget IS NULL THEN NULL
                    ELSE budget_over_under / NULLIF(revised_budget, 0)
                END AS delta_pct
            FROM rex.v_financials
            WHERE project_id = ANY($1::uuid[])
            ORDER BY ABS(COALESCE(
                budget_over_under / NULLIF(revised_budget, 0), 0
            )) DESC
            LIMIT 10
            """,
            project_ids,
        )

        sample_rows = [
            {
                "project_name": r["project_name"],
                "revised_budget": float(r["revised_budget"] or 0),
                "budget_over_under": float(r["budget_over_under"] or 0),
                "delta_pct": float(r["delta_pct"] or 0),
            }
            for r in rows
        ]

        # sample_rows is ordered by |delta_pct| DESC, so the worst offender
        # is always sample_rows[0] even though we capped at LIMIT 10.
        worst = sample_rows[0] if sample_rows else None

        stats = {
            "total_projects": total_projects,
            "projects_over_5pct": projects_over_5pct,
            "total_portfolio_delta": total_delta,
            "worst_variance_pct": worst["delta_pct"] if worst else None,
            "worst_project_name": worst["project_name"] if worst else None,
        }

        summary = [
            f"Projects tracked: {stats['total_projects']}",
            f"Projects with |variance| > 5%: {projects_over_5pct}",
            f"Portfolio budget over/under total: {total_delta:+,.2f}",
        ]
        if worst:
            summary.append(
                f"Worst variance: {worst['delta_pct']:+.1%} on {worst['project_name']}"
            )

        display_rows = [
            {
                **r,
                "delta_pct": f"{r['delta_pct']:+.1%}",
                "budget_over_under": f"{r['budget_over_under']:+,.0f}",
                "revised_budget": f"{r['revised_budget']:,.0f}",
            }
            for r in sample_rows
        ]

        return ActionResult(
            stats=stats,
            sample_rows=sample_rows,
            prompt_fragment=render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, len(project_ids)),
                summary_lines=summary,
                table_header=[
                    "project_name",
                    "revised_budget",
                    "budget_over_under",
                    "delta_pct",
                ],
                rows=display_rows,
                empty_message="No budget data is available for the selected scope.",
            ),
        )

    def _empty(self, ctx: ActionContext, n_projects: int) -> ActionResult:
        return ActionResult(
            stats={
                "total_projects": 0,
                "projects_over_5pct": 0,
                "total_portfolio_delta": 0.0,
                "worst_variance_pct": None,
                "worst_project_name": None,
            },
            sample_rows=[],
            prompt_fragment=render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, n_projects),
                summary_lines=["Projects tracked: 0"],
                table_header=[],
                rows=[],
                empty_message="No budget data is available for the selected scope.",
            ),
        )

    @staticmethod
    def _scope_label(ctx: ActionContext, n_projects: int) -> str:
        if ctx.project_id is not None:
            return "single project (page scope)"
        return f"portfolio across {n_projects} projects the user has access to"


__all__ = ["Handler"]
