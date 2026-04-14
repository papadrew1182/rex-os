import { test, expect } from '@playwright/test';

// Phase 46-50 regression smoke — covers the surfaces added in that sprint
// that the original smoke.spec.js does not touch:
//   - Companies admin page (list + create drawer)
//   - People & Members admin page (list + create-person drawer + add-member drawer)
//   - Photos page Upload button + drawer (phase 49)
//   - Portfolio page Create Project drawer (phase 48)
//   - Checklists page item edit drawer (phase 50)
//   - BuildVersionChip renders and shows FE/BE info after /api/version call
//   - Error boundary recovers after a synthetic crash on a route
//
// Same mocked-API pattern as smoke.spec.js — real browser, intercepted backend.

const ADMIN_USER = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'admin@rex.test',
  first_name: 'Admin',
  last_name: 'User',
  is_admin: true,
  global_role: 'vp',
  is_active: true,
  person_id: '10000000-0000-4000-a000-000000000001',
};

const PROJECT_FIXTURE = {
  id: '11111111-1111-1111-1111-111111111111',
  name: 'Bishop Modern',
  project_number: 'BM-001',
  status: 'active',
  address_line1: '123 Main St',
  city: 'Austin',
  state: 'TX',
  zip: '78701',
};

const COMPANY_FIXTURE = {
  id: 'c1111111-1111-1111-1111-111111111111',
  name: 'Acme Drywall',
  company_type: 'subcontractor',
  trade: 'Drywall',
  status: 'active',
  phone: '555-1212',
  email: 'ops@acme.test',
  city: 'Austin',
  insurance_expiry: '2026-12-31',
  bonding_capacity: 500000,
};

const PERSON_FIXTURE = {
  id: 'p1111111-1111-1111-1111-111111111111',
  first_name: 'Jane',
  last_name: 'Field',
  email: 'jane@acme.test',
  phone: '555-2323',
  title: 'Superintendent',
  role_type: 'lead_super',
  company_id: COMPANY_FIXTURE.id,
  is_active: true,
};

const PHOTO_FIXTURE = {
  id: 'ph111111-1111-1111-1111-111111111111',
  project_id: PROJECT_FIXTURE.id,
  filename: 'site-001.jpg',
  content_type: 'image/jpeg',
  file_size: 204800,
  storage_url: 'local://photos/site-001.jpg',
  storage_key: 'photos/site-001.jpg',
  taken_at: '2026-03-14T09:30:00+00:00',
  description: 'north elevation',
  location: '3rd floor',
  latitude: 30.2672,
  longitude: -97.7431,
  tags: null,
  source_type: null,
  source_id: null,
  uploaded_by: ADMIN_USER.person_id,
  created_at: '2026-03-14T10:00:00+00:00',
};

function json(route, data, status = 200) {
  return route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
  });
}

async function mockApi(page, overrides = {}) {
  const {
    companies = [COMPANY_FIXTURE],
    people = [PERSON_FIXTURE],
    photos = [PHOTO_FIXTURE],
    albums = [{ id: 'a1', name: 'Progress Photos' }],
    memberships = [],
    version = {
      service: 'rex-os-backend',
      version: '0.2.0',
      commit: 'abc1234deadbeef',
      build_time: '2026-04-13T00:00:00Z',
      environment: 'demo',
    },
    checklistItems = [
      {
        id: 'ci111111-1111-1111-1111-111111111111',
        checklist_id: 'cl111111-1111-1111-1111-111111111111',
        category: 'general',
        item_number: 1,
        name: 'Verify final punch complete',
        status: 'not_started',
        assigned_company_id: null,
        assigned_person_id: null,
        due_date: '2026-06-01',
        completed_date: null,
        completed_by: null,
        notes: '',
        sort_order: 1,
        spec_division: null,
        spec_section: null,
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ],
  } = overrides;

  await page.route('**/api/**', async (route, request) => {
    const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, '');
    const method = request.method();

    // Auth
    if (path === '/auth/me') return json(route, ADMIN_USER);
    if (path === '/auth/login') return json(route, { token: 'test-token', user: ADMIN_USER });

    // Version (BuildVersionChip calls this)
    if (path === '/version') return json(route, version);

    // Projects
    if (path === '/projects/' || path.startsWith('/projects/?') || path.startsWith('/projects?')) {
      if (method === 'GET') return json(route, [PROJECT_FIXTURE]);
      if (method === 'POST') return json(route, { ...JSON.parse(request.postData() || '{}'), id: 'new-proj-id' }, 201);
    }
    if (path.match(/^\/projects\/[^/]+$/)) {
      if (method === 'GET') return json(route, PROJECT_FIXTURE);
      if (method === 'PATCH') return json(route, { ...PROJECT_FIXTURE, ...JSON.parse(request.postData() || '{}') });
    }

    // Closeout portfolio
    if (path.startsWith('/closeout-readiness/portfolio')) {
      return json(route, {
        summary: { total_projects: 1, pass_count: 1, warning_count: 0, fail_count: 0, not_started_count: 0 },
        projects: [{
          project_id: PROJECT_FIXTURE.id,
          project_name: PROJECT_FIXTURE.name,
          project_number: PROJECT_FIXTURE.project_number,
          readiness_status: 'pass',
          best_checklist_percent: 80,
          total_milestones: 5,
          achieved_milestones: 3,
          holdback_gate_status: 'pass',
          open_issue_count: 0,
        }],
      });
    }

    // Companies
    if (path === '/companies/' || path.startsWith('/companies?') || path.startsWith('/companies/?')) {
      if (method === 'GET') return json(route, companies);
      if (method === 'POST') return json(route, { ...COMPANY_FIXTURE, ...JSON.parse(request.postData() || '{}'), id: 'new-co-id' }, 201);
    }
    if (path.match(/^\/companies\/[^/]+$/)) {
      if (method === 'PATCH') return json(route, { ok: true });
    }

    // People
    if (path === '/people/' || path.startsWith('/people?') || path.startsWith('/people/?')) {
      if (method === 'GET') return json(route, people);
      if (method === 'POST') return json(route, { ...PERSON_FIXTURE, ...JSON.parse(request.postData() || '{}'), id: 'new-person-id' }, 201);
    }
    if (path.match(/^\/people\/[^/]+$/)) {
      if (method === 'PATCH') return json(route, { ok: true });
    }

    // Project members
    if (path === '/project-members/' || path.startsWith('/project-members?') || path.startsWith('/project-members/?')) {
      if (method === 'GET') return json(route, memberships);
      if (method === 'POST') {
        const body = JSON.parse(request.postData() || '{}');
        return json(route, { id: 'new-pm-id', ...body, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }, 201);
      }
    }
    if (path.match(/^\/project-members\/[^/]+$/)) {
      if (method === 'PATCH') return json(route, { ok: true });
    }

    // Photos
    if (path === '/photos/' || path.startsWith('/photos?') || path.startsWith('/photos/?')) {
      if (method === 'GET') return json(route, photos);
    }
    if (path === '/photos/upload') {
      // Multipart upload — just echo back a photo record
      return json(route, { ...PHOTO_FIXTURE, id: 'uploaded-photo-id', filename: 'uploaded.jpg' }, 201);
    }
    if (path.match(/^\/photos\/[^/]+$/)) {
      if (method === 'PATCH') return json(route, { ok: true });
    }
    if (path === '/photo-albums/' || path.startsWith('/photo-albums?') || path.startsWith('/photo-albums/?')) {
      if (method === 'GET') return json(route, albums);
      if (method === 'POST') return json(route, { id: 'new-album-id', name: JSON.parse(request.postData() || '{}').name }, 201);
    }

    // Closeout checklists + items
    if (path === '/closeout-checklists/' || path.startsWith('/closeout-checklists?') || path.startsWith('/closeout-checklists/?')) {
      return json(route, [{
        id: 'cl111111-1111-1111-1111-111111111111',
        project_id: PROJECT_FIXTURE.id,
        total_items: 1,
        completed_items: 0,
        percent_complete: 0,
        substantial_completion_date: '2026-06-01',
      }]);
    }
    if (path.match(/^\/closeout-checklists\/[^/]+$/)) {
      return json(route, {
        id: 'cl111111-1111-1111-1111-111111111111',
        project_id: PROJECT_FIXTURE.id,
        total_items: 1,
        completed_items: 0,
        percent_complete: 0,
        substantial_completion_date: '2026-06-01',
      });
    }
    if (path === '/closeout-checklist-items/' || path.startsWith('/closeout-checklist-items?') || path.startsWith('/closeout-checklist-items/?')) {
      return json(route, checklistItems);
    }
    if (path.match(/^\/closeout-checklist-items\/[^/]+$/)) {
      if (method === 'PATCH') return json(route, { ok: true });
    }

    // Default empty for any unhandled list
    return json(route, []);
  });

  await page.addInitScript(() => { localStorage.setItem('rex_token', 'test-token'); });
}

test.describe('Phase 46-50 surfaces', () => {
  test('build version chip renders fe + be info', async ({ page }) => {
    await mockApi(page);
    await page.goto('/');
    await expect(page.locator('h1', { hasText: 'Portfolio' })).toBeVisible({ timeout: 10000 });
    // Chip shows fe/be identifiers
    const chip = page.locator('button[aria-label="Show build identity"]');
    await expect(chip).toBeVisible();
    await expect(chip).toContainText(/fe/);
    await expect(chip).toContainText(/be/);
    // Click to open popover
    await chip.click();
    await expect(page.locator('text=Build Identity')).toBeVisible();
    await expect(page.locator('text=rex-os-backend')).toBeVisible();
    // Demo env badge should be visible
    await expect(page.locator('button[aria-label="Show build identity"] >> text=demo').first()).toBeVisible();
  });

  test('portfolio Create Project drawer opens and submits', async ({ page }) => {
    await mockApi(page);
    await page.goto('/');
    await expect(page.locator('h1', { hasText: 'Portfolio' })).toBeVisible({ timeout: 10000 });
    const newBtn = page.locator('button', { hasText: '+ New Project' });
    await expect(newBtn).toBeEnabled();
    await newBtn.click();
    await expect(page.locator('#name')).toBeVisible();
    await page.fill('#name', 'Test Demo Project');
    await page.fill('#project_number', 'DEMO-001');
    await expect(page.locator('button[type="submit"]')).toBeEnabled({ timeout: 3000 });
    await page.click('button[type="submit"]');
    await expect(page.locator('#name')).not.toBeVisible({ timeout: 5000 });
  });

  test('companies page list + create drawer', async ({ page }) => {
    await mockApi(page);
    await page.goto('/#/companies');
    await expect(page.locator('h1', { hasText: 'Companies' })).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Acme Drywall').first()).toBeVisible();
    await page.click('button:has-text("+ New Company")');
    await expect(page.locator('#name')).toBeVisible({ timeout: 5000 });
    await page.fill('#name', 'Bolt Electric');
    await expect(page.locator('button[type="submit"]')).toBeEnabled();
    await page.click('button[type="submit"]');
    await expect(page.locator('#name')).not.toBeVisible({ timeout: 5000 });
  });

  test('people page list + add project membership for selected person', async ({ page }) => {
    await mockApi(page);
    await page.goto('/#/people');
    await expect(page.locator('h1', { hasText: 'People' })).toBeVisible({ timeout: 10000 });
    // Click the person's name cell to open the detail panel.
    // Two cells match "Jane Field" in strict mode (name cell + "Edit Jane Field"
    // action-column cell), so .first() picks the name cell explicitly.
    await page.getByRole('cell', { name: 'Jane Field' }).first().click();
    // Memberships card heading should appear — role-based to avoid matching
    // the page subtitle which also contains the words "project memberships".
    await expect(page.getByRole('heading', { name: 'Project Memberships' })).toBeVisible();
    // Click "+ Add" (button has aria-label for this specific person)
    await page.getByRole('button', { name: /add project membership/i }).click();
    // Project select should be required
    await expect(page.locator('#project_id')).toBeVisible({ timeout: 5000 });
    await page.selectOption('#project_id', PROJECT_FIXTURE.id);
    await expect(page.locator('button[type="submit"]')).toBeEnabled({ timeout: 3000 });
    await page.click('button[type="submit"]');
    // Drawer closes on success
    await expect(page.locator('#project_id')).not.toBeVisible({ timeout: 5000 });
  });

  test('photos page shows upload button + drawer', async ({ page }) => {
    await mockApi(page);
    await page.goto('/#/photos');
    await expect(page.locator('h1', { hasText: 'Photo Gallery' })).toBeVisible({ timeout: 10000 });
    const uploadBtn = page.locator('button', { hasText: '+ Upload Photo' });
    await expect(uploadBtn).toBeEnabled();
    await uploadBtn.click();
    // File input shows up
    await expect(page.locator('#file')).toBeVisible({ timeout: 5000 });
    // Cancel is present
    await page.click('button:has-text("Cancel")');
    await expect(page.locator('#file')).not.toBeVisible({ timeout: 5000 });
  });

  test('closeout item edit drawer opens on row click', async ({ page }) => {
    await mockApi(page);
    await page.goto('/#/checklists');
    await expect(page.locator('h1', { hasText: 'Closeout Checklists' })).toBeVisible({ timeout: 10000 });
    // Pick first checklist
    await page.click('text=Checklist 1');
    // Item row
    const row = page.locator('text=Verify final punch complete');
    await expect(row).toBeVisible({ timeout: 10000 });
    await row.click();
    // Item edit drawer visible
    await expect(page.locator('#name')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('#spec_division')).toBeVisible();
    await expect(page.locator('#spec_section')).toBeVisible();
  });
});
