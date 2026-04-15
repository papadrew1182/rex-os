"""Pydantic schemas for the assistant action catalog contract.

Frozen for Session 3 (frontend sidebar shell) consumers. Slug is the
canonical identity; ``legacy_aliases`` preserves legacy ``C-*`` IDs.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

RiskTier = Literal[
    "read_only",
    "internal_write_low",
    "connector_write_medium",
    "connector_write_high",
]

ReadinessState = Literal[
    "live",
    "alpha",
    "adapter_pending",
    "writeback_pending",
    "blocked",
    "disabled",
]


class ActionParam(BaseModel):
    name: str
    type: str
    label: str
    required: bool = False
    default: Any | None = None
    options: list[dict[str, Any]] | None = None


class CatalogCategory(BaseModel):
    key: str
    label: str


class CatalogAction(BaseModel):
    slug: str
    legacy_aliases: list[str] = Field(default_factory=list)
    label: str
    category: str
    description: str
    params_schema: list[ActionParam] = Field(default_factory=list)
    risk_tier: RiskTier
    readiness_state: ReadinessState
    required_connectors: list[str] = Field(default_factory=list)
    role_visibility: list[str] = Field(default_factory=list)
    enabled: bool = True
    can_run: bool = True


class CatalogResponse(BaseModel):
    version: str = "v1"
    categories: list[CatalogCategory]
    actions: list[CatalogAction]
