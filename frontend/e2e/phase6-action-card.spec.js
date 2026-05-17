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

test.skip("create_task auto-commits inline and can be undone within 60s", async ({ page }) => {
  const actionId = "act-e2e-1";

  await page.route("**/*", async (route, request) => {
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, "");
    const method = request.method();

    if (path === "/auth/me") return json(route, ADMIN_USER);
    if (path === "/auth/login") return json(route, { token: "test-token", user: ADMIN_USER });
    if (path === "/projects/" || path.startsWith("/projects/?") || path.startsWith("/projects?")) {
      return json(route, [PROJECT_FIXTURE]);
    }
    if (path.startsWith("/closeout-readiness/portfolio")) {
      return json(route, {
        summary: { total_projects: 1, pass_count: 1, warning_count: 0, fail_count: 0, not_started_count: 0 },
        projects: [],
      });
    }

    if (path.startsWith("/assistant/chat") && method === "POST") {
      let payload = {};
      try { payload = JSON.parse(request.postData() || "{}"); } catch {}

      if (!payload.stream) {
        return json(route, { accepted: true, conversation_id: "conv-e2e-1" });
      }

      const body = [
        'event: conversation.created\ndata: {"conversation_id":"conv-e2e-1"}\n\n',
        'event: message.started\ndata: {"conversation_id":"conv-e2e-1","sender_type":"assistant"}\n\n',
        'event: action_auto_committed\ndata: {"action_id":"act-e2e-1","tool_slug":"create_task","result":{"title":"check the duct conflict at grid B/4"}}\n\n',
        'event: message.delta\ndata: {"delta":" Task created.","accumulated":"Task created."}\n\n',
        'event: message.completed\ndata: {"conversation_id":"conv-e2e-1","content":"Task created."}\n\n',
      ].join("");

      return route.fulfill({
        status: 200,
        headers: {
          "content-type": "text/event-stream",
          "cache-control": "no-cache",
        },
        body,
      });
    }

    if (path === `/actions/${actionId}/undo` && method === "POST") {
      return json(route, { ok: true, action_id: actionId });
    }

    if (!url.pathname.includes("/api/") && !path.startsWith("/assistant/chat")) {
      return route.continue();
    }
    return json(route, []);
  });

  await page.addInitScript(() => {
    localStorage.setItem("rex_token", "test-token");
    localStorage.setItem("rex.assistant.use_mocks", "true");
    localStorage.removeItem("rex.assistant.ui");
  });

  await page.goto("/#/my-day");

  const launchCard = page.locator(".rex-myday__action-card", { hasText: "Morning Briefing" }).first();
  await expect(launchCard).toBeVisible({ timeout: 15000 });
  await launchCard.click();

  const card = page.locator(".rex-action-card--committed").first();
  await expect(card).toBeVisible({ timeout: 15000 });
  await expect(card).toContainText(/Create task/i);
  await expect(card.getByRole("button", { name: /^Undo$/i })).toBeVisible();

  await card.getByRole("button", { name: /^Undo$/i }).click();
  await expect(page.locator(".rex-action-card--undone").first()).toBeVisible({ timeout: 10000 });
});
