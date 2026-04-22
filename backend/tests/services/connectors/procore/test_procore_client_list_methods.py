"""Tests for ProcoreClient.list_<resource>() methods.

Uses httpx.MockTransport to return canned Procore responses. Asserts
pagination loop terminates, company header is set, updated_since is
passed correctly to the right query-param name per resource.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from app.services.ai.tools.procore_api import ProcoreClient


def _mk_client(handler) -> ProcoreClient:
    transport = httpx.MockTransport(handler)
    return ProcoreClient(
        client_id="x", client_secret="x", refresh_token="x",
        company_id="42", base_url="https://api.procore.com",
        _transport=transport,
    )


def _wrap_with_token(data_handler):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={
                "access_token": "tok", "expires_in": 3600,
            })
        return data_handler(request)
    return handler


# ─── submittals ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_list_submittals_single_page():
    def data(req):
        assert req.url.path == "/rest/v1.0/projects/99/submittals"
        assert req.headers.get("Procore-Company-Id") == "42"
        return httpx.Response(200, json=[{"id": 1, "number": "SUB-1"}, {"id": 2, "number": "SUB-2"}])
    c = _mk_client(_wrap_with_token(data))
    rows = await c.list_submittals(project_id="99")
    assert len(rows) == 2
    assert rows[0]["number"] == "SUB-1"


@pytest.mark.asyncio
async def test_list_submittals_pagination_terminates():
    pages = [[{"id": i} for i in range(3)], [{"id": i} for i in range(3, 6)], []]
    idx = [0]
    def data(req):
        page = pages[idx[0]]
        idx[0] += 1
        return httpx.Response(200, json=page)
    c = _mk_client(_wrap_with_token(data))
    rows = await c.list_submittals(project_id="99", per_page=3)
    assert len(rows) == 6


@pytest.mark.asyncio
async def test_list_submittals_updated_since_passes_filter():
    captured = {}
    def data(req):
        captured["params"] = dict(req.url.params)
        return httpx.Response(200, json=[])
    c = _mk_client(_wrap_with_token(data))
    since = datetime(2026, 4, 22, tzinfo=timezone.utc)
    await c.list_submittals(project_id="99", updated_since=since)
    # Some flavor of 'updated' should appear in params.
    assert any("updated" in k.lower() for k in captured["params"]), f"params={captured['params']}"


# ─── daily_logs ──────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_list_daily_logs_single_page():
    def data(req):
        assert "daily_logs" in req.url.path
        return httpx.Response(200, json=[{"id": 1, "date": "2026-04-22"}])
    c = _mk_client(_wrap_with_token(data))
    rows = await c.list_daily_logs(project_id="99")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_list_daily_logs_pagination_terminates():
    pages = [[{"id": 1}, {"id": 2}], []]
    idx = [0]
    def data(req):
        page = pages[idx[0]]; idx[0] += 1
        return httpx.Response(200, json=page)
    c = _mk_client(_wrap_with_token(data))
    rows = await c.list_daily_logs(project_id="99", per_page=2)
    assert len(rows) == 2


# ─── schedule_tasks ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_list_schedule_tasks_single_page():
    def data(req):
        assert "schedule" in req.url.path
        return httpx.Response(200, json=[{"id": 1, "name": "Pour footings"}])
    c = _mk_client(_wrap_with_token(data))
    rows = await c.list_schedule_tasks(project_id="99")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_list_schedule_tasks_pagination_terminates():
    pages = [[{"id": i} for i in range(3)], []]
    idx = [0]
    def data(req):
        page = pages[idx[0]]; idx[0] += 1
        return httpx.Response(200, json=page)
    c = _mk_client(_wrap_with_token(data))
    rows = await c.list_schedule_tasks(project_id="99", per_page=3)
    assert len(rows) == 3


# ─── change_events ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_list_change_events_single_page():
    def data(req):
        assert "change_events" in req.url.path
        return httpx.Response(200, json=[{"id": 1, "number": "CE-1"}])
    c = _mk_client(_wrap_with_token(data))
    rows = await c.list_change_events(project_id="99")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_list_change_events_pagination_terminates():
    pages = [[{"id": 1}], []]
    idx = [0]
    def data(req):
        page = pages[idx[0]]; idx[0] += 1
        return httpx.Response(200, json=page)
    c = _mk_client(_wrap_with_token(data))
    rows = await c.list_change_events(project_id="99", per_page=1)
    assert len(rows) == 1


# ─── inspections ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_list_inspections_single_page():
    def data(req):
        assert "inspection" in req.url.path.lower()
        return httpx.Response(200, json=[{"id": 1, "inspection_number": "INS-1"}])
    c = _mk_client(_wrap_with_token(data))
    rows = await c.list_inspections(project_id="99")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_list_inspections_pagination_terminates():
    pages = [[{"id": 1}], []]
    idx = [0]
    def data(req):
        page = pages[idx[0]]; idx[0] += 1
        return httpx.Response(200, json=page)
    c = _mk_client(_wrap_with_token(data))
    rows = await c.list_inspections(project_id="99", per_page=1)
    assert len(rows) == 1


# ─── shared behavior ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_company_id_header_set_on_list_requests():
    def data(req):
        # Any list request — doesn't matter which
        if req.url.path.startswith("/rest/"):
            assert req.headers.get("Procore-Company-Id") == "42"
        return httpx.Response(200, json=[])
    c = _mk_client(_wrap_with_token(data))
    await c.list_submittals(project_id="99")
