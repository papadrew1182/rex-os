// Mobile-overflow regression — iPhone Safari reported horizontal overflow
// on portrait, and a visible horizontal scrollbar in landscape after the
// feat/sidebar-shell merge. The spec runs against every project in
// playwright.config.js; iphone-portrait and iphone-landscape are the
// critical ones, but we also cover desktop Chromium + WebKit to guard
// against regressions at narrower-than-1280 desktop widths.
//
// Strategy: stub every API the shell touches with empty/minimal fixtures
// so we reach the logged-in home without needing real credentials, then
// measure layout. The existing smoke.spec.js follows the same pattern.

import { test, expect } from "@playwright/test";

// ── Fixtures ──────────────────────────────────────────────────────────────

const ADMIN_USER = {
  id: "00000000-0000-0000-0000-000000000001",
  email: "admin@rex.test",
  first_name: "Admin",
  last_name: "User",
  is_admin: true,
  global_role: "vp",
  is_active: true,
};

const BISHOP = {
  id: "11111111-1111-1111-1111-111111111111",
  name: "Bishop Modern",
  project_number: "BM-001",
  status: "active",
};

const JUNGLE_LAKEWOOD = {
  id: "22222222-2222-2222-2222-222222222222",
  name: "Jungle Lakewood",
  project_number: "JL-001",
  status: "active",
};

// Portfolio fixture mirrors the shape rendered by pages/Portfolio.jsx.
const PORTFOLIO_FIXTURE = {
  summary: {
    total_projects: 2,
    pass_count: 0,
    warning_count: 0,
    fail_count: 0,
    not_started_count: 2,
  },
  projects: [
    {
      project_id: BISHOP.id,
      project_name: BISHOP.name,
      project_number: BISHOP.project_number,
      readiness_status: "not_started",
      best_checklist_percent: 0,
      achieved_milestones: 0,
      total_milestones: 0,
      holdback_gate_status: "not_applicable",
      open_issue_count: 0,
    },
    {
      project_id: JUNGLE_LAKEWOOD.id,
      project_name: JUNGLE_LAKEWOOD.name,
      project_number: JUNGLE_LAKEWOOD.project_number,
      readiness_status: "not_started",
      best_checklist_percent: 0,
      achieved_milestones: 0,
      total_milestones: 0,
      holdback_gate_status: "not_applicable",
      open_issue_count: 0,
    },
  ],
};

// Session 3 /api/me envelope — the AppContext fetcher unwraps .user.
const ME_FIXTURE = {
  user: {
    id: "uuid-me",
    email: "admin@rex.test",
    full_name: "Admin User",
    primary_role_key: "VP",
    role_keys: ["VP"],
    legacy_role_aliases: ["VP_PM"],
    project_ids: [BISHOP.id],
    feature_flags: {
      assistant_sidebar: true,
      control_plane_home: true,
      my_day_home: true,
    },
  },
};

const PERMISSIONS_FIXTURE = {
  permissions: [
    "assistant.chat",
    "assistant.catalog.read",
    "portfolio.read",
    "projects.read",
  ],
};

const EMPTY_CATALOG = {
  version: "v1",
  categories: [],
  actions: [],
};

// ── Mock installer ────────────────────────────────────────────────────────

async function installMocks(page) {
  // Seed the legacy AuthProvider so it doesn't bounce to #/login.
  await page.addInitScript(() => {
    localStorage.setItem("rex_token", "test-token");
  });

  await page.route("**/api/**", async (route, request) => {
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, "");
    const json = (data, status = 200) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(data),
      });

    // ── Legacy auth (frontend/src/auth.jsx) ──────────────────────────
    if (path === "/auth/me") return json(ADMIN_USER);
    if (path === "/auth/login")
      return json({ token: "test-token", user: ADMIN_USER });

    // ── Session 3 identity + permissions ─────────────────────────────
    if (path === "/me") return json(ME_FIXTURE);
    if (path === "/me/permissions") return json(PERMISSIONS_FIXTURE);
    if (path === "/context/current") return json({ project_id: BISHOP.id });

    // ── Assistant sidebar data (mocked empty so it renders inert) ────
    if (path === "/assistant/catalog") return json(EMPTY_CATALOG);
    if (path === "/assistant/conversations") return json({ items: [] });

    // ── Projects list (topbar project picker + ProjectProvider) ──────
    if (path === "/projects/" || path.startsWith("/projects?"))
      return json([BISHOP, JUNGLE_LAKEWOOD]);

    // ── Portfolio page data ──────────────────────────────────────────
    if (path.startsWith("/closeout-readiness/portfolio"))
      return json(PORTFOLIO_FIXTURE);

    // ── Notifications badge count ────────────────────────────────────
    if (path.startsWith("/notifications/unread-count"))
      return json({ count: 0 });
    if (path.startsWith("/notifications"))
      return json([]);

    // Default — empty list is safe for list endpoints.
    return json([]);
  });
}

// ── Layout assertions ─────────────────────────────────────────────────────

/**
 * Assert the page has no horizontal overflow, AND that no visible card-
 * shaped element extends past the viewport's right edge. Returns the
 * offenders as part of the error message when it fails, so the test
 * output itself tells you *which* element is bleeding past.
 */
async function assertNoHorizontalOverflow(page) {
  const layout = await page.evaluate(() => {
    const vw = window.innerWidth;
    const docScrollWidth = document.documentElement.scrollWidth;
    const selectors = [
      ".rex-stat-card",
      ".rex-card",
      ".rex-table-wrap",
      ".rex-shell-content",
      ".rex-content",
      ".rex-sidebar",
      "[class*='assistant']", // AssistantSidebar container (class varies by impl)
    ];
    const seen = new Set();
    const offenders = [];
    for (const sel of selectors) {
      for (const el of document.querySelectorAll(sel)) {
        if (seen.has(el) || !el.offsetParent) continue;
        seen.add(el);
        const r = el.getBoundingClientRect();
        if (r.right > vw + 1) {
          offenders.push({
            selector: sel,
            className: String(el.className || "").slice(0, 80),
            right: Math.round(r.right),
            width: Math.round(r.width),
          });
        }
      }
    }
    return { vw, docScrollWidth, offenders };
  });

  const msg = () =>
    `Horizontal overflow detected.\n` +
    `  viewport.innerWidth = ${layout.vw}\n` +
    `  documentElement.scrollWidth = ${layout.docScrollWidth}\n` +
    `  offending elements:\n${layout.offenders
      .map((o) => `    - ${o.selector} (${o.className}) right=${o.right} width=${o.width}`)
      .join("\n") || "    (none)"}`;

  expect(layout.docScrollWidth, msg()).toBeLessThanOrEqual(layout.vw + 1);
  expect(layout.offenders, msg()).toEqual([]);
}

// ── Tests ─────────────────────────────────────────────────────────────────

test.describe("Portfolio (/) — no horizontal overflow", () => {
  test.beforeEach(async ({ page }) => {
    await installMocks(page);
  });

  test("landing + key cards visible, table wrap contained", async ({ page }, testInfo) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: /portfolio closeout readiness/i })
    ).toBeVisible({ timeout: 10000 });

    // Wait for at least one stat card to render (data fetched).
    await expect(page.locator(".rex-stat-card").first()).toBeVisible();

    await assertNoHorizontalOverflow(page);

    // Also assert the top action row ("+ New Project" button) doesn't
    // clip off-screen. It's the most likely victim of a shared flex
    // nowrap regression.
    const actionRow = page.getByRole("button", { name: /new project/i });
    if (await actionRow.count()) {
      const box = await actionRow.first().boundingBox();
      const vw = testInfo.project.use.viewport?.width ?? 1280;
      expect(
        box && box.x + box.width <= vw + 1,
        `"+ New Project" button clips off-screen: ${JSON.stringify(box)} at vw=${vw}`
      ).toBe(true);
    }
  });
});
