"""rfi_aging — open RFIs with aging buckets.

Reads rex.v_project_mgmt filtered to entity_type='rfi' and status='open'.
Aging buckets are computed from days_open:
  0-7, 8-14, 15-30, 30+.
Sample rows are the 10 oldest open RFIs (days_open DESC).
"""
from __future__ import annotations

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    resolve_scope_project_ids,
    render_fragment,
)


class Handler:
    slug = "rfi_aging"

    async def run(self, ctx: ActionContext) -> ActionResult:
        project_ids = await resolve_scope_project_ids(
            ctx.conn,
            user_account_id=ctx.user_account_id,
            project_id=ctx.project_id,
        )
        if not project_ids:
            return ActionResult(
                stats={
                    "total_open": 0,
                    "buckets": {"0_to_7": 0, "8_to_14": 0, "15_to_30": 0, "30_plus": 0},
                    "oldest_days": None,
                },
                sample_rows=[],
                prompt_fragment=render_fragment(
                    slug=self.slug,
                    scope_label=self._scope_label(ctx, 0),
                    summary_lines=["Total open RFIs: 0"],
                    table_header=[],
                    rows=[],
                    empty_message="You have no open RFIs in the selected scope.",
                ),
            )

        buckets_row = await ctx.conn.fetchrow(
            """
            SELECT
                COUNT(*)                                                   AS total_open,
                COUNT(*) FILTER (WHERE days_open BETWEEN 0 AND 7)          AS b_0_7,
                COUNT(*) FILTER (WHERE days_open BETWEEN 8 AND 14)         AS b_8_14,
                COUNT(*) FILTER (WHERE days_open BETWEEN 15 AND 30)        AS b_15_30,
                COUNT(*) FILTER (WHERE days_open > 30)                     AS b_30_plus,
                MAX(days_open)                                             AS oldest_days
            FROM rex.v_project_mgmt
            WHERE entity_type = 'rfi'
              AND status = 'open'
              AND project_id = ANY($1::uuid[])
            """,
            project_ids,
        )

        total = int(buckets_row["total_open"] or 0)

        if total == 0:
            return ActionResult(
                stats={
                    "total_open": 0,
                    "buckets": {"0_to_7": 0, "8_to_14": 0, "15_to_30": 0, "30_plus": 0},
                    "oldest_days": None,
                },
                sample_rows=[],
                prompt_fragment=render_fragment(
                    slug=self.slug,
                    scope_label=self._scope_label(ctx, len(project_ids)),
                    summary_lines=["Total open RFIs: 0"],
                    table_header=[],
                    rows=[],
                    empty_message="You have no open RFIs in the selected scope.",
                ),
            )

        sample_q = await ctx.conn.fetch(
            """
            SELECT
                pm.entity_number              AS rfi_number,
                pm.title                      AS subject,
                COALESCE(pm.days_open, 0)     AS days_open,
                p.name                        AS project_name
            FROM rex.v_project_mgmt pm
            JOIN rex.projects p ON p.id = pm.project_id
            WHERE pm.entity_type = 'rfi'
              AND pm.status = 'open'
              AND pm.project_id = ANY($1::uuid[])
            ORDER BY pm.days_open DESC NULLS LAST, pm.due_date ASC NULLS LAST
            LIMIT 10
            """,
            project_ids,
        )
        sample_rows = [dict(r) for r in sample_q]

        stats = {
            "total_open": total,
            "buckets": {
                "0_to_7":  int(buckets_row["b_0_7"] or 0),
                "8_to_14": int(buckets_row["b_8_14"] or 0),
                "15_to_30": int(buckets_row["b_15_30"] or 0),
                "30_plus": int(buckets_row["b_30_plus"] or 0),
            },
            "oldest_days": int(buckets_row["oldest_days"] or 0),
        }

        summary = [
            f"Total open RFIs: {total}",
            f"Aging: {stats['buckets']['0_to_7']} (0-7d), "
            f"{stats['buckets']['8_to_14']} (8-14d), "
            f"{stats['buckets']['15_to_30']} (15-30d), "
            f"{stats['buckets']['30_plus']} (30+d)",
            f"Oldest: {stats['oldest_days']} days",
        ]

        return ActionResult(
            stats=stats,
            sample_rows=sample_rows,
            prompt_fragment=render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, len(project_ids)),
                summary_lines=summary,
                table_header=["project_name", "rfi_number", "subject", "days_open"],
                rows=sample_rows,
                empty_message="You have no open RFIs in the selected scope.",
            ),
        )

    @staticmethod
    def _scope_label(ctx: ActionContext, n_projects: int) -> str:
        if ctx.project_id is not None:
            return "single project (page scope)"
        return f"portfolio across {n_projects} projects the user has access to"


__all__ = ["Handler"]
