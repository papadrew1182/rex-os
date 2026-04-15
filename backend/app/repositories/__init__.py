"""Repository package for Session 2 data access helpers.

Session 2 (feat/canonical-connectors) lane.

Thin DB access helpers for the identity / RBAC / connector / source_link
domain. Consumed by the Session 2 endpoint routes and (later) by
Session 1's assistant lane when it needs to resolve permissions outside
a normal FastAPI request context.

Named ``_s2`` module-prefix so the package can coexist with Session 1's
existing ``backend/repositories/`` top-level package if one of them
later moves to ``backend/app/repositories/``. (See
``docs/roadmaps/baseline-reconciliation.md`` §11.)
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
