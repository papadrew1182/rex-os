"""submittal_sla — open submittals with SLA-aging buckets.

rex.v_project_mgmt surfaces submittals with days_open=NULL, so we
compute days_since_created from v_project_mgmt.created_at at query time.
SLA buckets: 0-5, 6-10, 11-20, 21+ calendar days (business-day math
is a future refinement if needed).

"Open" for submittals maps to the working statuses {draft, pending,
submitted} — everything prior to a terminal approval/rejection/closure.
"""
from __future__ import annotations

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    resolve_scope_project_ids,
    _render_fragment,
)


_OPEN_STATUSES = ("draft", "pending", "submitted")


class Handler:
    slug = "submittal_sla"

    async def run(self, ctx: ActionContext) -> ActionResult:
        project_ids = await resolve_scope_project_ids(
            ctx.conn, user_account_id=ctx.user_account_id, project_id=ctx.project_id,
        )
        empty_stats = {
            "total_open": 0,
            "buckets": {"0_to_5": 0, "6_to_10": 0, "11_to_20": 0, "21_plus": 0},
            "oldest_days": None,
        }
        if not project_ids:
            return self._empty(ctx, 0, empty_stats)

        row = await ctx.conn.fetchrow(
            """
            WITH base AS (
                SELECT
                    pm.*,
                    EXTRACT(DAY FROM now() - pm.created_at)::int AS days_since_created
                FROM rex.v_project_mgmt pm
                WHERE pm.entity_type = 'submittal'
                  AND pm.status = ANY($2::text[])
                  AND pm.project_id = ANY($1::uuid[])
            )
            SELECT
                COUNT(*)                                                     AS total_open,
                COUNT(*) FILTER (WHERE days_since_created BETWEEN 0 AND 5)   AS b_0_5,
                COUNT(*) FILTER (WHERE days_since_created BETWEEN 6 AND 10)  AS b_6_10,
                COUNT(*) FILTER (WHERE days_since_created BETWEEN 11 AND 20) AS b_11_20,
                COUNT(*) FILTER (WHERE days_since_created > 20)              AS b_21_plus,
                MAX(days_since_created)                                      AS oldest_days
            FROM base
            """,
            project_ids,
            list(_OPEN_STATUSES),
        )
        total = int(row["total_open"] or 0)
        if total == 0:
            return self._empty(ctx, len(project_ids), empty_stats)

        sample = await ctx.conn.fetch(
            """
            SELECT
                pm.entity_number              AS submittal_number,
                pm.title                      AS title,
                EXTRACT(DAY FROM now() - pm.created_at)::int AS days_since_created,
                p.name                        AS project_name
            FROM rex.v_project_mgmt pm
            JOIN rex.projects p ON p.id = pm.project_id
            WHERE pm.entity_type = 'submittal'
              AND pm.status = ANY($2::text[])
              AND pm.project_id = ANY($1::uuid[])
            ORDER BY pm.created_at ASC
            LIMIT 10
            """,
            project_ids,
            list(_OPEN_STATUSES),
        )
        sample_rows = [dict(r) for r in sample]

        stats = {
            "total_open": total,
            "buckets": {
                "0_to_5":   int(row["b_0_5"]  or 0),
                "6_to_10":  int(row["b_6_10"] or 0),
                "11_to_20": int(row["b_11_20"] or 0),
                "21_plus":  int(row["b_21_plus"] or 0),
            },
            "oldest_days": int(row["oldest_days"] or 0),
        }

        summary = [
            f"Total open submittals: {total}",
            f"Aging: {stats['buckets']['0_to_5']} (0-5d), "
            f"{stats['buckets']['6_to_10']} (6-10d), "
            f"{stats['buckets']['11_to_20']} (11-20d), "
            f"{stats['buckets']['21_plus']} (21+d)",
            f"Oldest: {stats['oldest_days']} days",
        ]

        return ActionResult(
            stats=stats,
            sample_rows=sample_rows,
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, len(project_ids)),
                summary_lines=summary,
                table_header=["project_name", "submittal_number", "title", "days_since_created"],
                rows=sample_rows,
                empty_message="You have no open submittals in the selected scope.",
            ),
        )

    def _empty(self, ctx, n_projects, empty_stats):
        return ActionResult(
            stats=empty_stats,
            sample_rows=[],
            prompt_fragment=_render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, n_projects),
                summary_lines=["Total open submittals: 0"],
                table_header=[],
                rows=[],
                empty_message="You have no open submittals in the selected scope.",
            ),
        )

    @staticmethod
    def _scope_label(ctx, n_projects):
        if ctx.project_id is not None:
            return "single project (page scope)"
        return f"portfolio across {n_projects} projects the user has access to"


__all__ = ["Handler"]
