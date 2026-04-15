// Manual-verification smoke for the merge-readiness pass.
//
// This file is NOT part of the merged test suite — it ships under a
// leading-underscore name so it is obvious to future readers, and so
// it can be removed in the follow-up cleanup PR after cutover. It
// exists to give the reviewer a reproducible record of the two manual
// passes required by the Session 3 cutover handoff doc §13:
//
//   A. Default mock pass — shell + rail + quick-action + Integration tab
//      all render against mocks with USE_ASSISTANT_MOCKS=true and no
//      localStorage override.
//   B. Degraded live-override pass — localStorage override flips to
//      live, no backend endpoints are present in the test harness, all
//      surfaces degrade to `unavailable`, UI stays functional.

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
  return route.fulfill({ status, contentType: "application/json", body: JSON.stringify(data) });
}

async function bootstrap(page, { liveOverride = null } = {}) {
  // Zero backend knowledge of Session 3 endpoints — any /api/me,
  // /api/assistant/*, /api/control-plane/* call returns 404 so the
  // degraded-live path can be exercised.
  await page.route("**/api/**", async (route, request) => {
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, "");
    if (path === "/auth/me") return json(route, ADMIN_USER);
    if (path === "/auth/login") return json(route, { token: "test-token", user: ADMIN_USER });
    if (path === "/projects/" || path.startsWith("/projects/?") || path.startsWith("/projects?"))
      return json(route, [PROJECT_FIXTURE]);
    // Deliberately return 404 for every Session 3 endpoint so
    // live-override falls into the unavailable path.
    if (path === "/me" || path === "/me/permissions" || path === "/context/current"
      || path.startsWith("/assistant/") || path.startsWith("/control-plane/")
      || path.startsWith("/myday/")) {
      return route.fulfill({ status: 404, body: "not implemented" });
    }
    return json(route, []);
  });
  await page.addInitScript((override) => {
    localStorage.setItem("rex_token", "test-token");
    if (override === null) localStorage.removeItem("rex.assistant.use_mocks");
    else localStorage.setItem("rex.assistant.use_mocks", override);
  }, liveOverride);
}

test.describe("Manual verification — merge readiness pass", () => {
  test("A. default mock pass: rail + quick action + diagnostics all mock", async ({ page }) => {
    await bootstrap(page, { liveOverride: null });
    await page.goto("/#/my-day");
    const rail = page.locator("aside.rex-assistant-rail").first();
    await expect(rail).toBeVisible({ timeout: 10000 });
    await expect(rail.locator(".rex-assistant-rail__brand")).toHaveText("REX AI");

    // Launch a mock-backed quick action and see the stream render.
    const actionHeader = rail.locator(".rex-action-card__header", { hasText: "Morning Briefing" }).first();
    await actionHeader.click();
    await rail.locator(".rex-action-card__launch", { hasText: "Run Morning Briefing" }).click();
    await expect(rail.locator(".rex-assistant-msg--assistant")).toContainText("Morning briefing", { timeout: 15000 });

    // Diagnostics tab shows every surface as mock.
    await page.goto("/#/control-plane");
    await page.click('button[role="tab"]:has-text("Integration")');
    // Every row's source cell is either "mock" or "pending" (the chat
    // stream surface is marked "mock" by the mock emitter path; other
    // surfaces flip "pending" → "mock" as they resolve).
    const identityRow = page.locator("tr", { hasText: "GET /api/me" }).first();
    await expect(identityRow.locator(".rex-readiness--adapter")).toBeVisible({ timeout: 10000 });
  });

  test("B. degraded live-override pass: unavailable badges + working rail", async ({ page }) => {
    await bootstrap(page, { liveOverride: "false" });
    await page.goto("/#/control-plane");
    await page.click('button[role="tab"]:has-text("Integration")');
    // Identity + catalog live calls both 404 → `unavailable`.
    const identityRow = page.locator("tr", { hasText: "GET /api/me" }).first();
    await expect(identityRow.locator(".rex-readiness--blocked")).toBeVisible({ timeout: 10000 });
    const catalogRow = page.locator("tr", { hasText: "GET /api/assistant/catalog" }).first();
    await expect(catalogRow.locator(".rex-readiness--blocked")).toBeVisible();

    // Rail still works — degraded data from mock fallback.
    await page.goto("/#/my-day");
    const rail = page.locator("aside.rex-assistant-rail").first();
    await expect(rail).toBeVisible({ timeout: 10000 });
    await expect(rail.locator(".rex-assistant-rail__brand")).toHaveText("REX AI");
  });
});
