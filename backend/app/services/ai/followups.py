"""Lightweight follow-up suggestion generator.

Session 1 ships a deterministic heuristic generator. A model-backed
generator can replace this later without changing the callsite.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FollowupSuggestion:
    label: str


_DEFAULTS: list[str] = [
    "Summarize the top risks",
    "Show the biggest movers this week",
    "Draft an owner-facing recap",
]

_BY_SLUG: dict[str, list[str]] = {
    "budget_variance": [
        "Show top 5 cost codes driving the variance",
        "Compare against last month",
        "Draft an owner narrative of the variance",
    ],
    "rfi_aging": [
        "Filter to RFIs older than 14 days",
        "Group by responsible party",
        "Draft a nudge email to the design team",
    ],
    "submittal_sla": [
        "Show submittals breaching the A&E review SLA",
        "Group by reviewer",
        "Export aging submittals to a CSV",
    ],
    "monthly_owner_report": [
        "Draft the schedule narrative section",
        "Draft the financial narrative section",
        "List the top 3 risks to call out",
    ],
    "critical_path_delays": [
        "Show impacted downstream activities",
        "Suggest recovery sequencing",
        "Draft a delay memo",
    ],
    "two_week_lookahead": [
        "Expand to a 4-week look-ahead",
        "Filter to inspections only",
        "Add weather risk for the window",
    ],
    "morning_briefing": [
        "Show me anything that changed overnight",
        "What needs my attention today?",
        "Show me open items with an owner of me",
    ],
}


class FollowupGenerator:
    def suggest(
        self,
        *,
        active_action_slug: str | None,
        last_user_message: str | None,
    ) -> list[FollowupSuggestion]:
        if active_action_slug and active_action_slug in _BY_SLUG:
            return [FollowupSuggestion(label=label) for label in _BY_SLUG[active_action_slug]]
        return [FollowupSuggestion(label=label) for label in _DEFAULTS]
