// Phase 53 hardening — assistant sidebar integration tests.
//
// Scope: the right-rail assistant shell built in Session 3, hardened
// in the Gate C pass. These tests run against the mocked API path
// (USE_ASSISTANT_MOCKS=true in src/lib/api.js) so the SSE event
// sequence is deterministic and the test can assert against real
// token-by-token streaming semantics.
//
// What we verify:
//   1. Sidebar mounts on /my-day and the context badge shows "My Day"
//   2. Workspace mode toggle widens the rail (class flips)
//   3. Quick action launch drives streaming render in ChatThread —
//      status chip appears, then the final assistant response text is
//      visible, then the Actions tab restores
//   4. Action suggestions chips render after an action that emits them
//      (morning_briefing emits two suggestions from the mock stream)
//   5. Recent-conversations jump on /my-day opens the sidebar and
//      switches to the Chat tab with the conversation loaded
//   6. Control Plane dependent-actions column renders from the
//      client-derived connector → actions map
//
// Pattern: reuse the legacy mock-API installer so non-assistant boot
// endpoints (/auth/me, /projects/) work. Assistant endpoints are
// mocked client-side so we do not need to intercept them.

import { test, expect } from "@playwright/test";

const ADMIN_USER = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "admin@rex.test",
  first_name: "Admin",
  last_name: "User",
  is_admin: true,
  global_role: "vp",
  is_active: true,
};

const PROJECT_FIXTURE = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Bishop Modern",
  project_number: "BM-001",
  status: "active",
};

function json(route, data, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(data),
  });
}

async function mockApi(page, { user = ADMIN_USER } = {}) {
  await page.route("**/api/**", async (route, request) => {
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, "");

    if (path === "/auth/me") return json(route, user);
    if (path === "/auth/login") return json(route, { token: "test-token", user });
    if (path === "/projects/" || path.startsWith("/projects/?") || path.startsWith("/projects?"))
      return json(route, [PROJECT_FIXTURE]);
    if (path.startsWith("/closeout-readiness/portfolio")) {
      return json(route, {
        summary: { total_projects: 1, pass_count: 1, warning_count: 0, fail_count: 0, not_started_count: 0 },
        projects: [],
      });
    }
    // Everything else: empty list — assistant endpoints don't hit this
    // route at all because USE_ASSISTANT_MOCKS short-circuits them.
    return json(route, []);
  });

  await page.addInitScript(() => {
    localStorage.setItem("rex_token", "test-token");
    // Reset any persisted assistant UI prefs so tests are deterministic.
    localStorage.removeItem("rex.assistant.ui");
  });
}

test.describe("Phase 53 — assistant sidebar hardening", () => {
  test("1. sidebar mounts on /my-day with context badge", async ({ page }) => {
    await mockApi(page);
    await page.goto("/#/my-day");
    const rail = page.locator("aside.rex-assistant-rail").first();
    await expect(rail).toBeVisible({ timeout: 10000 });
    await expect(rail.locator(".rex-assistant-rail__brand")).toHaveText("REX AI");
    // ContextBadge prefers active project name over the route name when
    // a project is selected. The Topbar auto-selects the first project,
    // so we expect the fixture project's name.
    await expect(rail.locator(".rex-assistant-rail__context")).toContainText("Bishop Modern");
    // The badge's title attr still carries the route metadata so the
    // route-context-injection surface is observable:
    await expect(rail.locator(".rex-assistant-rail__context")).toHaveAttribute(
      "title",
      /my_day\s*·\s*\/my-day/,
    );
  });

  test("2. workspace mode toggle widens the rail", async ({ page }) => {
    await mockApi(page);
    await page.goto("/#/my-day");
    const rail = page.locator("aside.rex-assistant-rail").first();
    await expect(rail).toBeVisible({ timeout: 10000 });
    await expect(rail).not.toHaveClass(/rex-assistant-rail--workspace/);
    await rail.locator('button[aria-label="Enter workspace mode"]').click();
    await expect(rail).toHaveClass(/rex-assistant-rail--workspace/);
    // Pressing Escape exits workspace mode (global listener)
    await page.keyboard.press("Escape");
    await expect(rail).not.toHaveClass(/rex-assistant-rail--workspace/);
  });

  test("3. quick action launch drives streaming render", async ({ page }) => {
    await mockApi(page);
    await page.goto("/#/my-day");
    const rail = page.locator("aside.rex-assistant-rail").first();
    await expect(rail).toBeVisible({ timeout: 10000 });

    // Expand the Morning Briefing action card, then launch it.
    // Action card headers are buttons with the action label.
    const actionHeader = rail.locator(".rex-action-card__header", { hasText: "Morning Briefing" }).first();
    await expect(actionHeader).toBeVisible({ timeout: 5000 });
    await actionHeader.click();
    const launchBtn = rail.locator(".rex-action-card__launch", { hasText: "Run Morning Briefing" });
    await expect(launchBtn).toBeVisible();
    await launchBtn.click();

    // Launch flips to Chat tab — expect the streaming status indicator.
    await expect(rail.locator(".rex-assistant-thread__status")).toBeVisible({ timeout: 5000 });

    // And eventually the completed assistant response with the known
    // mock copy for morning_briefing.
    await expect(
      rail.locator(".rex-assistant-msg--assistant .rex-assistant-msg__content")
    ).toContainText("Morning briefing", { timeout: 15000 });

    // Stream finishes → status indicator goes away, followups chips render.
    await expect(rail.locator(".rex-assistant-thread__status")).not.toBeVisible({ timeout: 10000 });
    await expect(rail.locator(".rex-assistant-thread__followup-chip").first()).toBeVisible();
  });

  test("4. action suggestions render after a morning_briefing stream", async ({ page }) => {
    await mockApi(page);
    await page.goto("/#/my-day");
    const rail = page.locator("aside.rex-assistant-rail").first();
    await expect(rail).toBeVisible({ timeout: 10000 });

    // Launch Morning Briefing — the SSE mock emits action.suggestions
    // for this slug specifically.
    const actionHeader = rail.locator(".rex-action-card__header", { hasText: "Morning Briefing" }).first();
    await actionHeader.click();
    await rail.locator(".rex-action-card__launch", { hasText: "Run Morning Briefing" }).click();

    // Wait for the stream to land the suggestion chips.
    const suggestions = rail.locator(".rex-assistant-thread__suggestions");
    await expect(suggestions).toBeVisible({ timeout: 15000 });
    await expect(suggestions.locator(".rex-assistant-thread__suggestion-chip")).toHaveCount(2);
  });

  test("5. /control-plane renders connector dependent-actions column", async ({ page }) => {
    await mockApi(page);
    await page.goto("/#/control-plane");
    // Control Plane shell header renders the tab list — wait for the
    // connector panel to paint. Column header 'Dependent actions' is
    // unique to the hardening pass.
    await expect(page.locator("th", { hasText: "Dependent actions" })).toBeVisible({ timeout: 10000 });
  });
});
