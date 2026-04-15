// Phase 54 — live-integration adapter tests.
//
// These tests flip the assistant lane into LIVE mode via the runtime
// override (`localStorage['rex.assistant.use_mocks'] = 'false'`), then
// intercept the published contract endpoints with fixtures that match
// Session 3 charter shapes. That exercises the adapter's pass-through
// path end-to-end — including the Integration diagnostics panel in
// Control Plane, which should report the surfaces as "live" when a
// contract-matching fixture is served, and "unavailable" when the
// fixture drifts from contract.
//
// Pattern:
//   - addInitScript flips the localStorage override BEFORE React boots
//   - page.route intercepts /api/me, /api/me/permissions, /api/assistant/*
//     with published-contract JSON
//   - navigate to /#/control-plane, open the Integration tab, read the
//     source badges
//
// Why this test cares about UI assertions instead of unit-testing the
// adapter directly: the adapter's liveOrMock() path runs inside the
// real bundle, so the DOM-reflected source state is the most honest
// signal that live-mode integration works without shipping broken bits.

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

// Contract-matching /api/me payload (Session 3 charter).
const ME_LIVE_FIXTURE = {
  user: {
    id: "uuid-me",
    email: "aroberts@exxircapital.com",
    full_name: "Andrew Roberts",
    primary_role_key: "VP",
    role_keys: ["VP"],
    legacy_role_aliases: ["VP_PM"],
    project_ids: [PROJECT_FIXTURE.id],
    feature_flags: { assistant_sidebar: true, control_plane_home: true, my_day_home: true },
  },
};

// Contract-matching /api/assistant/catalog payload (minimal but valid).
const CATALOG_LIVE_FIXTURE = {
  version: "v1",
  categories: [{ key: "OPERATIONS", label: "Operations" }],
  actions: [
    {
      slug: "morning_briefing",
      legacy_aliases: ["C-22"],
      label: "Morning Briefing",
      category: "OPERATIONS",
      description: "On-demand briefing with all alerts",
      params_schema: [],
      risk_tier: "read_only",
      readiness_state: "live",
      required_connectors: [],
      role_visibility: ["VP", "PM", "GENERAL_SUPER", "LEAD_SUPER", "ASSISTANT_SUPER", "ACCOUNTANT"],
      enabled: true,
      can_run: true,
    },
  ],
};

// Drifted catalog — readiness_state not in vocabulary. Should trip the
// probe and land the surface as "unavailable".
const CATALOG_DRIFTED_FIXTURE = {
  version: "v1",
  categories: [],
  actions: [
    {
      slug: "mystery",
      label: "Mystery Action",
      category: "OPS",
      readiness_state: "probably_live",
      role_visibility: ["VP"],
      enabled: true,
      can_run: true,
    },
  ],
};

function json(route, data, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(data),
  });
}

async function installMocks(page, { catalogFixture }) {
  await page.route("**/api/**", async (route, request) => {
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, "");
    const method = request.method();

    // Legacy auth — shell gate
    if (path === "/auth/me") return json(route, ADMIN_USER);
    if (path === "/auth/login") return json(route, { token: "test-token", user: ADMIN_USER });
    if (path === "/projects/" || path.startsWith("/projects/?") || path.startsWith("/projects?"))
      return json(route, [PROJECT_FIXTURE]);

    // Live contract surfaces (Session 3)
    if (path === "/me") return json(route, ME_LIVE_FIXTURE);
    if (path === "/me/permissions")
      return json(route, { permissions: ["assistant.chat", "assistant.catalog.read", "control_plane.view"] });
    if (path === "/context/current") {
      return json(route, {
        project: null,
        route: { name: "control_plane", path: "/control-plane" },
        page_context: { surface: "control_plane", entity_type: null, entity_id: null, filters: {} },
        assistant_defaults: { suggested_action_slugs: ["morning_briefing"] },
      });
    }
    if (path === "/assistant/catalog") return json(route, catalogFixture);
    if (path === "/assistant/conversations") return json(route, { items: [] });

    // Control Plane surfaces — valid minimal shapes
    if (path === "/control-plane/connectors") return json(route, { items: [{ key: "procore", label: "Procore", status: "adapter_pending" }] });
    if (path === "/control-plane/automations") return json(route, { items: [] });
    if (path === "/control-plane/queue") return json(route, { items: [] });

    // Default: empty
    return json(route, []);
  });

  // Bootstrap: token + flip live mode BEFORE the bundle reads the override.
  await page.addInitScript(() => {
    localStorage.setItem("rex_token", "test-token");
    localStorage.setItem("rex.assistant.use_mocks", "false");
  });
}

test.describe("Phase 54 — live-integration adapter", () => {
  test("1. diagnostics panel reports LIVE for valid contract fixtures", async ({ page }) => {
    await installMocks(page, { catalogFixture: CATALOG_LIVE_FIXTURE });
    await page.goto("/#/control-plane");

    // Click the Integration tab in the control plane tab bar.
    await page.click('button[role="tab"]:has-text("Integration")');

    // Find the row for /api/me — it should show the "live" badge.
    const identityRow = page.locator("tr", { hasText: "GET /api/me" }).first();
    await expect(identityRow).toBeVisible({ timeout: 10000 });
    await expect(identityRow.locator(".rex-readiness--live")).toBeVisible();

    // Catalog row should also be live.
    const catalogRow = page.locator("tr", { hasText: "GET /api/assistant/catalog" }).first();
    await expect(catalogRow.locator(".rex-readiness--live")).toBeVisible();

    // Rollup summary should contain "partially live" or "fully live".
    const summary = page.locator(".rex-integration-summary");
    await expect(summary).toContainText(/live/i);
  });

  test("2. diagnostics panel reports UNAVAILABLE when catalog drifts from contract", async ({ page }) => {
    await installMocks(page, { catalogFixture: CATALOG_DRIFTED_FIXTURE });
    await page.goto("/#/control-plane");
    await page.click('button[role="tab"]:has-text("Integration")');

    const catalogRow = page.locator("tr", { hasText: "GET /api/assistant/catalog" }).first();
    await expect(catalogRow).toBeVisible({ timeout: 10000 });
    await expect(catalogRow.locator(".rex-readiness--blocked")).toBeVisible();
    // The drifted readiness value should surface as a probe issue.
    await expect(catalogRow).toContainText(/probably_live/);
  });

  test("3. assistant rail still renders when one surface is unavailable", async ({ page }) => {
    await installMocks(page, { catalogFixture: CATALOG_DRIFTED_FIXTURE });
    await page.goto("/#/my-day");
    // Sidebar mounts — feature flag came from /api/me which was valid.
    const rail = page.locator("aside.rex-assistant-rail").first();
    await expect(rail).toBeVisible({ timeout: 10000 });
    // Because catalog drifted, the adapter fell back to the mock
    // catalog and the Actions tab still renders actions.
    await expect(rail.locator(".rex-assistant-rail__brand")).toHaveText("REX AI");
  });

  test("4. runtime override toggle is present and interactive", async ({ page }) => {
    await installMocks(page, { catalogFixture: CATALOG_LIVE_FIXTURE });
    await page.goto("/#/control-plane");
    await page.click('button[role="tab"]:has-text("Integration")');
    // The runtime override already reads "false" (live) so the "Go live" button is disabled.
    await expect(page.locator('button:has-text("Go live")')).toBeDisabled();
    // Force mock is enabled (we can flip to mock mode).
    await expect(page.locator('button:has-text("Force mock")')).toBeEnabled();
  });
});
