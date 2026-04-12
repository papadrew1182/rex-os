import { test, expect } from '@playwright/test';

// ── Test fixtures ─────────────────────────────────────────────────────────
const ADMIN_USER = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'admin@rex.test',
  first_name: 'Admin',
  last_name: 'User',
  is_admin: true,
  global_role: 'vp',
  is_active: true,
};

const READONLY_USER = {
  id: '00000000-0000-0000-0000-000000000002',
  email: 'viewer@rex.test',
  first_name: 'Viewer',
  last_name: 'Only',
  is_admin: false,
  global_role: null,
  is_active: true,
};

const PROJECT_FIXTURE = {
  id: '11111111-1111-1111-1111-111111111111',
  name: 'Test Project',
  project_number: 'TP-001',
  status: 'active',
};

/** Fulfill a route with JSON, setting the correct Content-Type header. */
function json(route, data, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
  });
}

// ── Mock API installer ────────────────────────────────────────────────────
async function mockApi(page, { user = ADMIN_USER, rfis = [], punch = [], dailyLogs = [], meetings = [], correspondence = [], photos = [], albums = [], changeEvents = [], lineItems = [] } = {}) {
  await page.route('**/api/**', async (route, request) => {
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, '');
    const method = request.method();

    // Auth
    if (path === '/auth/me') return json(route, user);
    if (path === '/auth/login') return json(route, { token: 'test-token', user });

    // Project list
    if (path === '/projects/' || path.startsWith('/projects/?') || path.startsWith('/projects?')) return json(route, [PROJECT_FIXTURE]);

    // Closeout readiness portfolio — needs summary + projects shape
    if (path.startsWith('/closeout-readiness/portfolio')) return json(route, {
      summary: { total_projects: 1, pass_count: 1, warning_count: 0, fail_count: 0, not_started_count: 0 },
      projects: [{
        project_id: PROJECT_FIXTURE.id,
        project_name: PROJECT_FIXTURE.name,
        project_number: PROJECT_FIXTURE.project_number,
        readiness_status: 'pass',
        best_checklist_pct: 80,
        milestones_total: 5,
        milestones_achieved: 3,
        holdback_status: 'pass',
        open_issues: 0,
      }],
    });

    // RFIs
    if (path === '/rfis/' || path.startsWith('/rfis?')) {
      if (method === 'GET') return json(route, rfis);
      if (method === 'POST') return json(route, { ...JSON.parse(request.postData() || '{}'), id: 'new-rfi-id' }, 201);
    }
    if (path.startsWith('/rfis/')) {
      if (method === 'PATCH') return json(route, { ok: true });
    }

    // Punch
    if (path === '/punch-items/' || path.startsWith('/punch-items?')) {
      if (method === 'GET') return json(route, punch);
      if (method === 'POST') return json(route, { ...JSON.parse(request.postData() || '{}'), id: 'new-punch-id' }, 201);
    }
    if (path.startsWith('/punch-items/')) {
      if (method === 'PATCH') return json(route, { ok: true });
    }

    // People / Companies / Cost codes / Drawings (lookup endpoints)
    if (path.startsWith('/people')) return json(route, [{ id: 'p1', first_name: 'Alice', last_name: 'Builder' }]);
    if (path.startsWith('/companies')) return json(route, [{ id: 'c1', name: 'Acme Sub' }]);
    if (path.startsWith('/cost-codes')) return json(route, []);
    if (path === '/drawings/' || path.startsWith('/drawings?')) return json(route, []);
    if (path.startsWith('/drawing-areas')) return json(route, []);
    if (path.startsWith('/drawing-revisions')) return json(route, []);
    if (path.startsWith('/submittal-packages')) return json(route, []);
    if (path.startsWith('/specifications')) return json(route, []);
    if (path.startsWith('/schedule-activities')) return json(route, []);
    if (path.startsWith('/billing-periods')) return json(route, []);
    if (path.startsWith('/commitments') && method === 'GET') return json(route, []);

    // Daily logs
    if (path === '/daily-logs/' || path.startsWith('/daily-logs?')) {
      if (method === 'GET') return json(route, dailyLogs);
      if (method === 'POST') return json(route, { ...JSON.parse(request.postData() || '{}'), id: 'new-dl-id' }, 201);
    }
    if (path.match(/\/daily-logs\/[^/]+\/summary/)) return json(route, { daily_log_id: 'x', total_workers: 0, total_hours: 0, unique_companies: 0 });
    if (path.match(/\/projects\/[^/]+\/manpower-summary/)) return json(route, { total_logs: 0, total_workers: 0, total_hours: 0, average_workers_per_log: 0, by_company: [] });

    // Manpower entries
    if (path === '/manpower-entries/' || path.startsWith('/manpower-entries?')) {
      if (method === 'GET') return json(route, []);
      if (method === 'POST') return json(route, { id: 'new-mp-id' }, 201);
    }

    // Meetings
    if (path === '/meetings/' || path.startsWith('/meetings?')) {
      if (method === 'GET') return json(route, meetings);
      if (method === 'POST') return json(route, { ...JSON.parse(request.postData() || '{}'), id: 'new-mtg-id' }, 201);
    }
    if (path === '/meeting-action-items/' || path.startsWith('/meeting-action-items?')) {
      if (method === 'GET') return json(route, []);
      if (method === 'POST') return json(route, { id: 'new-ai-id' }, 201);
    }

    // Change events
    if (path === '/change-events/' || path.startsWith('/change-events?')) {
      if (method === 'GET') return json(route, changeEvents);
      if (method === 'POST') return json(route, { ...JSON.parse(request.postData() || '{}'), id: 'new-ce-id' }, 201);
    }
    if (path === '/change-event-line-items/' || path.startsWith('/change-event-line-items?')) {
      if (method === 'GET') return json(route, lineItems);
      if (method === 'POST') return json(route, { id: 'new-li-id' }, 201);
    }
    if (path.match(/\/change-events\/[^/]+\/detail/)) return json(route, { change_event: changeEvents[0] || {}, line_items: lineItems, pcos: [], ccos: [] });

    // Correspondence
    if (path === '/correspondence/' || path.startsWith('/correspondence?')) {
      if (method === 'GET') return json(route, correspondence);
      if (method === 'POST') return json(route, { ...JSON.parse(request.postData() || '{}'), id: 'new-corr-id' }, 201);
    }
    if (path.startsWith('/correspondence/')) {
      if (method === 'PATCH') return json(route, { ok: true });
    }

    // Photos
    if (path === '/photos/' || path.startsWith('/photos?')) {
      if (method === 'GET') return json(route, photos);
    }
    if (path.startsWith('/photos/')) {
      if (method === 'PATCH') return json(route, { ok: true });
    }
    if (path === '/photo-albums/' || path.startsWith('/photo-albums?')) {
      return json(route, albums);
    }

    // Attachments
    if (path.startsWith('/attachments')) return json(route, []);

    // Default: empty array for any unhandled list endpoint
    return json(route, []);
  });

  // Pre-set token so the auth bootstraps
  await page.addInitScript(() => {
    localStorage.setItem('rex_token', 'test-token');
  });
}

// ── Tests ─────────────────────────────────────────────────────────────────
//
// Note: Field components from forms.jsx use id={name} (not name={name}),
// so selectors use #id rather than input[name="..."].

test.describe('Rex OS smoke', () => {
  test('1. login screen and portfolio load', async ({ page }) => {
    await mockApi(page);
    await page.goto('/');
    await expect(page.locator('h1', { hasText: 'Portfolio' })).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Test Project').first()).toBeVisible();
  });

  test('2. create an RFI as admin', async ({ page }) => {
    await mockApi(page);
    await page.goto('/#/rfis');
    await expect(page.locator('h1', { hasText: 'RFI' })).toBeVisible({ timeout: 10000 });
    const newBtn = page.locator('button', { hasText: '+ New RFI' });
    await expect(newBtn).toBeEnabled();
    await newBtn.click();
    // Field uses id=rfi_number
    await expect(page.locator('#rfi_number')).toBeVisible();
    await page.fill('#rfi_number', 'RFI-001');
    await page.fill('#subject', 'Test Subject');
    await page.fill('#question', 'Test question?');
    await page.click('button[type="submit"]');
    // Drawer should close on success
    await expect(page.locator('#rfi_number')).not.toBeVisible({ timeout: 5000 });
  });

  test('3. create a punch item as admin', async ({ page }) => {
    await mockApi(page);
    await page.goto('/#/punch-list');
    await expect(page.locator('h1', { hasText: 'Punch' })).toBeVisible({ timeout: 10000 });
    await page.click('button:has-text("+ New Punch Item")');
    await expect(page.locator('#punch_number')).toBeVisible({ timeout: 5000 });
    await page.fill('#punch_number', '1');
    await page.fill('#title', 'Repair drywall');
    await page.click('button[type="submit"]');
    await expect(page.locator('#punch_number')).not.toBeVisible({ timeout: 5000 });
  });

  test('4. create a daily log as admin', async ({ page }) => {
    await mockApi(page);
    await page.goto('/#/daily-logs');
    await expect(page.locator('h1', { hasText: 'Daily' })).toBeVisible({ timeout: 10000 });
    await page.click('button:has-text("+ New Daily Log")');
    await expect(page.locator('#log_date')).toBeVisible({ timeout: 5000 });
    // Use fill then dispatchEvent to ensure React synthetic event fires on date input
    const today = new Date().toISOString().slice(0, 10);
    await page.fill('#log_date', today);
    await page.locator('#log_date').dispatchEvent('change');
    // Wait for submit to become enabled, then click
    await expect(page.locator('button[type="submit"]')).toBeEnabled({ timeout: 3000 });
    await page.click('button[type="submit"]');
    await expect(page.locator('#log_date')).not.toBeVisible({ timeout: 5000 });
  });

  test('5. create a meeting as admin', async ({ page }) => {
    await mockApi(page);
    await page.goto('/#/meetings');
    await expect(page.locator('h1', { hasText: 'Meetings' })).toBeVisible({ timeout: 10000 });
    await page.click('button:has-text("+ New Meeting")');
    await expect(page.locator('#title')).toBeVisible({ timeout: 5000 });
    await page.fill('#title', 'Weekly OAC');
    // meeting_type and meeting_date are required
    await page.fill('#meeting_type', 'oac');
    const today = new Date().toISOString().slice(0, 10);
    await page.fill('#meeting_date', today);
    await page.locator('#meeting_date').dispatchEvent('change');
    await expect(page.locator('button[type="submit"]')).toBeEnabled({ timeout: 3000 });
    await page.click('button[type="submit"]');
    await expect(page.locator('#title')).not.toBeVisible({ timeout: 5000 });
  });

  test('6. create a change event as admin', async ({ page }) => {
    await mockApi(page);
    await page.goto('/#/change-orders');
    await expect(page.locator('h1', { hasText: 'Change' })).toBeVisible({ timeout: 10000 });
    await page.click('button:has-text("+ New Change Event")');
    await expect(page.locator('#title')).toBeVisible({ timeout: 5000 });
    await page.fill('#title', 'Test CE');
    await page.fill('#event_number', 'CE-001');
    await expect(page.locator('button[type="submit"]')).toBeEnabled({ timeout: 3000 });
    await page.click('button[type="submit"]');
    await expect(page.locator('#title')).not.toBeVisible({ timeout: 5000 });
  });

  test('7. create correspondence as admin', async ({ page }) => {
    await mockApi(page);
    await page.goto('/#/correspondence');
    await expect(page.locator('h1', { hasText: 'Correspondence' })).toBeVisible({ timeout: 10000 });
    await page.click('button:has-text("+ New")');
    await expect(page.locator('#correspondence_number')).toBeVisible({ timeout: 5000 });
    await page.fill('#correspondence_number', 'CORR-001');
    await page.fill('#subject', 'Test letter');
    // Select a correspondence_type (required field — also marks form dirty)
    await page.selectOption('#correspondence_type', 'letter');
    await expect(page.locator('button[type="submit"]')).toBeEnabled({ timeout: 3000 });
    await page.click('button[type="submit"]');
    await expect(page.locator('#correspondence_number')).not.toBeVisible({ timeout: 5000 });
  });

  test('8. read-only user cannot perform a write action', async ({ page }) => {
    await mockApi(page, { user: READONLY_USER });
    await page.goto('/#/rfis');
    await expect(page.locator('h1', { hasText: 'RFI' })).toBeVisible({ timeout: 10000 });
    const newBtn = page.locator('button', { hasText: '+ New RFI' });
    await expect(newBtn).toBeDisabled();
  });
});
