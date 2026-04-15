"""Quick-action catalog import + structural validation.

Bridge between the Python source of truth in
``app.data.quick_actions_catalog`` and ``rex.ai_action_catalog``. Three roles:

1. ``validate_catalog()`` — pure structural validation (no DB access).
2. ``upsert_catalog(pool)`` — idempotent bulk UPSERT.
3. ``build_catalog_response_from_source(role_keys)`` — render the full
   catalog response without touching the DB. Used by tests and fakes.

Risk vocabulary: read_only | internal_write_low | connector_write_medium | connector_write_high
Readiness vocabulary: live | alpha | adapter_pending | writeback_pending | blocked | disabled
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import asyncpg

from app.data.quick_actions_catalog import (
    CATEGORY_LABELS,
    QUICK_ACTIONS_CATALOG,
)

VALID_RISK_TIERS: frozenset[str] = frozenset({
    "read_only",
    "internal_write_low",
    "connector_write_medium",
    "connector_write_high",
})
VALID_READINESS_STATES: frozenset[str] = frozenset({
    "live",
    "alpha",
    "adapter_pending",
    "writeback_pending",
    "blocked",
    "disabled",
})
CANONICAL_ROLE_KEYS: frozenset[str] = frozenset({
    "VP",
    "PM",
    "GENERAL_SUPER",
    "LEAD_SUPER",
    "ASSISTANT_SUPER",
    "ACCOUNTANT",
})

_ALIAS_RE = re.compile(r"^C-\d+$")
_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass
class CatalogValidationError(Exception):
    code: str
    message: str
    offending: str | None = None

    def __str__(self) -> str:  # pragma: no cover
        return f"[{self.code}] {self.message}"


def validate_catalog(entries: list[dict[str, Any]] | None = None) -> None:
    """Raise ``CatalogValidationError`` on any structural violation."""
    data = entries or QUICK_ACTIONS_CATALOG

    seen_slugs: set[str] = set()
    seen_aliases: set[str] = set()

    for entry in data:
        slug = entry.get("slug")
        if not slug or not isinstance(slug, str):
            raise CatalogValidationError(
                code="missing_slug", message="Entry is missing a slug", offending=str(entry)
            )
        if not _SLUG_RE.match(slug):
            raise CatalogValidationError(
                code="invalid_slug_format",
                message=f"Slug '{slug}' is not snake_case",
                offending=slug,
            )
        if slug in seen_slugs:
            raise CatalogValidationError(
                code="duplicate_slug", message=f"Slug '{slug}' is duplicated", offending=slug
            )
        seen_slugs.add(slug)

        aliases = entry.get("legacy_aliases") or []
        if not isinstance(aliases, list):
            raise CatalogValidationError(
                code="invalid_aliases",
                message=f"legacy_aliases must be a list for slug '{slug}'",
                offending=slug,
            )
        for alias in aliases:
            if not isinstance(alias, str) or not _ALIAS_RE.match(alias):
                raise CatalogValidationError(
                    code="invalid_alias_format",
                    message=f"Alias '{alias}' on '{slug}' must match C-[0-9]+",
                    offending=alias,
                )
            if alias in seen_aliases:
                raise CatalogValidationError(
                    code="duplicate_alias",
                    message=f"Alias '{alias}' appears on more than one slug",
                    offending=alias,
                )
            seen_aliases.add(alias)

        risk = entry.get("risk_tier")
        if risk not in VALID_RISK_TIERS:
            raise CatalogValidationError(
                code="invalid_risk_tier",
                message=f"Risk tier '{risk}' not in vocabulary",
                offending=slug,
            )

        readiness = entry.get("readiness_state")
        if readiness not in VALID_READINESS_STATES:
            raise CatalogValidationError(
                code="invalid_readiness_state",
                message=f"Readiness '{readiness}' not in vocabulary",
                offending=slug,
            )

        roles = entry.get("role_visibility") or []
        if not isinstance(roles, list):
            raise CatalogValidationError(
                code="invalid_roles",
                message=f"role_visibility must be a list for '{slug}'",
                offending=slug,
            )
        for r in roles:
            if r not in CANONICAL_ROLE_KEYS:
                raise CatalogValidationError(
                    code="non_canonical_role",
                    message=f"Role '{r}' on '{slug}' is not a canonical role key",
                    offending=r,
                )

        if not isinstance(entry.get("required_connectors") or [], list):
            raise CatalogValidationError(
                code="invalid_connectors",
                message=f"required_connectors must be a list for '{slug}'",
                offending=slug,
            )
        if not isinstance(entry.get("params_schema") or [], list):
            raise CatalogValidationError(
                code="invalid_params_schema",
                message=f"params_schema must be a list for '{slug}'",
                offending=slug,
            )


async def upsert_catalog(
    pool: asyncpg.Pool, entries: list[dict[str, Any]] | None = None
) -> int:
    """Upsert all entries into ``rex.ai_action_catalog``. Returns row count."""
    data = entries or QUICK_ACTIONS_CATALOG
    validate_catalog(data)

    sql = """
        INSERT INTO rex.ai_action_catalog
            (slug, legacy_aliases, label, category, description,
             params_schema, risk_tier, readiness_state,
             required_connectors, role_visibility, handler_key,
             enabled, metadata)
        VALUES
            ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11, $12, $13::jsonb)
        ON CONFLICT (slug) DO UPDATE SET
            legacy_aliases      = EXCLUDED.legacy_aliases,
            label               = EXCLUDED.label,
            category            = EXCLUDED.category,
            description         = EXCLUDED.description,
            params_schema       = EXCLUDED.params_schema,
            risk_tier           = EXCLUDED.risk_tier,
            readiness_state     = EXCLUDED.readiness_state,
            required_connectors = EXCLUDED.required_connectors,
            role_visibility     = EXCLUDED.role_visibility,
            handler_key         = EXCLUDED.handler_key,
            enabled             = EXCLUDED.enabled,
            metadata            = EXCLUDED.metadata
    """

    count = 0
    async with pool.acquire() as conn:
        async with conn.transaction():
            for entry in data:
                await conn.execute(
                    sql,
                    entry["slug"],
                    list(entry.get("legacy_aliases") or []),
                    entry["label"],
                    entry["category"],
                    entry["description"],
                    json.dumps(entry.get("params_schema") or []),
                    entry["risk_tier"],
                    entry["readiness_state"],
                    list(entry.get("required_connectors") or []),
                    list(entry.get("role_visibility") or []),
                    entry.get("handler_key"),
                    bool(entry.get("enabled", True)),
                    json.dumps(entry.get("metadata") or {}),
                )
                count += 1
    return count


def build_catalog_response_from_source(
    *, role_keys: list[str] | None = None
) -> dict[str, Any]:
    """Render the full catalog response directly from the Python source."""
    data = [dict(e) for e in QUICK_ACTIONS_CATALOG]
    if role_keys is not None:
        role_set = set(role_keys)
        data = [
            e for e in data
            if not e["role_visibility"]
            or role_set.intersection(e["role_visibility"])
        ]

    cats: dict[str, str] = {}
    for e in data:
        if e["category"] not in cats:
            cats[e["category"]] = CATEGORY_LABELS.get(
                e["category"], e["category"].replace("_", " ").title()
            )

    return {
        "version": "v1",
        "categories": [{"key": k, "label": v} for k, v in cats.items()],
        "actions": [
            {
                "slug": e["slug"],
                "legacy_aliases": e["legacy_aliases"],
                "label": e["label"],
                "category": e["category"],
                "description": e["description"],
                "params_schema": e["params_schema"],
                "risk_tier": e["risk_tier"],
                "readiness_state": e["readiness_state"],
                "required_connectors": e["required_connectors"],
                "role_visibility": e["role_visibility"],
                "enabled": e["enabled"],
                "can_run": _derive_can_run(e),
            }
            for e in data
        ],
    }


def resolve_alias(identifier: str) -> str | None:
    """Pure-Python lookup: slug or legacy alias -> canonical slug."""
    for entry in QUICK_ACTIONS_CATALOG:
        if entry["slug"] == identifier or identifier in entry["legacy_aliases"]:
            return entry["slug"]
    return None


def _derive_can_run(entry: dict[str, Any]) -> bool:
    if not entry.get("enabled", True):
        return False
    return entry["readiness_state"] in {"live", "alpha"}


__all__ = [
    "CANONICAL_ROLE_KEYS",
    "CatalogValidationError",
    "VALID_READINESS_STATES",
    "VALID_RISK_TIERS",
    "build_catalog_response_from_source",
    "resolve_alias",
    "upsert_catalog",
    "validate_catalog",
]
