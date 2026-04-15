"""Role-normalized assistant context builder.

Builds the ``AssistantUser`` view and owns the legacy-to-canonical role
normalization map. Role policy is centralized here so the frontend never
needs to know legacy aliases — it always sees canonical keys.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from schemas.assistant import AssistantUser, PageContext

CANONICAL_ROLES: tuple[str, ...] = (
    "VP",
    "PM",
    "GENERAL_SUPER",
    "LEAD_SUPER",
    "ASSISTANT_SUPER",
    "ACCOUNTANT",
)

LEGACY_ROLE_ALIAS_MAP: dict[str, str] = {
    # VP
    "vp": "VP",
    "vp_pm": "VP",
    "vice_president": "VP",
    "vice president": "VP",
    # PM
    "pm": "PM",
    "project_manager": "PM",
    "project manager": "PM",
    # General Super
    "gs": "GENERAL_SUPER",
    "general_super": "GENERAL_SUPER",
    "general_superintendent": "GENERAL_SUPER",
    "general superintendent": "GENERAL_SUPER",
    # Lead Super
    "ls": "LEAD_SUPER",
    "lead_super": "LEAD_SUPER",
    "lead_superintendent": "LEAD_SUPER",
    "lead superintendent": "LEAD_SUPER",
    # Assistant Super
    "as": "ASSISTANT_SUPER",
    "assistant_super": "ASSISTANT_SUPER",
    "assistant_superintendent": "ASSISTANT_SUPER",
    "assistant superintendent": "ASSISTANT_SUPER",
    # Accountant
    "acct": "ACCOUNTANT",
    "accounting": "ACCOUNTANT",
    "accountant": "ACCOUNTANT",
}


def normalize_role(raw_role: str | None) -> str | None:
    """Map a legacy role string to a canonical role key, or None."""
    if not raw_role:
        return None
    key = raw_role.strip().lower().replace("-", "_")
    if key in LEGACY_ROLE_ALIAS_MAP:
        return LEGACY_ROLE_ALIAS_MAP[key]
    up = raw_role.strip().upper().replace("-", "_").replace(" ", "_")
    if up in CANONICAL_ROLES:
        return up
    return None


def normalize_roles(raw_roles: list[str] | None) -> list[str]:
    """Normalize a list, preserving canonical-priority order and dedup."""
    if not raw_roles:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for raw in raw_roles:
        canon = normalize_role(raw)
        if canon and canon not in seen:
            seen.add(canon)
            result.append(canon)
    result.sort(key=CANONICAL_ROLES.index)
    return result


@dataclass
class AssistantContext:
    user: AssistantUser
    project_id: UUID | None
    page_context: PageContext
    system_prompt: str


class ContextBuilder:
    def build_user(
        self,
        *,
        user_id: UUID,
        email: str | None,
        full_name: str | None,
        legacy_role: str | None,
        extra_role_aliases: list[str] | None = None,
        project_ids: list[UUID] | None = None,
    ) -> AssistantUser:
        aliases: list[str] = []
        if legacy_role:
            aliases.append(legacy_role)
        if extra_role_aliases:
            aliases.extend(extra_role_aliases)

        role_keys = normalize_roles(aliases)
        primary = role_keys[0] if role_keys else "PM"

        return AssistantUser(
            id=user_id,
            email=email,
            full_name=full_name,
            primary_role_key=primary,
            role_keys=role_keys or [primary],
            legacy_role_aliases=aliases,
            project_ids=project_ids or [],
        )

    def build_context(
        self,
        *,
        user: AssistantUser,
        project_id: UUID | None,
        page_context: PageContext,
        system_prompt: str,
    ) -> AssistantContext:
        return AssistantContext(
            user=user,
            project_id=project_id,
            page_context=page_context,
            system_prompt=_augment_system_prompt(system_prompt, user, project_id),
        )


def _augment_system_prompt(
    base: str, user: AssistantUser, project_id: UUID | None
) -> str:
    role_line = (
        f"Current user role (canonical): {user.primary_role_key}"
        + (f". Secondary: {', '.join(user.role_keys[1:])}" if len(user.role_keys) > 1 else "")
    )
    project_line = (
        f"Active project_id: {project_id}." if project_id else "No active project context."
    )
    return f"{base}\n\n{role_line}\n{project_line}"
