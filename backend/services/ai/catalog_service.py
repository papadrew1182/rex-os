"""Catalog service — presentation-layer view of the action catalog."""

from __future__ import annotations

from repositories.catalog_repository import CatalogRepository
from schemas.catalog import ActionParam, CatalogAction, CatalogCategory, CatalogResponse

_CATEGORY_LABELS: dict[str, str] = {
    "FINANCIALS": "Financials",
    "SCHEDULING": "Scheduling",
    "PROJECT_MGMT": "Project Management",
    "PROCUREMENT": "Procurement",
    "OPERATIONS": "Operations",
    "EXECUTIVE": "Executive",
    "DIRECTORY": "Directory",
    "PERFORMANCE": "Performance",
    "TRAINING": "Training",
}


class CatalogService:
    def __init__(self, repo: CatalogRepository) -> None:
        self._repo = repo

    async def build_catalog_response(
        self, *, role_keys: list[str] | None = None
    ) -> CatalogResponse:
        rows = await self._repo.list_actions(role_keys=role_keys)
        actions = [_row_to_action_model(row) for row in rows]

        seen: dict[str, str] = {}
        for a in actions:
            if a.category not in seen:
                seen[a.category] = _CATEGORY_LABELS.get(
                    a.category, a.category.replace("_", " ").title()
                )
        categories = [CatalogCategory(key=k, label=v) for k, v in seen.items()]
        categories.sort(key=lambda c: c.label)

        return CatalogResponse(
            version="v1",
            categories=categories,
            actions=actions,
        )


def _row_to_action_model(row: dict) -> CatalogAction:
    params_raw = row.get("params_schema") or []
    if not isinstance(params_raw, list):
        params_raw = []
    params = [
        ActionParam(
            name=p.get("name", ""),
            type=p.get("type", "text"),
            label=p.get("label", p.get("name", "")),
            required=bool(p.get("required", False)),
            default=p.get("default"),
            options=p.get("options"),
        )
        for p in params_raw
        if isinstance(p, dict)
    ]
    return CatalogAction(
        slug=row["slug"],
        legacy_aliases=row.get("legacy_aliases") or [],
        label=row["label"],
        category=row["category"],
        description=row["description"],
        params_schema=params,
        risk_tier=row["risk_tier"],
        readiness_state=row["readiness_state"],
        required_connectors=row.get("required_connectors") or [],
        role_visibility=row.get("role_visibility") or [],
        enabled=bool(row.get("enabled", True)),
        can_run=_derive_can_run(row),
    )


def _derive_can_run(row: dict) -> bool:
    """``can_run`` reflects readiness/enabled state only.

    Connector availability is Session 2's concern — when it lands, the
    frontend can layer a connector-aware check on top of ``can_run``
    without us changing the contract.
    """
    if not row.get("enabled", True):
        return False
    return row.get("readiness_state") in {"live", "alpha"}
