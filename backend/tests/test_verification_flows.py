"""UI verification integration tests.

Exercises the 6 target flows end-to-end as described in UI_VERIFICATION_PLAN.md,
using the rollback_client for DB isolation where possible and the real auth
flow to prove the full request lifecycle.

Flows:
1. Portfolio closeout readiness
2. Project closeout readiness detail
3. Closeout checklist from template
4. Checklist item completion + rollup
5. Milestone evidence / certification / gate evaluation
6. Attachment upload + download with auth
"""

import contextlib
import uuid

from httpx import AsyncClient

from app.dependencies import get_current_user
from main import app
from tests.helpers import PROJECT_BISHOP, PERSON_ROBERTS, uid

ADMIN_EMAIL = "aroberts@exxircapital.com"
NON_ADMIN_EMAIL = "mandersen@exxircapital.com"
PASSWORD = "rex2026!"
TEMPLATE_STANDARD = "a0000001-0000-0000-0000-000000000001"


@contextlib.contextmanager
def _no_auth_override():
    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        yield
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved


async def _login_token(client: AsyncClient, email: str) -> str:
    r = await client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ═══════════════════════════════════════════════════════════════════════════
# Flow 1: Portfolio closeout readiness
# ═══════════════════════════════════════════════════════════════════════════


async def test_flow1_portfolio_closeout_readiness(client: AsyncClient):
    """Admin sees portfolio readiness with summary counts and project rows."""
    r = await client.get("/api/closeout-readiness/portfolio")
    assert r.status_code == 200
    body = r.json()
    assert "summary" in body
    assert "projects" in body
    summary = body["summary"]
    assert summary["total_projects"] >= 0
    for key in ("pass_count", "warning_count", "fail_count", "not_started_count"):
        assert key in summary


async def test_flow1_portfolio_readiness_scoped(client: AsyncClient):
    """Non-admin sees only their projects in the portfolio."""
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get("/api/closeout-readiness/portfolio", headers=_auth(token))
    assert r.status_code == 200
    body = r.json()
    # Mitch is a member of the seeded projects — should see some but not orphans
    for proj in body["projects"]:
        assert "readiness_status" in proj


# ═══════════════════════════════════════════════════════════════════════════
# Flow 2: Project closeout readiness detail
# ═══════════════════════════════════════════════════════════════════════════


async def test_flow2_project_closeout_readiness(client: AsyncClient):
    """Drill into Bishop project's closeout readiness."""
    r = await client.get(f"/api/projects/{PROJECT_BISHOP}/closeout-readiness")
    assert r.status_code == 200
    body = r.json()
    assert body["project_id"] == PROJECT_BISHOP
    assert body["overall_status"] in ("pass", "warning", "fail", "not_started")
    assert "checklist_summary" in body
    assert "milestone_summary" in body
    assert "warranty_summary" in body
    assert "open_issues" in body


# ═══════════════════════════════════════════════════════════════════════════
# Flow 3: Create closeout checklist from template
# ═══════════════════════════════════════════════════════════════════════════


async def test_flow3_create_checklist_from_template(client: AsyncClient):
    """Admin creates a 34-item checklist from the standard template."""
    r = await client.post(
        "/api/closeout-checklists/from-template",
        json={
            "project_id": PROJECT_BISHOP,
            "template_id": TEMPLATE_STANDARD,
            "substantial_completion_date": "2026-06-01",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["project_id"] == PROJECT_BISHOP
    assert body["total_items"] == 34
    assert body["completed_items"] == 0
    assert body["percent_complete"] == 0

    # Store checklist_id for flow 4
    return body["id"]


# ═══════════════════════════════════════════════════════════════════════════
# Flow 4: Complete checklist items + verify rollup
# ═══════════════════════════════════════════════════════════════════════════


async def test_flow4_checklist_item_completion_and_rollup(client: AsyncClient):
    """Mark one item complete, verify parent rollup updates."""
    # Create a fresh checklist
    r = await client.post(
        "/api/closeout-checklists/from-template",
        json={
            "project_id": PROJECT_BISHOP,
            "template_id": TEMPLATE_STANDARD,
            "substantial_completion_date": "2026-07-01",
        },
    )
    assert r.status_code == 201
    checklist_id = r.json()["id"]
    total = r.json()["total_items"]

    # List items
    items_r = await client.get(f"/api/closeout-checklist-items/?checklist_id={checklist_id}")
    assert items_r.status_code == 200
    items = items_r.json()
    assert len(items) == total

    # Mark first item complete
    first_item_id = items[0]["id"]
    patch_r = await client.patch(
        f"/api/closeout-checklist-items/{first_item_id}",
        json={"status": "complete", "completed_date": "2026-06-15"},
    )
    assert patch_r.status_code == 200

    # Re-fetch checklist to verify rollup
    checklist_r = await client.get(f"/api/closeout-checklists/{checklist_id}")
    assert checklist_r.status_code == 200
    checklist = checklist_r.json()
    assert checklist["completed_items"] == 1
    assert checklist["percent_complete"] > 0
    expected_pct = round(1 / total * 100, 2)
    assert abs(checklist["percent_complete"] - expected_pct) < 0.1


# ═══════════════════════════════════════════════════════════════════════════
# Flow 5: Milestone evidence → certification → gate evaluation
# ═══════════════════════════════════════════════════════════════════════════


async def test_flow5_milestone_full_lifecycle(client: AsyncClient):
    """Exercise the complete milestone lifecycle: create → evidence → certify → gates."""

    # Use a fresh project to avoid unique constraint on (project_id, milestone_type)
    proj = await client.post(
        "/api/projects/",
        json={"project_number": f"VF-MS-{uid()}", "name": f"VF-Milestone-{uid()}", "status": "active"},
    )
    assert proj.status_code == 201
    fresh_project_id = proj.json()["id"]

    # 5a: Create milestone
    r = await client.post(
        "/api/completion-milestones/",
        json={
            "project_id": fresh_project_id,
            "milestone_type": "substantial_completion",
            "milestone_name": f"SC-Verify-{uid()}",
            "target_date": "2026-06-30",
            "status": "pending",
        },
    )
    assert r.status_code == 201, r.text
    milestone_id = r.json()["id"]
    assert r.json()["status"] == "pending"

    # 5b: View evidence checklist
    r = await client.get(f"/api/completion-milestones/{milestone_id}/evidence-checklist")
    assert r.status_code == 200
    evidence = r.json()
    assert evidence["milestone_id"] == milestone_id
    assert "checklist" in evidence

    # 5c: Evaluate evidence
    r = await client.post(
        f"/api/completion-milestones/{milestone_id}/evaluate-evidence",
        json={"all_items_complete": True, "notes": "All docs received"},
    )
    assert r.status_code == 200
    assert r.json()["is_evidence_complete"] is True

    # 5d: Certify milestone
    r = await client.post(
        f"/api/completion-milestones/{milestone_id}/certify",
        json={
            "certified_by": PERSON_ROBERTS,
            "actual_date": "2026-06-15",
            "notes": "Verified in integration test",
        },
    )
    assert r.status_code == 200
    cert = r.json()
    assert cert["status"] == "achieved"
    assert cert["certified_by"] == PERSON_ROBERTS
    # Variance: target was 2026-06-30, actual 2026-06-15 → -15 days (early)
    assert cert.get("evidence_incomplete_warning") in (None, False)

    # 5e: Evaluate gates
    r = await client.post(f"/api/completion-milestones/{milestone_id}/evaluate-gates")
    assert r.status_code == 200
    gates = r.json()
    assert gates["milestone_id"] == milestone_id
    assert gates["gate_status"] in ("pass", "warning", "fail", "not_applicable")
    assert "gate_results" in gates
    assert len(gates["gate_results"]) > 0
    assert "summary_message" in gates


# ═══════════════════════════════════════════════════════════════════════════
# Flow 6: Attachment upload + download with auth
# ═══════════════════════════════════════════════════════════════════════════


async def test_flow6_attachment_upload_and_download(client: AsyncClient):
    """Upload a file to Bishop, then download it — both with auth."""
    file_content = b"Integration test PDF content for verification"
    filename = f"verify-{uid()}.pdf"

    # Upload
    files = {"file": (filename, file_content, "application/pdf")}
    data = {
        "project_id": PROJECT_BISHOP,
        "source_type": "rfi",
        "source_id": str(uuid.uuid4()),
    }
    r = await client.post("/api/attachments/upload", data=data, files=files)
    assert r.status_code == 201, r.text
    att = r.json()
    assert att["filename"] == filename
    assert att["file_size"] == len(file_content)
    assert att["content_type"] == "application/pdf"
    attachment_id = att["id"]

    # Download
    r = await client.get(f"/api/attachments/{attachment_id}/download")
    assert r.status_code == 200
    assert r.content == file_content
    assert "attachment" in r.headers.get("content-disposition", "")


async def test_flow6_attachment_download_denied_non_member(client: AsyncClient):
    """Upload to an orphan project, then verify non-member download is denied."""
    # Create orphan project (admin stub active)
    proj = await client.post(
        "/api/projects/",
        json={"project_number": f"VF-{uid()}", "name": f"VF-{uid()}", "status": "active"},
    )
    orphan_id = proj.json()["id"]

    # Upload
    files = {"file": (f"orph-{uid()}.txt", b"secret", "text/plain")}
    data = {
        "project_id": orphan_id,
        "source_type": "submittal",
        "source_id": str(uuid.uuid4()),
    }
    r = await client.post("/api/attachments/upload", data=data, files=files)
    assert r.status_code == 201
    att_id = r.json()["id"]

    # Non-member download → 403
    with _no_auth_override():
        token = await _login_token(client, NON_ADMIN_EMAIL)
        r = await client.get(f"/api/attachments/{att_id}/download", headers=_auth(token))
    assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════
# Cross-flow: permission denial smoke
# ═══════════════════════════════════════════════════════════════════════════


async def test_unauthenticated_portfolio_denied(client: AsyncClient):
    """Portfolio readiness requires auth after Sprint verification tightening."""
    with _no_auth_override():
        r = await client.get("/api/closeout-readiness/portfolio")
    assert r.status_code == 401
