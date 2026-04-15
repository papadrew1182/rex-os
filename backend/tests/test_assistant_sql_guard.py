"""Unit tests for the Session 1 SQL guard."""

from __future__ import annotations

import pytest

from app.services.ai.sql_guard import BlockedQueryError, DEFAULT_ALLOWED_VIEWS, SqlGuard


def _guard() -> SqlGuard:
    return SqlGuard()


def test_guard_accepts_select_against_allowed_view():
    result = _guard().check(
        "SELECT project_id, status FROM rex.v_project_mgmt WHERE status = 'active'"
    )
    assert result.referenced_views == ["rex.v_project_mgmt"]


def test_guard_accepts_with_cte_against_allowed_view():
    result = _guard().check(
        "WITH recent AS (SELECT * FROM rex.v_financials) SELECT * FROM recent"
    )
    assert "rex.v_financials" in result.referenced_views


def test_guard_rejects_non_allowlisted_view():
    with pytest.raises(BlockedQueryError) as err:
        _guard().check("SELECT * FROM rex.v_unknown")
    assert err.value.code == "unallowed_view"


def test_guard_rejects_procore_schema_direct_read():
    with pytest.raises(BlockedQueryError) as err:
        _guard().check("SELECT * FROM procore.rfis")
    assert err.value.code in {"unallowed_view", "unallowed_schema"}


def test_guard_rejects_public_schema_access():
    with pytest.raises(BlockedQueryError) as err:
        _guard().check("SELECT * FROM public.users")
    assert err.value.code in {"unallowed_view", "unallowed_schema"}


def test_guard_rejects_information_schema():
    with pytest.raises(BlockedQueryError) as err:
        _guard().check("SELECT table_name FROM information_schema.tables")
    assert err.value.code in {"unallowed_view", "unallowed_schema"}


def test_guard_rejects_ddl_drop():
    with pytest.raises(BlockedQueryError) as err:
        _guard().check("DROP TABLE rex.v_project_mgmt")
    assert err.value.code == "non_select"


def test_guard_rejects_dml_delete():
    with pytest.raises(BlockedQueryError) as err:
        _guard().check("DELETE FROM rex.chat_messages")
    assert err.value.code == "non_select"


def test_guard_rejects_dml_update():
    with pytest.raises(BlockedQueryError) as err:
        _guard().check("UPDATE rex.chat_messages SET content = 'x'")
    assert err.value.code == "non_select"


def test_guard_rejects_multi_statement_injection():
    with pytest.raises(BlockedQueryError) as err:
        _guard().check(
            "SELECT 1 FROM rex.v_project_mgmt; DELETE FROM rex.chat_messages"
        )
    assert err.value.code == "multiple_statements"


def test_guard_rejects_line_comment():
    with pytest.raises(BlockedQueryError) as err:
        _guard().check("SELECT 1 FROM rex.v_project_mgmt -- sneaky")
    assert err.value.code == "comments_forbidden"


def test_guard_rejects_block_comment():
    with pytest.raises(BlockedQueryError) as err:
        _guard().check("SELECT 1 /* hidden */ FROM rex.v_project_mgmt")
    assert err.value.code == "comments_forbidden"


def test_guard_rejects_unqualified_table():
    with pytest.raises(BlockedQueryError) as err:
        _guard().check("SELECT * FROM some_table")
    assert err.value.code == "unqualified_table"


def test_guard_rejects_empty_query():
    with pytest.raises(BlockedQueryError) as err:
        _guard().check("")
    assert err.value.code == "empty_query"


def test_guard_rejects_set_statement():
    with pytest.raises(BlockedQueryError) as err:
        _guard().check("SET search_path = public")
    assert err.value.code == "non_select"


def test_guard_exposes_the_documented_allowlist():
    expected = {
        "rex.v_project_mgmt",
        "rex.v_financials",
        "rex.v_schedule",
        "rex.v_directory",
        "rex.v_portfolio",
        "rex.v_risk",
        "rex.v_myday",
    }
    assert DEFAULT_ALLOWED_VIEWS == frozenset(expected)
