# Rex OS Frontend Roadmap

> First-pass real frontend roadmap.
> Last reconciled: **2026-04-12** (post phase 39).
> Reflects actual implemented state on the master branch.
> A screen-data readiness audit is **not** the same thing as this — see `SCREEN_TO_DATA_MAP.md` for that.

---

## 1) Current shipped frontend state

| Metric | Value | Source |
|---|---|---|
| Page components | 30 | `frontend/src/pages/*.jsx` |
| App routes (HashRouter) | 30 | `frontend/src/App.jsx` |
| Stack | React 18 + Vite 5 + react-router 7 | `package.json` |
| Build output | 80 modules, ~508 KB raw / ~122 KB gzip | `vite build` (phase 40 reconciliation run) |
| Shared components | 7 | ui.jsx (Badge/StatCard/Card/Row/PageLoader/Flash/ProgressBar) |
| Shared platform modules | 4 | api.js, auth.jsx, project.jsx, permissions.js |
| Shared write-flow module | 1 | forms.jsx (FormDrawer + 8 input primitives) |
| Shared file preview module | 1 | preview.jsx (FilePreviewDrawer) |
| Shared notification module | 1 | notifications.jsx (NotificationProvider + bell + drawer) |
| Shared alert callout module | 1 | AlertCallout.jsx (per-page alert surface) |
| CSS theme file | 1 | rex-theme.css (single-file design system, ~10 KB) |
| Mocked Playwright tests | 8 | `frontend/e2e/smoke.spec.js` |
| Real-backend e2e | 0 (in-frontend) — covered by backend phase 25/30/35 tests | |
| Deployment | Vercel | `vercel.json`, `.vercel/project.json` |

**Stack details:**
- React 18.3, react-dom 18.3, react-router-dom 7.14
- Vite 5.4 (HashRouter, dev proxy `/api → localhost:9000`, prod uses `VITE_API_URL`)
- No state management library (React state + a few contexts)
- No CSS framework; single-file CSS variables + utility classes
- No icon library; emoji + text glyphs only
- ESLint 8 + react / react-hooks / react-refresh plugins
- Playwright 1.59 for smoke tests
- @vitejs/plugin-react for fast refresh

---

## 2) Screen family maturity matrix

| Family | Pages | Maturity | Write flows | Notes |
|---|---|---|---|---|
| **Auth** | Login | ✅ shipped | login | Redirects unauthenticated users; bcrypt verified server-side |
| **Portfolio / Readiness** | Portfolio, ProjectReadiness | ✅ shipped | read-first | Closeout-readiness flagship; status badges, KPI cards, milestone health |
| **Schedule workbench** | ScheduleHealth (5 tabs) | ✅ deep | read + filter persistence in URL | Gantt + Activities + Lookahead + Critical Path + Health; CSV/Print export; shared right-side detail panel; phase 38 fields exposed |
| **Closeout & Warranty** | Checklists, Milestones, Warranties, OmManuals | ✅ shipped | full CRUD on warranties + om_manuals; checklist item toggle | Includes evidence, certification, gate evaluation workflows; new O&M Manuals page from phase 39 |
| **Compliance** | InsuranceCertificates | ✅ shipped | full CRUD | Global (not project-scoped); auto-status refresh button; expiry color coding |
| **Financials** | BudgetOverview, PayApplications, Commitments, ChangeOrders | ✅ shipped | full CRUD | Includes nested line items (commitment line items, change event line items) and PCO/CCO display |
| **Field Ops** | RfiManagement, PunchList, SubmittalManagement, DailyLogs, Inspections, Tasks, Meetings, Observations, SafetyIncidents | ✅ shipped | full CRUD | All have FormDrawer create/edit; nested children for Daily Log manpower entries, Inspection items, Meeting action items; phase 39 contributing fields on Observations |
| **Document Management** | Drawings, Specifications, Photos, Correspondence, Attachments | ✅ shipped | full CRUD on drawings/specs/correspondence; **Photos: edit-only metadata** (no upload UI) | File preview drawer wired into Drawings, Specifications, Correspondence, Warranties, InsuranceCertificates, Attachments |
| **Field health views** | ExecutionHealth | ✅ shipped | read-first | Aggregated counts + Tasks by status + Manpower + Inspections + Punch summary |
| **Inbox / Operations** | Notifications, AdminJobs | ✅ shipped | mark read, dismiss, run job | AdminJobs is admin/VP-only with `<Navigate to="/" replace>` defense in depth |

**Total: 30 page components, all live in production.**

---

## 3) Shared UX / platform systems already built

### App shell
- **HashRouter** — chosen for compatibility with file:// preview and simple Vercel deployment (no SPA rewrites needed for path routing)
- **`Shell` component** in `App.jsx` — sidebar (220px dark purple), topbar (54px white with project context + bell), content area (`rex-content`)
- **`AuthProvider`** wraps Shell; renders `<Login>` when no user
- **`ProjectProvider`** wraps Shell content; provides `useProject()` with `projects`, `selected`, `selectedId`, `select(id)`
- **`NotificationProvider`** wraps Shell content; polls `/api/notifications/unread-count` every 60s

### Navigation structure
```
Overview:        Portfolio
Inbox:           Notifications
Financials:      Budget Overview · Pay Applications · Commitments · Change Orders
Field Ops:       RFIs · Punch List · Submittals · Daily Logs · Inspections · Tasks ·
                 Meetings · Observations · Safety Incidents
Document Mgmt:   Drawings · Specifications · Photos · Correspondence
Closeout & Warranty: Warranties · O&M Manuals
Compliance:      Insurance Certificates
Project:         Schedule Health · Execution Health · Checklists · Milestones · Attachments
Admin (admin/VP only): Operations
```

### Write-flow layer (`forms.jsx`)
- **`FormDrawer`** — slide-in right-side panel with title/subtitle, save/cancel/reset, dirty-form discard guard, ESC to close, delete confirmation (when `mode==="edit"`), inline error/success Flash, submit spinner, edit-vs-create button label
- **`useFormState(initial)`** — minimal form state with dirty tracking; resets when a new initial reference is passed; `setField`, `reset`, `setAll`
- **Field primitives**: `Field`, `NumberField`, `DateField`, `TimeField`, `TextArea`, `Select`, `Checkbox` — all share label + error display conventions
- **`WriteButton`** — permission-aware action button that auto-disables when `usePermissions().canWrite` is false
- **`cleanPayload(values, allowEmpty)`** — strips null/empty before POST/PATCH

### Permission UX (`permissions.js`)
- **`usePermissions()`** returns `{ user, isAdmin, isVp, isAdminOrVp, canWrite, canFieldWrite, canDelete }`
- Frontend gating is optimistic — `canWrite = isAdminOrVp` for the visible-affordance level. Backend remains the source of truth and will 403/404 if a non-permitted action sneaks through.
- AdminJobs page additionally redirects via `<Navigate to="/" replace>` if `!isAdminOrVp`.

### File preview (`preview.jsx`)
- **`FilePreviewDrawer`** component — fetches via auth-gated `/api/attachments/{id}/download`, builds a blob URL, renders PDFs via `<iframe>` and images via `<img>`, falls back to download for unsupported types
- Accepts a `directUrl` prop for entities like Drawings whose `image_url` is a public URL (bypasses the download endpoint)
- Wired into 6 pages: Attachments, Drawings, Specifications, Correspondence, Warranties, InsuranceCertificates
- Cleans up blob URLs in `useEffect` cleanup; ESC closes the drawer

### Schedule workbench (`pages/ScheduleHealth.jsx`)
- **5 tabs**: Gantt (default), Health, Activities, Lookahead, Critical Path
- **Lifted state** at the parent level: `activities`, `schedules`, filters, selected activity for the shared right-side detail panel
- **URL persistence** via hash query string (`readUrlState` / `writeUrlState`) — filters survive reload and tab switches
- **Persistent filter toolbar** above tabs: search, schedule selector, WBS root, assigned company, assigned person, cost code, critical-only checkbox, Clear button
- **Single shared right-side detail panel** with predecessor/successor lookup via `/api/activity-links`, constraint lookup via `/api/schedule-constraints`
- **Gantt** is hand-rolled with absolute-positioned divs (no react-gantt dep): split layout, WBS hierarchy expand/collapse, scroll-sync, today marker, zoom levels (week/month/quarter), bar layers (planned/baseline/actual/percent fill)
- **CSV export**: inline `downloadCsv` helper, no dependencies (Activities + Critical Path)
- **Print export**: opens new window with branded HTML/CSS, calls `window.print()` (Activities, Lookahead by week, Critical Path)
- **Phase 38 fields** wired into all 4 surfaces: start_variance_days, finish_variance_days, free_float_days

### Notifications UX (`notifications.jsx` + `pages/Notifications.jsx`)
- **NotificationBell** — topbar button with red unread count badge; click opens slide-in drawer
- **NotificationDrawer** — most recent 20 notifications, severity-tinted left borders, mark-read / dismiss / open / view-all / mark-all-read
- **Notifications page** — full filterable inbox with severity / domain / scope filters and 4 KPI cards
- **Polling**: 60s interval via `setInterval` with cleanup in `useEffect` cleanup
- **`AlertCallout`** — per-page in-context alert surface (phase 37); used on Schedule, Warranties, Insurance, RFIs, Submittals, Punch List

### CSS / design system (`rex-theme.css`)
- Single CSS file with CSS custom properties for the entire palette
- Dark purple sidebar (`#2D1B4E`), accent purple (`#6b45a1`), purple table headers, solid uppercase status badges
- Syne 700/800 for headings, DM Sans 400-700 for body
- Utility classes for grid (`rex-grid-2/3/4/5`), stat cards (left border 3px accent + color modifiers), tables (purple thead, striped rows, hover), badges (5 color variants), drawer overlays, form groups, search bars, empty states, tabs
- **Status: stable.** No design-system rewrite planned.

---

## 4) Frontend technical debt / polish backlog

### Known UX gaps
- **`location` filter on Schedule** is wired in shared state and `filteredActivities` logic but has no toolbar input — works programmatically via URL state but not user-settable. Minor.
- **No route loading indicator** between page transitions — relies on each page's own `<PageLoader>` after data fetch starts.
- **No global error boundary on the route level** — `ErrorBoundary` exists in `App.jsx` but only wraps the entire `<Routes>` element. A page error shows "Something went wrong" with no per-page recovery.
- **No "create project" UI** — projects are seeded at the DB level. The new `latitude`/`longitude` fields from phase 39 have no edit surface.
- **No "create company / vendor" UI** — companies are seeded at the DB level. The new `mobile_phone`/`website` fields from phase 39 have no edit surface either.
- **No "create user" or invite flow** — user provisioning is DB-direct.
- **Photos**: no upload UI (deferred). Edit-metadata only.
- **Closeout checklist items**: spec_division/spec_section are now **displayed** but not editable from the UI. Full edit drawer for individual items is not built.

### Performance observations
- Bundle size: 508 KB raw / 122 KB gzip — Vite warns about chunks > 500 KB (we're now just over). Consider code-splitting per-page (react.lazy on ScheduleHealth is the obvious first candidate).
- Notification polling (60s) is a fixed cost for every authenticated user — fine for now but should switch to SSE/WebSocket if user count grows.
- Schedule workbench fetches per-schedule activities sequentially via `Promise.all` — fine for typical projects but could degrade with hundreds of schedules. No pagination currently.
- File preview blob URLs are revoked on cleanup but not when switching between previews rapidly — minor leak risk.

### Accessibility / responsiveness
- **No explicit ARIA labels** on most icon-only buttons (notification bell, drawer close, etc.).
- **No keyboard navigation** for the Gantt timeline.
- **Mobile responsiveness**: untested. The dense table layouts and 220px sidebar would be cramped under 1024px viewport. No media queries currently.
- **Color contrast**: not formally audited. The dark purple sidebar and white text pass WCAG AA visually but no Lighthouse run is on file.
- **Focus traps** in drawers: not implemented. ESC works but tab navigation can escape the drawer.

### Frontend testing
- **8 mocked Playwright smoke tests** — all use `page.route` mocks, not a real backend. Coverage:
  1. Login → portfolio
  2. Create RFI as admin
  3. Create punch item as admin
  4. Create daily log as admin
  5. Create meeting as admin
  6. Create change event as admin
  7. Create correspondence as admin
  8. Read-only user can't perform write
- **No real-backend frontend e2e** — instead, the backend test suite has 28 tests (`test_phase25/30/35`) that exercise the full HTTP API end-to-end with rollback isolation.
- **No component unit tests** — Vitest is not set up.
- **No visual regression tests** — no Chromatic or Percy.

### Build / tooling debt
- **No CI** — frontend `npm run build` is only enforced manually.
- **ESLint runs locally only** — no pre-commit or pre-push hook.
- **No TypeScript** — `package.json` includes `@types/react` and `@types/react-dom` but the project is JavaScript with JSX. TS migration would be a big project, not currently planned.
- **No source maps in production build** — debugging from Sentry (when added) will need source map upload config.

---

## 5) Recommended next frontend sequence

In rough priority order:

1. **Per-page error boundaries** — wrap each `<Route>` with a recoverable fallback so one page crashing doesn't kill the entire SPA shell.
2. **Mobile responsiveness pass** — at minimum add a hamburger sidebar for <1024px viewports and let critical pages (Portfolio, Notifications) reflow. Defer full mobile redesign.
3. **CI workflow** — `.github/workflows/ci.yml` running `npm run build` and `npm run test:e2e` on PR. Same workflow can run backend pytest.
4. **Project + Company create/edit forms** — close the loop on phase 39 lat/lng + mobile/website fields.
5. **Photo upload UI** — multipart form against the existing `/api/attachments/upload` endpoint; only blocked by storage backend choice in prod.
6. **Closeout checklist item edit drawer** — expose spec_division/spec_section + the rest of the item fields for editing.
7. **Sentry / error tracking integration** — frontend errors are currently invisible to the team.
8. **Lighthouse / accessibility audit** — at minimum tab-trap focus in drawers, ARIA labels on icon buttons, color contrast spot checks.
9. **Code splitting if bundle > 600 KB** — react.lazy on heavy pages (Schedule workbench is the obvious first candidate).
10. **Component unit tests for the shared infrastructure** — FormDrawer, useFormState, AlertCallout, FilePreviewDrawer. Vitest + react-testing-library.

---

## 6) Deferred / intentionally later items

- **Drag-to-reschedule on Gantt** — explicitly out of scope by sprint brief; would require server-side reschedule semantics + dependency cascades.
- **Dependency arrows on Gantt bars** — explicitly out of scope; predecessor/successor data is surfaced via the detail panel instead.
- **Real-time updates** (SSE / WebSocket) — pull-based notifications work fine for current scale.
- **Storybook / design system docs** — not justified for current screen count.
- **TypeScript migration** — would require porting 30 page components + shared modules; defer until/unless the team grows.
- **OCR / annotation / document AI** — explicitly excluded by sprint brief.
- **Mobile native apps** — explicitly out of scope.
- **Bonus / scorecard / performance dashboards** — explicitly out of scope until product design pass.
- **Per-user notification preference matrix** — backend doesn't expose this yet; can add later.
- **API versioning UI** — no breaking response changes are planned; can add when needed.

---

## 7) Document hygiene

This file should be updated whenever:
- A new screen family ships
- Shared infrastructure (forms, preview, notifications, callout) gets a major addition
- The bundle size moves by >50 KB
- The deployment topology changes
- A frontend technical-debt category gets resolved

**Stale claims to watch out for:**
- "Read-first" labeling on pages that now have full CRUD (most do as of phase 20)
- "Photos page is read-only" — partially true: edit-metadata only, no upload
- "No file preview" — built in phase 29
- "Schedule workbench is one tab" — it's 5 tabs now
- "No notifications" — built in phase 32
- "No admin operations page" — built in phase 34

This is a **planning document**, not a screen catalog. The screen catalog lives at `SCREEN_TO_DATA_MAP.md`.
