# Rex OS Frontend Roadmap

> First-pass real frontend roadmap.
> Last reconciled: **2026-04-14** (phases 41–53: production promotion complete).
> Reflects actual implemented state on the `main` branch. Production is live
> at **`main @ d119663`** (phase 41–53 promotion landed at `3148f0c`; `d119663`
> is a post-reconciliation CI workflow fix with no runtime change). The prior
> integration branch `master` is deprecated — see `DEPLOY.md §4c`.
> A screen-data readiness audit is **not** the same thing as this — see `SCREEN_TO_DATA_MAP.md` for that.

---

## 1) Current shipped frontend state

| Metric | Value | Source |
|---|---|---|
| Page components | **32** | `frontend/src/pages/*.jsx` (phase 48 added Companies + People & Members) |
| App routes (HashRouter) | 32 | `frontend/src/App.jsx` |
| Stack | React 18 + Vite 5 + react-router 7 + @sentry/react 8 | `package.json` — Sentry added phase 46, gated by `VITE_SENTRY_DSN` |
| Build output | **~311 modules, ~620 KB raw / ~156 KB gzip** | `vite build` 2026-04-14 — phase 46–50 added ~110 KB of new UI (BuildVersionChip, admin pages, photo upload drawer, error boundary rewrite, responsive CSS) |
| Build identity injection | `__REX_GIT_SHA__`, `__REX_BUILD_TIME__` | `vite.config.js` `define` — sourced from `VERCEL_GIT_COMMIT_SHA` / `RAILWAY_GIT_COMMIT_SHA` / `GITHUB_SHA` at build time |
| Version module | `frontend/src/version.js` | exports `GIT_SHA`, `BUILD_TIME`, `VERSION_INFO` and `main.jsx` pins them to `window.__REX_VERSION__` (read-only) |
| Build version chip | `frontend/src/BuildVersionChip.jsx` (phase 47) | sidebar-bottom chip showing `fe <sha>` + `be <sha>`; click to expand popover with `/api/version` backend identity + environment badge (non-production only) |
| Sentry integration (frontend) | `frontend/src/sentry.js` (phase 46) | `initSentry()` in `main.jsx`, no-op without `VITE_SENTRY_DSN`. **Code-ready, not activated on prod** as of this reconciliation. |
| Error boundary | `frontend/src/ErrorBoundary.jsx` (phase 46 rewrite) | Per-route isolation via `routeKey={location.pathname}` — crash on one route contains and auto-resets on navigation; retry without full page reload; Rex-styled panel; Sentry reporting when enabled |
| Fetch state helper | `frontend/src/fetchState.jsx` (phase 46) | `LoadState` + `classifyError` — distinguishes auth vs network vs empty vs server-error on data-heavy pages |
| CI gates | pytest + vite build | `.github/workflows/ci.yml` runs on every push + PR (phase 42) |
| Deployed smoke | Playwright + curl invariants | `.github/workflows/deployed-smoke.yml` (workflow_dispatch + 6h cron) |
| Shared components | 7 | ui.jsx (Badge/StatCard/Card/Row/PageLoader/Flash/ProgressBar) |
| Shared platform modules | 4 | api.js, auth.jsx, project.jsx, permissions.js |
| Shared write-flow module | 1 | forms.jsx (FormDrawer + **9** input primitives — phase 49 added `FileInput`) |
| Shared file preview module | 1 | preview.jsx (FilePreviewDrawer) |
| Shared notification module | 1 | notifications.jsx (NotificationProvider + bell + drawer) |
| Shared alert callout module | 1 | AlertCallout.jsx (per-page alert surface) |
| CSS theme file | 1 | rex-theme.css — phase 50 added responsive media queries at 900px (off-canvas sidebar + hamburger) and 560px (stat grid collapse, drawer clamp to viewport) |
| Mocked Playwright tests | **14** | `frontend/e2e/smoke.spec.js` (8) + `frontend/e2e/phase46_50.spec.js` (6) — phase 52 added coverage for BuildVersionChip, Portfolio create drawer, Companies, People+Members, Photos upload drawer, Checklist item edit |
| Real-backend e2e | 0 (in-frontend) — covered by backend phase 25/30/35 tests + demo-env browser flight for phase 46–50 | |
| Deployment | Vercel | `rex-os` project in `robertsandrewt-3928s-projects` team; serves `https://rex-os.vercel.app`. **Deployed-verified** 2026-04-14 at bundle `index-gT1ItBVr.js`. |

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
| **Document Management** | Drawings, Specifications, Photos, Correspondence, Attachments | ✅ shipped | full CRUD including **Photos upload + metadata edit + bytes preview** (phases 49, 51, 53) | File preview drawer wired into Drawings, Specifications, Correspondence, Warranties, InsuranceCertificates, Attachments. Photos page has upload drawer with album create-on-upload, taken_at, location, lat/lng, tags. |
| **Field health views** | ExecutionHealth | ✅ shipped | read-first | Aggregated counts + Tasks by status + Manpower + Inspections + Punch summary |
| **Inbox / Operations** | Notifications, AdminJobs | ✅ shipped | mark read, dismiss, run job | AdminJobs is admin/VP-only with `<Navigate to="/" replace>` defense in depth |
| **Admin (phase 48)** | Companies, People & Members | ✅ shipped | full CRUD + project-member create/edit | Admin/VP-only sidebar group. Companies page with insurance/bonding filters + CRUD; People page with detail-panel project-membership management (+ Add button + access-level edit). Both browser-verified on demo + deployed-verified on prod 2026-04-14. |

**Total: 32 page components, all live in production at `main @ d119663`** (phase 41–53 promotion commit was `3148f0c`; `d119663` is a CI-only fix on top with no runtime change).

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
Admin (admin/VP only): Companies · People & Members · Operations
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

### Known UX gaps (post phase 53 — what's still open)
- **`location` filter on Schedule** is wired in shared state and `filteredActivities` logic but has no toolbar input — works programmatically via URL state but not user-settable. Minor.
- **No route loading indicator** between page transitions — relies on each page's own `<PageLoader>` after data fetch starts.
- **No "create user" or invite flow** — new user provisioning is still DB-direct. The People & Members admin page can list/edit existing users and manage their project memberships (phase 48), but there's no "invite a new user via email + signup link" flow. Deferred until there's a clear need.
- **Backend Sentry in prod** — `REX_SENTRY_DSN` unset on prod; backend errors only surface via Railway log scraping. Not a frontend gap but users feel it as "weird bug disappeared."
- **Frontend Sentry in prod** — `VITE_SENTRY_DSN` unset on the Vercel prod project; frontend runtime exceptions are invisible beyond the browser console.
- **Real S3 storage in prod** — still `local`. Photo uploads work but live on the ephemeral Railway disk; a container recycle would lose them. See `DEPLOY.md §1f` for the activation sequence.
- **Real-browser sanity pass on prod post-promotion** — the phase 46–53 build has been API-level verified on prod but the final manual "click through the live prod UI once" check was still open at the time of this reconciliation.

### Closed in phases 46–53 (previously in this list)
- ✅ **Per-route error boundaries** — shipped phase 46. `ErrorBoundary` now wraps `<Routes>` with `routeKey={location.pathname}` for auto-reset on navigation, retry without reload, Sentry reporting when DSN set.
- ✅ **Create/edit project drawer** — shipped phase 48A. Portfolio page has admin **+ New Project** button; edit drawer prefills from `GET /api/projects/{id}`, supports all phase-39 fields including lat/lng, contract_value, square_footage.
- ✅ **Companies admin page** — shipped phase 48B. Full CRUD including phase-39 `mobile_phone` / `website` / `insurance_carrier` / `insurance_expiry` / `bonding_capacity`.
- ✅ **People & Members admin page** — shipped phase 48C. Person CRUD + per-person project-membership create/edit (picks project, access level, primary flag, active flag); graceful 409 messaging on duplicate membership.
- ✅ **Photos upload UI** — shipped phase 49. Multipart form against `POST /api/photos/upload` with album create-on-upload, taken_at, description, location, lat/lng, tags. **Phase 51** fixed the metadata PATCH blocker so filename/taken_at/lat/lng survive round-trip. **Phase 53** added `GET /api/photos/{id}/bytes` for the preview path.
- ✅ **Closeout checklist item edit drawer** — shipped phase 50. Exposes name, category, status, due_date, assigned_person_id, assigned_company_id, notes, spec_division, spec_section.
- ✅ **BuildVersionChip** — shipped phase 47. Sidebar-bottom chip showing FE + BE commit; click to expand popover with full `/api/version` identity.
- ✅ **Responsive shell below tablet** — shipped phase 50 (partial). Media queries at 900px (off-canvas sidebar, hamburger menu in topbar) and 560px (5-up stat grids collapse to 2, drawer clamps to viewport width). Not a full mobile redesign — adequate for narrow-viewport sanity.

### Performance observations
- Bundle size: **~620 KB raw / ~156 KB gzip** (post phase 46–50). Vite still warns about chunks > 500 KB. Consider code-splitting per-page (react.lazy on ScheduleHealth is the obvious first candidate). Advisory, not blocking.
- Notification polling (60s) is a fixed cost for every authenticated user — fine for now but should switch to SSE/WebSocket if user count grows.
- Schedule workbench fetches per-schedule activities sequentially via `Promise.all` — fine for typical projects but could degrade with hundreds of schedules. No pagination currently.
- File preview blob URLs are revoked on cleanup but not when switching between previews rapidly — minor leak risk.

### Accessibility / responsiveness
- **Partial ARIA labels** — phase 50 added labels on key icon-only buttons (notification bell, drawer close, topbar menu, edit buttons in admin tables, membership + Add button). Not comprehensive; keyboard-only navigation hasn't been audited end-to-end.
- **No keyboard navigation** for the Gantt timeline.
- **Responsive layout**: phase 50 added media queries at 900px (off-canvas sidebar + hamburger) and 560px (grid collapse + drawer clamp). This is a tablet/narrow-desktop sanity pass, **not** a full mobile redesign. Behavior below 560px is not formally audited. No explicit phone breakpoint.
- **Color contrast**: not formally audited. The dark purple sidebar and white text pass WCAG AA visually but no Lighthouse run is on file.
- **Focus traps** in drawers: not implemented. ESC works but tab navigation can escape the drawer.

### Frontend testing
- **14 mocked Playwright tests** — all use `page.route` mocks, not a real backend.
  - `smoke.spec.js` (8): login → portfolio, create RFI/punch/daily-log/meeting/change-event/correspondence, read-only-denied
  - `phase46_50.spec.js` (6, phase 52): BuildVersionChip popover, Portfolio create drawer submit, Companies list + create, People detail panel + add project membership, Photos upload drawer opens + file input renders + cancel, Checklists item edit drawer opens with spec fields
- **No real-backend frontend e2e** inside the frontend repo — the backend test suite has 28 tests (`test_phase25/30/35`) that exercise the full HTTP API end-to-end with rollback isolation, and the phase 46–53 flight used the demo environment + a real browser (via the Chrome extension) for the live UI sanity.
- **No component unit tests** — Vitest is not set up.
- **No visual regression tests** — no Chromatic or Percy.

### Build / tooling debt
- ✅ **CI**: `.github/workflows/ci.yml` runs backend pytest + frontend `vite build` on every push + PR (phase 42).
- **ESLint runs locally only** — no pre-commit or pre-push hook. Note: the repo has `npm run lint` in package.json but no `.eslintrc` config file, so the lint script currently fails. Low priority.
- **No TypeScript** — `package.json` includes `@types/react` and `@types/react-dom` but the project is JavaScript with JSX. TS migration would be a big project, not currently planned.
- **No source maps in production build** — debugging from Sentry (when activated) will need source map upload config. Plan for this when flipping frontend Sentry on in prod.

---

## 5) Recommended next frontend sequence

Items 1–7 from the prior version of this list are all shipped — see
"Closed in phases 46–53" above. Remaining work in rough priority order:

1. **Activate frontend Sentry in demo, then prod** — set `VITE_SENTRY_DSN`
   + `VITE_SENTRY_ENV` on the Vercel demo project, redeploy (Vite env is
   build-time), prove one deliberate event in the Sentry dashboard, then
   repeat on prod. Code path (`frontend/src/sentry.js`) is already wired.
2. **Real-browser sanity pass on prod post-promotion** — walk the core
   flight against `https://rex-os.vercel.app` once, log verdicts, close
   the loop. API-level smoke is already green.
3. **Full mobile responsiveness pass** — phase 50 added narrow-desktop
   adaptation (900/560px); a proper phone pass would need one more
   breakpoint + table reflow strategy. Low priority until there's mobile
   user demand.
4. **Lighthouse / accessibility audit** — at minimum tab-trap focus in
   drawers, finish ARIA labels on icon buttons (phase 50 was partial),
   color contrast spot checks, keyboard-only navigation pass.
5. **Code splitting** — bundle is ~620 KB; `react.lazy` on ScheduleHealth
   would shave off significant weight since it pulls in the Gantt. Still
   advisory, not blocking.
6. **Source map upload pipeline** — required before flipping frontend
   Sentry on prod with meaningful stack traces.
7. **Component unit tests for the shared infrastructure** — FormDrawer,
   useFormState, AlertCallout, FilePreviewDrawer, BuildVersionChip. Vitest
   + react-testing-library.
8. **ESLint config** — `npm run lint` script exists but no `.eslintrc`,
   so lint currently fails. Add a minimal config or remove the script.

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
- "Photos page has no upload" — shipped phase 49
- "Photos metadata PATCH silently drops filename/lat/lng/taken_at" — fixed phase 51
- "No file preview" — built in phase 29
- "Schedule workbench is one tab" — it's 5 tabs now
- "No notifications" — built in phase 32
- "No admin operations page" — built in phase 34
- "No create-project / create-company / create-user UI" — shipped phase 48 (Portfolio + Companies admin + People & Members)
- "No per-route error boundaries" — shipped phase 46
- "No responsive media queries" — shipped phase 50 at 900px + 560px
- "Bundle is ~508 KB" — it's ~620 KB post phase 46–50
- "8 mocked Playwright tests" — it's 14 post phase 52
- "30 page components" — it's 32 post phase 48
- "Deploys watch master" — **deploys watch `main`** since 2026-04-14 (see `DEPLOY.md §4a`)

This is a **planning document**, not a screen catalog. The screen catalog lives at `SCREEN_TO_DATA_MAP.md`.
