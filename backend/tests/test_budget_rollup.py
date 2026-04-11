"""Budget rollup math helper tests."""

import uuid
from httpx import AsyncClient

PROJECT_BISHOP = "40000000-0000-4000-a000-000000000001"
BOGUS_UUID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

def _uid(): return uuid.uuid4().hex[:8]


async def _project(c: AsyncClient) -> str:
    r = await c.post("/api/projects/", json={"name": f"Budg-{_uid()}", "status": "active"})
    return r.json()["id"]


async def _cost_code(c: AsyncClient, project_id: str) -> str:
    r = await c.post("/api/cost-codes/", json={
        "project_id": project_id, "code": f"CC-{_uid()}", "name": f"CC-{_uid()}",
        "cost_type": "labor",
    })
    return r.json()["id"]


async def _budget_line(c: AsyncClient, project_id: str, cc_id: str, **kw) -> dict:
    p = {
        "project_id": project_id, "cost_code_id": cc_id,
        "original_budget": 100000, "approved_changes": 0,
        "committed_costs": 0, "direct_costs": 0, "pending_changes": 0,
    }
    p.update(kw)
    r = await c.post("/api/budget-line-items/", json=p)
    assert r.status_code == 201
    return r.json()


# ── Read-only rollup ────────────────────────────────────────────────────────

async def test_rollup_basic_math(client: AsyncClient):
    pid = await _project(client)
    cc = await _cost_code(client, pid)
    line = await _budget_line(
        client, pid, cc,
        original_budget=100000, approved_changes=5000,
        committed_costs=60000, direct_costs=10000, pending_changes=2000,
    )
    r = await client.get(f"/api/budget-line-items/{line['id']}/rollup")
    assert r.status_code == 200
    body = r.json()
    assert body["revised_budget"] == 105000  # 100000 + 5000
    assert body["projected_cost"] == 72000   # 60000 + 10000 + 2000
    assert body["over_under"] == 33000        # 105000 - 72000


async def test_rollup_negative_over_under(client: AsyncClient):
    """projected_cost > revised_budget -> negative over_under."""
    pid = await _project(client)
    cc = await _cost_code(client, pid)
    line = await _budget_line(
        client, pid, cc,
        original_budget=50000, approved_changes=0,
        committed_costs=60000, direct_costs=10000, pending_changes=0,
    )
    r = await client.get(f"/api/budget-line-items/{line['id']}/rollup")
    body = r.json()
    assert body["revised_budget"] == 50000
    assert body["projected_cost"] == 70000
    assert body["over_under"] == -20000


async def test_rollup_404(client: AsyncClient):
    r = await client.get(f"/api/budget-line-items/{BOGUS_UUID}/rollup")
    assert r.status_code == 404


# ── Refresh single ──────────────────────────────────────────────────────────

async def test_refresh_persists_rollup(client: AsyncClient):
    pid = await _project(client)
    cc = await _cost_code(client, pid)
    # Create with stale stored values
    line = await _budget_line(
        client, pid, cc,
        original_budget=100000, approved_changes=5000,
        committed_costs=60000, direct_costs=10000, pending_changes=2000,
        revised_budget=999, projected_cost=999, over_under=999,  # stale
    )
    r = await client.post(f"/api/budget-line-items/{line['id']}/refresh-rollup")
    assert r.status_code == 200
    body = r.json()
    assert body["revised_budget"] == 105000
    assert body["projected_cost"] == 72000
    assert body["over_under"] == 33000


async def test_refresh_404(client: AsyncClient):
    r = await client.post(f"/api/budget-line-items/{BOGUS_UUID}/refresh-rollup")
    assert r.status_code == 404


# ── Bulk refresh ────────────────────────────────────────────────────────────

async def test_bulk_refresh_project(client: AsyncClient):
    pid = await _project(client)
    cc = await _cost_code(client, pid)
    await _budget_line(client, pid, cc, original_budget=100, approved_changes=10, committed_costs=50, revised_budget=0, projected_cost=0)
    await _budget_line(client, pid, cc, original_budget=200, approved_changes=20, committed_costs=100, revised_budget=0, projected_cost=0)
    await _budget_line(client, pid, cc, original_budget=300, approved_changes=30, committed_costs=150, revised_budget=0, projected_cost=0)

    r = await client.post(f"/api/budget-line-items/refresh-rollups?project_id={pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["total_line_items"] == 3
    assert body["updated_count"] == 3

    # Second call should be idempotent — no updates needed
    r2 = await client.post(f"/api/budget-line-items/refresh-rollups?project_id={pid}")
    assert r2.json()["updated_count"] == 0
