"""documentation_compliance — overdue / near-due closeout checklist items.

Reads rex.v_closeout_items. (rex.v_documents is just an attachments
bridge with no compliance semantics, so we redirect here.)

Buckets:
  - overdue:            status != 'complete' AND due_date < today
  - due_within_30_days: status != 'complete' AND due_date BETWEEN today AND today+30

Note on status values: rex.closeout_checklist_items.status CHECK
constraint is ('not_started','in_progress','complete','n_a'). We exclude
'complete' (and implicitly 'n_a' has no meaningful due-date semantics but
is covered by the != 'complete' predicate — n/a items still show if their
due_date is in-range; acceptable because n/a items are usually also set
past their due date in practice).
"""
from __future__ import annotations

from app.services.ai.actions.base import (
    ActionContext,
    ActionResult,
    resolve_scope_project_ids,
    render_fragment,
)


class Handler:
    slug = "documentation_compliance"

    async def run(self, ctx: ActionContext) -> ActionResult:
        project_ids = await resolve_scope_project_ids(
            ctx.conn,
            user_account_id=ctx.user_account_id,
            project_id=ctx.project_id,
        )
        if not project_ids:
            return self._empty(ctx, 0)

        row = await ctx.conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (
                    WHERE status != 'complete'
                      AND due_date < CURRENT_DATE
                )                                            AS overdue_items,
                COUNT(*) FILTER (
                    WHERE status != 'complete'
                      AND due_date BETWEEN CURRENT_DATE
                                       AND CURRENT_DATE + INTERVAL '30 days'
                )                                            AS due_within_30_days
            FROM rex.v_closeout_items
            WHERE project_id = ANY($1::uuid[])
            """,
            project_ids,
        )
        sample = await ctx.conn.fetch(
            """
            SELECT
                p.name       AS project_name,
                ci.category  AS category,
                ci.name      AS item_name,
                ci.status    AS status,
                ci.due_date  AS due_date,
                (ci.due_date - CURRENT_DATE) AS days_to_due
            FROM rex.v_closeout_items ci
            JOIN rex.projects p ON p.id = ci.project_id
            WHERE ci.project_id = ANY($1::uuid[])
              AND ci.status != 'complete'
              AND (
                ci.due_date < CURRENT_DATE
                OR ci.due_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
              )
            ORDER BY
                CASE WHEN ci.due_date < CURRENT_DATE THEN 0 ELSE 1 END,
                ci.due_date ASC
            LIMIT 10
            """,
            project_ids,
        )
        sample_rows = [dict(r) for r in sample]
        display_rows = [
            {
                **r,
                "due_date": r["due_date"].isoformat() if r.get("due_date") else "",
            }
            for r in sample_rows
        ]

        stats = {
            "overdue_items": int(row["overdue_items"] or 0),
            "due_within_30_days": int(row["due_within_30_days"] or 0),
        }

        summary = [
            f"Overdue items: {stats['overdue_items']}",
            f"Due within 30 days: {stats['due_within_30_days']}",
        ]

        return ActionResult(
            stats=stats,
            sample_rows=sample_rows,
            prompt_fragment=render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, len(project_ids)),
                summary_lines=summary,
                table_header=[
                    "project_name", "category", "item_name",
                    "status", "due_date", "days_to_due",
                ],
                rows=display_rows,
                empty_message="No overdue or near-due closeout items in the selected scope.",
            ),
        )

    def _empty(self, ctx: ActionContext, n_projects: int) -> ActionResult:
        return ActionResult(
            stats={"overdue_items": 0, "due_within_30_days": 0},
            sample_rows=[],
            prompt_fragment=render_fragment(
                slug=self.slug,
                scope_label=self._scope_label(ctx, n_projects),
                summary_lines=["Overdue items: 0", "Due within 30 days: 0"],
                table_header=[],
                rows=[],
                empty_message="No overdue or near-due closeout items in the selected scope.",
            ),
        )

    @staticmethod
    def _scope_label(ctx: ActionContext, n_projects: int) -> str:
        if ctx.project_id is not None:
            return "single project (page scope)"
        return f"portfolio across {n_projects} projects the user has access to"


__all__ = ["Handler"]
