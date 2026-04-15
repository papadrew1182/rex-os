"""Repository package for backend data access helpers.

Thin DB access helpers for the identity / RBAC / connector / source_link
domain (originally Session 2 / feat/canonical-connectors) plus the
assistant catalog / chat / prompt repositories (originally Session 1 /
feat/ai-spine). Both sets now live here after the post-merge
consolidation on ``main``; see ``docs/roadmaps/baseline-reconciliation.md``
for the history.
"""

from app.repositories.identity_repository import (
    get_user_permissions,
    get_user_roles,
    resolve_role_alias,
)
from app.repositories.connector_repository import (
    list_connectors_with_status,
    list_connector_accounts,
)

__all__ = [
    "get_user_permissions",
    "get_user_roles",
    "resolve_role_alias",
    "list_connectors_with_status",
    "list_connector_accounts",
]
