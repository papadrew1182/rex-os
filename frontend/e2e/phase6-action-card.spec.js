// Phase 6 action card end-to-end smoke.
//
// TODO (enable when running against a real dev env):
// Prerequisites:
//   - Backend running on the configured baseURL with:
//       - REX_ENABLE_SCHEDULER disabled (optional; not strictly required)
//       - ANTHROPIC_API_KEY set
//       - A seeded admin user (aroberts@exxircapital.com / rex2026!)
//   - Frontend dev server running (npm run dev)
//   - The LLM must pick the `create_task` tool for the "create a task…"
//     prompt. If it picks another tool, rewrite the prompt or reduce
//     temperature in the backend to make this deterministic.
//
// After those are set, remove `.skip` and run:
//   cd frontend && npx playwright test phase6-action-card.spec.js --headed

import { test, expect } from "@playwright/test";

test.skip("create_task auto-commits inline and can be undone within 60s", async ({ page }) => {
  // 1. Log in
  await page.goto("/login");
  await page.getByLabel(/email/i).fill("aroberts@exxircapital.com");
  await page.getByLabel(/password/i).fill("rex2026!");
  await page.getByRole("button", { name: /sign in|log in/i }).click();

  // 2. Navigate to the assistant sidebar
  await page.goto("/");

  // 3. Trigger create_task via the assistant composer. The selector here
  //    is intentionally loose — tighten to whatever the real composer
  //    textbox uses when enabling this test.
  const composer = page.getByLabel("Message the assistant");
  await composer.fill("create a task to check the duct conflict at grid B/4");
  await composer.press("Enter");

  // 4. Expect a committed action card with an Undo button.
  const card = page.locator(".rex-action-card--committed").first();
  await expect(card).toBeVisible({ timeout: 15000 });
  await expect(card).toContainText(/Create task/i);
  await expect(card).toContainText(/Undo/i);

  // 5. Click Undo; expect card to flip to undone state.
  await card.getByRole("button", { name: /undo/i }).click();
  await expect(page.locator(".rex-action-card--undone").first()).toBeVisible();
});
