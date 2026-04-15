"""Safe-SQL guard for the free-form query planner.

The guard is DEFENSIVE-BY-DEFAULT. Any query that fails a rule is rejected
with a structured ``BlockedQueryError`` — never quietly rewritten.

Rules:
1. Single statement only.
2. Must start with SELECT or WITH.
3. No SQL comments (-- or /* */).
4. No DDL / DML / transactional keywords.
5. Every FROM/JOIN target must be in the curated allowlist (or a CTE).
6. No cross-schema reads outside ``rex.v_*``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DEFAULT_ALLOWED_VIEWS: frozenset[str] = frozenset(
    {
        "rex.v_project_mgmt",
        "rex.v_financials",
        "rex.v_schedule",
        "rex.v_directory",
        "rex.v_portfolio",
        "rex.v_risk",
        "rex.v_myday",
    }
)

_FORBIDDEN_KEYWORDS = (
    "insert", "update", "delete", "merge", "truncate", "drop",
    "alter", "create", "grant", "revoke", "vacuum", "analyze",
    "copy", "call", "do", "lock", "begin", "commit", "rollback",
    "savepoint", "set", "reset", "notify", "listen", "refresh",
)

_QUALIFIED_REF_RE = re.compile(
    r"(?<![\w.])([a-zA-Z_][\w]*)\.([a-zA-Z_][\w]*)",
)

_FROM_JOIN_RE = re.compile(
    r"\b(?:from|join)\s+([a-zA-Z_][\w]*(?:\.[a-zA-Z_][\w]*)?)",
    re.IGNORECASE,
)

_CTE_NAME_RE = re.compile(
    r"(?:\bwith\b|,)\s+([a-zA-Z_][\w]*)\s+as\s*\(",
    re.IGNORECASE,
)


@dataclass
class BlockedQueryError(Exception):
    code: str
    message: str
    offending: str | None = None
    details: dict[str, str] = field(default_factory=dict)

    def __str__(self) -> str:  # pragma: no cover
        return f"[{self.code}] {self.message}"


@dataclass
class GuardResult:
    sql: str
    referenced_views: list[str]


class SqlGuard:
    def __init__(self, *, allowed_views: frozenset[str] | None = None) -> None:
        self.allowed_views = allowed_views or DEFAULT_ALLOWED_VIEWS

    def check(self, sql: str) -> GuardResult:
        if sql is None or not sql.strip():
            raise BlockedQueryError(code="empty_query", message="Empty SQL query.")

        stripped = sql.strip().rstrip(";").strip()

        self._reject_comments(stripped)
        self._reject_multiple_statements(stripped)
        self._reject_non_select(stripped)
        self._reject_forbidden_keywords(stripped)
        cte_names = self._collect_cte_names(stripped)
        referenced = self._collect_from_join_refs(stripped)
        self._reject_unallowed_views(referenced, cte_names=cte_names)
        self._reject_unallowed_qualified_refs(stripped)

        real_views = sorted(
            ref for ref in referenced if "." in ref and ref not in cte_names
        )
        return GuardResult(sql=stripped, referenced_views=real_views)

    def _reject_comments(self, sql: str) -> None:
        if "--" in sql or "/*" in sql or "*/" in sql:
            raise BlockedQueryError(
                code="comments_forbidden",
                message="SQL comments are not allowed in assistant queries.",
            )

    def _reject_multiple_statements(self, sql: str) -> None:
        if ";" in sql:
            raise BlockedQueryError(
                code="multiple_statements",
                message="Only a single SQL statement is allowed.",
            )

    def _reject_non_select(self, sql: str) -> None:
        head = sql.lstrip().split(None, 1)[0].lower() if sql.lstrip() else ""
        if head not in {"select", "with"}:
            raise BlockedQueryError(
                code="non_select",
                message="Only SELECT/WITH statements are allowed.",
                offending=head,
            )

    def _reject_forbidden_keywords(self, sql: str) -> None:
        lowered = sql.lower()
        for kw in _FORBIDDEN_KEYWORDS:
            if re.search(rf"\b{kw}\b", lowered):
                raise BlockedQueryError(
                    code="forbidden_keyword",
                    message=f"Keyword '{kw}' is not allowed.",
                    offending=kw,
                )

    def _collect_from_join_refs(self, sql: str) -> set[str]:
        return {m.group(1).lower() for m in _FROM_JOIN_RE.finditer(sql)}

    def _collect_cte_names(self, sql: str) -> set[str]:
        return {m.group(1).lower() for m in _CTE_NAME_RE.finditer(sql)}

    def _reject_unallowed_views(
        self, referenced: set[str], *, cte_names: set[str]
    ) -> None:
        for ref in referenced:
            if "." not in ref:
                if ref in cte_names:
                    continue
                raise BlockedQueryError(
                    code="unqualified_table",
                    message=(
                        "All table references must be schema-qualified as "
                        "rex.v_* (or resolve to a WITH CTE)."
                    ),
                    offending=ref,
                )
            if ref not in self.allowed_views:
                raise BlockedQueryError(
                    code="unallowed_view",
                    message=f"View '{ref}' is not on the assistant allowlist.",
                    offending=ref,
                )

    def _reject_unallowed_qualified_refs(self, sql: str) -> None:
        for match in _QUALIFIED_REF_RE.finditer(sql):
            schema, name = match.group(1).lower(), match.group(2).lower()
            qualified = f"{schema}.{name}"
            if qualified in self.allowed_views:
                continue
            if schema in {"pg_catalog", "information_schema", "public"}:
                raise BlockedQueryError(
                    code="unallowed_schema",
                    message=f"Schema '{schema}' is not readable from the assistant.",
                    offending=qualified,
                )
            raise BlockedQueryError(
                code="unallowed_schema",
                message=(
                    f"Reference '{qualified}' is outside the curated allowlist. "
                    "Assistant queries may only read rex.v_* views."
                ),
                offending=qualified,
            )
