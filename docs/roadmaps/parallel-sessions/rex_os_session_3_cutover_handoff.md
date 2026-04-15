# Session 3 — sidebar shell cutover & operations handoff

Status: ready to merge  
Branch: `feat/sidebar-shell`  
Commits: `ee8f7dd` → `f5beb0d` → `adcd606` (+ this merge-readiness pass)  
Owners: frontend lane  
Last updated: 2026-04-14

This document is the single page a developer or operator needs to (1)
understand what `feat/sidebar-shell` delivers, (2) cut over from mocks to
live endpoints when Sessions 1 and 2 land, and (3) roll back if cutover
misbehaves. It is written to be self-contained — read this file, then
read the three source files it points at, and you will have the full
picture without needing to replay the commit history.

---

## 1. What landed, by commit

### `ee8f7dd` — persistent shell + first-pass Session 3 surfaces
- `AssistantSidebar` persistent right rail mounted in `App.jsx`, present
  on every route, feature-flag + permission gated.
- Reducer-driven assistant state (`useAssistantState.js`) — React Context
  + `useReducer`, no state library.
- Catalog / conversations / conversation-detail / chat fetches via
  `lib/api.js` (all mocked at this stage).
- Mock SSE emitter in `lib/sse.js` for end-to-end streaming render
  before the backend exists.
- Control Plane starter (connectors, actions, automations, queue,
  roles) under `/control-plane`.
- My Day starter under `/my-day`.
- Slug-based action identity. Canonical role keys only.

### `f5beb0d` — Gate C hardening
- Workspace-mode toggle on the rail (`⊞` / `◧`, 560 px width variant).
- UI prefs persisted in `localStorage` via `lib/../assistant/uiPrefs.js`
  (collapsed / activeTab / workspaceMode).
- Cancellable SSE mock timers — rapid route changes never leak
  dispatches into an unmounted tree.
- Reducer normalization: `APPEND_LOCAL_USER_MESSAGE` /
  `REMOVE_LOCAL_USER_MESSAGE`, `STREAM_ABORT`, `SET_LAST_FAILED_MESSAGE`,
  retry path, pending flag.
- Unified `buildChatRequest()` — one request-builder for quick-action,
  freeform, and command mode.
- `ChatThread` error banner + retry; aborted/error message bubble tags.
- `ConnectorHealthPanel` client-derived connector → dependent-actions map.
- Reducer unit test suite (pure Node + assert), 24 tests.
- Playwright integration suite (`phase53_assistant_hardening.spec.js`),
  5 tests.

### `adcd606` — live-integration readiness
- Source-state registry `lib/integrationSource.js`: per-surface record
  of source (live / mock / unavailable / pending), `lastFetchAt`,
  `lastError`, `normalizations`, `probeIssues`, `attemptedLive`.
- Contract probes `lib/contractProbes.js`: developer-readable shape
  validators, never throw, guard canonical role keys + readiness
  vocabulary + SSE event vocabulary.
- `lib/api.js` rewritten: every read flows through `liveOrMock()` which
  runs the probe, records the source, and degrades to mock on failure.
- Runtime mock/live override via `shouldUseMocks()` (precedence:
  per-call option → `localStorage["rex.assistant.use_mocks"]` →
  compile-time `USE_ASSISTANT_MOCKS` constant).
- `normalizeMeEnvelope()` — wraps a bare-user `/api/me` response in
  `{ user }` and records the fix. Only normalization in the lane.
- `lib/sse.js` uses `shouldUseMocks()`, records `chatStream` source
  state across the stream lifecycle, normalizes CRLF frame boundaries,
  surfaces unknown-event warnings once per event.
- Pure SSE parser extracted to `lib/sseParser.js` (Node-testable).
- `controlPlane/IntegrationDiagnosticsPanel.jsx` — operator-facing
  table of every surface with source badge, last fetch, last error,
  probe issues, plus runtime override toggle buttons.
- Contract probe + SSE parser + adapter unit tests (41 Node tests).
- Live-mode Playwright suite (`phase54_live_integration.spec.js`),
  4 tests with contract-matching + drifted fixtures.

### This merge-readiness pass
- Removed one dead re-export (`__parseSseFrameForTests` in
  `lib/sse.js` — no consumer after parser extraction).
- Tightened stale module-header comment in `lib/sseParser.js`.
- Wrote this handoff doc.
- Added cutover-focused inline comments to `lib/api.js`,
  `lib/sse.js`, `lib/contractProbes.js`,
  `IntegrationDiagnosticsPanel.jsx`.
- Re-ran full test matrix and recorded results below.

---

## 2. Surface matrix

Every assistant-lane contract surface registered in `integrationSource`.
The diagnostics panel surfaces them all; this is the canonical list.

| Surface (registry key)      | HTTP                                          | Probe                           | Owner    |
|-----------------------------|-----------------------------------------------|---------------------------------|----------|
| `identity`                  | `GET /api/me`                                 | `probeMeShape`                  | Session 2|
| `permissions`               | `GET /api/me/permissions`                     | `probePermissionsShape`         | Session 2|
| `context`                   | `GET /api/context/current`                    | `probeCurrentContextShape`      | Session 2|
| `catalog`                   | `GET /api/assistant/catalog`                  | `probeCatalogShape`             | Session 1|
| `conversations`             | `GET /api/assistant/conversations`            | `probeConversationsListShape`   | Session 1|
| `conversationDetail`        | `GET /api/assistant/conversations/{id}`       | `probeConversationDetailShape`  | Session 1|
| `chatStream`                | `POST /api/assistant/chat` (SSE)              | `probeChatAckShape` + vocabulary| Session 1|
| `controlPlaneConnectors`    | `GET /api/control-plane/connectors`           | `probeConnectorsShape`          | Session 2|
| `controlPlaneAutomations`   | `GET /api/control-plane/automations`          | `probeAutomationsShape`         | Session 2|
| `controlPlaneQueue`         | `GET /api/control-plane/queue`                | noop (contract not frozen)      | Session 2|
| `myDayHome`                 | `GET /api/myday/home`                         | noop (contract not frozen)      | Session 2|

**Current live endpoint availability** (repo truth as of this commit):
zero. Only `/api/auth/me` exists in the backend, with a materially
incompatible shape — see §9.

---

## 3. Source states

Every surface is always in exactly one of these states:

| State         | Meaning                                                                                      | UI behavior                                           |
|---------------|----------------------------------------------------------------------------------------------|-------------------------------------------------------|
| `pending`     | Nothing has resolved yet for this surface (initial state on page load)                       | Diagnostics shows neutral badge; other panels keep their loading state |
| `live`        | A real backend call succeeded AND matched the frozen contract                                | Feature renders live data                             |
| `mock`        | The mock path was used — either master switch is on or per-call `mock: true`                 | Feature renders mock data; diagnostics badges `mock`  |
| `unavailable` | Live call was attempted and either failed (network/404/5xx) or drifted from contract         | Feature falls back to mock shape; diagnostics shows the error and any probe issues |

Falling from `live` to `unavailable` does not crash the UI. The adapter
always has a mock shape to return, so the rail keeps rendering, quick
actions stay visible, and the operator sees the degraded state in the
diagnostics panel rather than a white screen.

---

## 4. Mock / live mode override

Precedence (highest wins):

1. **Per-call option.** `fetchMe({ live: true })` forces live for one
   call; `fetchMe({ mock: true })` forces mock. Rarely needed in
   components; used by tests.
2. **localStorage runtime override.**
   `localStorage.setItem("rex.assistant.use_mocks", "true")` or
   `"false"`. Any other value (or the key missing) falls through. The
   diagnostics panel's toggle buttons write this key and reload.
3. **Compile-time default.** `USE_ASSISTANT_MOCKS` constant in
   `lib/api.js`. Currently `true`. **This is the primary master
   switch.** Flipping it to `false` makes live the default for every
   build — only do that after Sessions 1 and 2 land.

The override lives in `shouldUseMocks()` at the top of `lib/api.js` and
in no other place. `lib/sse.js` imports the same function so the stream
path and the fetch path can never disagree about mode.

---

## 5. Normalization behavior

Exactly one normalization exists in the lane:

- **`normalizeMeEnvelope(raw)` in `lib/api.js`.** If `/api/me` returns
  a bare user object (`{ id, email, ... }`) instead of the envelope
  (`{ user: { ... } }`), the adapter wraps it and records
  `normalizations: ["wrapped bare user response into { user }"]` on
  the `identity` surface so the diagnostics panel makes the fix
  visible. This matches the probe, which tolerates both shapes.

No other endpoint is normalized. Every other surface is **pass-through
or fail-the-probe**. This is deliberate — silent coercion of drifted
backend shapes into looking-healthy UI would hide the exact problems
cutover is trying to catch.

---

## 6. Contract probe philosophy

Probes are defined in `lib/contractProbes.js`. Each returns
`{ ok: true, issues: [] }` or `{ ok: false, issues: [human-readable, ...] }`.
They:

- check only the fields the frontend actually reads (minimum useful)
- enforce canonical role keys: `VP | PM | GENERAL_SUPER | LEAD_SUPER |
  ASSISTANT_SUPER | ACCOUNTANT`
- enforce readiness vocabulary: `live | alpha | adapter_pending |
  writeback_pending | blocked | disabled`
- enforce SSE event vocabulary: `conversation.created |
  message.started | message.delta | message.completed |
  followups.generated | action.suggestions | error`
- never throw, never mutate, never normalize (normalization is a
  separate concern)

When a probe fails, `liveOrMock()` in `lib/api.js`:

1. logs `[integration] <surface> live response failed contract probe:`
   followed by the issue list (developer-readable, one-shot per fetch)
2. sets the surface to `unavailable` with `probeIssues` populated
3. returns the mock payload so the UI stays standing

The diagnostics panel is the operator's view of those issues; the
console is the developer's view. They stay in sync because both read
the same `integrationSource` registry.

---

## 7. SSE vocabulary and parser expectations

The live path in `lib/sse.js` uses `fetch` + `ReadableStream.getReader`
to read POST `/api/assistant/chat` as SSE. Frame parsing is delegated to
the pure `lib/sseParser.js` module.

The parser handles the real-world SSE surface:

- `event: <name>\n` (defaults to `message` when absent)
- one or more `data: <line>\n` lines (joined with `\n` per spec)
- `: <comment>` keep-alive lines (returns `null`)
- unknown field lines (`id:`, `retry:`, custom) silently ignored
- empty / whitespace-only frames (return `null`)
- non-JSON data (passed through as raw string)
- trailing `\r` on lines (stripped — some servers don't normalize CRLF)

The buffer layer in `lib/sse.js`:

- splits at `\n\n` frame boundaries after normalizing `\r\n` → `\n` on
  every chunk (so CRLF servers tokenize identically to LF servers)
- carries partial chunks across reads (buffer + indexOf loop)
- marks `chatStream` as `live` on the **first successfully parsed
  frame** and `unavailable` on fetch error (never on abort)
- handles `AbortError` as a normal close (no error surface)

**Unknown event names** (e.g. a backend accidentally emits `tool.called`)
produce a one-shot `console.warn` per event name and are still forwarded
to the reducer, which default-drops them. This means vocabulary drift is
visible without breaking the thread render.

**Open Session 1 question**: the `action.suggestions` payload shape is
not contract-frozen in the Session 1 packet. The frontend accepts two
shapes defensively in the reducer:

1. `{ suggestions: [{ slug, reason }, ...] }`
2. bare `[slug, slug, ...]` array

and ignores unknown shapes via `safeActionSuggestions()` in
`assistant/useAssistantState.js`. When Session 1 freezes the shape,
either tighten the probe in `contractProbes.js` to enforce it, or
remove the defensive fallback — whichever the backend team prefers.

---

## 8. Degraded-mode behavior

When `USE_ASSISTANT_MOCKS=true` (default) — everything renders against
mocks. The diagnostics panel reports every surface as `mock`. The
assistant rail, Control Plane tabs, and My Day all work.

When `localStorage["rex.assistant.use_mocks"]="false"` is set and no
backend endpoints are live — `shouldUseMocks()` returns `false`, the
adapter attempts every live fetch, every one fails (404 / network /
parse error), each surface is marked `unavailable` with a readable
error, and `liveOrMock()` returns the mock shape. **Net effect: the UI
still works**, the rail still streams, Control Plane still shows its
mock data — but the diagnostics panel makes the degradation visible so
nobody confuses it for a healthy live build.

This is the state Session 3 is expected to be in from the moment
`feat/sidebar-shell` merges to main until Sessions 1 and 2 land their
backends. The cutover is then surgical (see §10).

---

## 9. Why `/api/auth/me` is intentionally NOT bridged

The existing backend has `GET /api/auth/me`, registered under the
`/api/auth` router, returning:

```
{ user_id, email, global_role, is_admin, is_active, last_login,
  person_id, first_name, last_name }
```

The Session 3 contract expects `GET /api/me` (no `/auth/` prefix)
returning:

```
{ user: { id, email, full_name, primary_role_key, role_keys,
  legacy_role_aliases, project_ids, feature_flags } }
```

These are the same concept but a different contract, a different path,
and a different envelope. Bridging them would require inventing
translations for `global_role` → `primary_role_key` (the canonical role
vocabulary does not map 1:1 to the legacy `global_role` values),
fabricating `role_keys`, synthesizing `project_ids` from a separate
permission query, and assuming `feature_flags` values. Every one of
those would be a frontend-only contract that the eventual Session 2
`/api/me` would then have to match.

The mission rule is explicit: **do not invent a new contract**.
The `identity` surface stays `unavailable` (or `mock`) until Session 2
ships the real `/api/me` at the real path with the real envelope. The
diagnostics panel reports this clearly.

---

## 10. Cutover checklist — when Sessions 1 and 2 land

Do these in order. Stop and investigate if any step reports drift the
diagnostics panel flags as `unavailable`.

### Pre-cutover (Session 1 or 2 is ready to merge)

1. Rebase or merge the session's backend branch into `main` as usual.
2. Deploy to preview. Confirm the endpoint list responds:
   - `GET /api/me`
   - `GET /api/me/permissions`
   - `GET /api/context/current`
   - `GET /api/assistant/catalog`
   - `GET /api/assistant/conversations`
   - `GET /api/assistant/conversations/{id}` (pick a real id)
   - `POST /api/assistant/chat` (SSE — verify `Content-Type:
     text/event-stream` and documented events)
   - `GET /api/control-plane/connectors`
   - `GET /api/control-plane/automations`

### Per-surface cutover (preferred — surgical, low-risk)

1. Open the deployed preview. Navigate to `/#/control-plane` →
   `Integration` tab. Confirm every surface currently shows `mock` (or
   `unavailable` if the runtime override is already set to live).
2. In the browser devtools:
   `localStorage.setItem("rex.assistant.use_mocks", "false")` and
   reload.
3. Watch the Integration tab. Each surface whose endpoint is now live
   should flip to `live`. Each surface whose endpoint is still missing
   flips to `unavailable` with a readable error.
4. **Expected drift surfaces early at this stage.** Read the
   `probeIssues` column. If a backend field is missing or uses a
   non-canonical value, **fix it in the backend**, not in the probe.
   The probes are the frozen contract.
5. Exercise the key user flows against the preview with the override
   on: load `/my-day`, open the assistant, launch a quick action,
   watch a stream render. Compare against the mock path (toggle off,
   reload, re-run).
6. Once every surface owned by the shipping session reports `live`,
   stop. Leave the override on for the remainder of preview testing.

### Global cutover (when both Sessions 1 and 2 have shipped and stabilized)

1. Leave the runtime override enabled in the deployed preview for one
   full working day. Watch for `unavailable` flickers under real load.
   Fix root causes in the backend.
2. In `frontend/src/lib/api.js`, flip:
   ```js
   export const USE_ASSISTANT_MOCKS = false;
   ```
3. Remove the runtime override from test fixtures that no longer need
   it (optional — the override still works either way).
4. Ship. The compile-time default is now live; the override remains
   available for developers who want to run the frontend against mocks
   locally while they work on contract shape drift.

### Per-surface force-live (middle ground — when some endpoints are
live but others aren't, and you do not want a global flip)

You can pin a single call to live in code by passing `{ live: true }`:

```js
const permissions = await fetchPermissions({ live: true });
```

This overrides `shouldUseMocks()` for that call only. Use this when
one surface has shipped and you want to exercise it in production
builds without flipping the master switch. Keep usage tight — the goal
is the master-switch flip, not a permanent sprinkling of per-call
overrides.

---

## 11. Rollback checklist — if cutover misbehaves

If live cutover breaks a surface in production or a preview:

### Immediate — operator-level (no redeploy)

1. In the affected browser, open devtools and run:
   `localStorage.setItem("rex.assistant.use_mocks", "true")` then
   reload.
2. Or, if the diagnostics panel is reachable, click **Force mock**
   (Control Plane → Integration tab).
3. The frontend re-resolves every surface in mock mode immediately.
4. This is per-browser; it does not change the deployed build.

### Developer-level (single-build rollback)

1. In `lib/api.js`, set `USE_ASSISTANT_MOCKS = true`.
2. Commit and deploy. The whole app returns to Gate C demo behavior
   instantly. Nothing else changes.
3. No contract was changed; no fixture was rewritten; the backend
   endpoints themselves are untouched. Flip the flag back when the
   drift is fixed upstream.

### Surgical rollback — one surface at a time

1. Identify the problem surface in the diagnostics panel.
2. In `lib/api.js`, pin the specific call to mock with `{ mock: true }`:
   ```js
   const catalog = await fetchAssistantCatalog({ mock: true });
   ```
   (or use a localStorage flag if you prefer runtime control)
3. Leave every other surface live.
4. Re-deploy. The one bad surface runs on mocks; everything else keeps
   benefitting from live data.

---

## 12. Blockers remaining before full cutover

### Owned by Session 1 (AI spine)
- `GET /api/assistant/catalog` — must match `probeCatalogShape`
  contract: `{ version, categories, actions: [{ slug, label, category,
  readiness_state, role_visibility, ... }] }`, canonical roles and
  readiness vocabulary enforced.
- `GET /api/assistant/conversations` — `{ items: [{ id, title?, ... }] }`.
- `GET /api/assistant/conversations/{id}` — `{ conversation, messages }`.
- `POST /api/assistant/chat` — SSE with exactly the seven documented
  events; `accepted: true` in the ack; `Content-Type:
  text/event-stream`.
- Freeze the `action.suggestions` payload shape (see §7).

### Owned by Session 2 (connectors + canonical identity)
- `GET /api/me` at `/me` (NOT `/auth/me`), wrapped `{ user: {...} }`,
  with `full_name`, `primary_role_key`, `role_keys`,
  `legacy_role_aliases`, `project_ids`, `feature_flags`.
- `GET /api/me/permissions` — `{ permissions: [string, ...] }`.
- `GET /api/context/current` — `{ project, route, page_context,
  assistant_defaults }`.
- `GET /api/control-plane/connectors` — `{ items: [{ key, label,
  status, ... }] }`.
- `GET /api/control-plane/automations` — `{ items: [{ slug,
  readiness_state, ... }] }`.

### Not blocking but nice-to-have
- `GET /api/control-plane/queue` — placeholder in the frontend until
  queue semantics are frozen.
- `GET /api/myday/home` — My Day surface has no hard dependency on
  this endpoint; it synthesizes its own content from the catalog and
  reducer state.

### Session 3 follow-up PR after Sessions 1/2 merge
- **None required.** Session 3 is designed so the cutover is a single
  flag flip. The only follow-up that may make sense after both
  sessions ship and stabilize is a cleanup PR that:
  1. Flips `USE_ASSISTANT_MOCKS` to `false`.
  2. Deletes the mock fixtures that are no longer referenced
     (`mockCatalog.js`, `mockConversations.js`, `mockIdentity.js`,
     `mockAutomations.js`) if the team decides to drop them entirely.
     We recommend keeping them for local-dev offline mode and keeping
     the mock path in `liveOrMock()` — the runtime override is a
     feature, not a debt.
  3. Tightens any probe that was provisionally noop (`queue`,
     `myDayHome`) once backend semantics are frozen.
  4. Freezes `action.suggestions` payload shape and removes the
     defensive fallback in `safeActionSuggestions()`.

---

## 13. Test + verification matrix

All verified green in the merge-readiness commit:

| Suite                                              | Count | Command                                                      |
|----------------------------------------------------|-------|--------------------------------------------------------------|
| Reducer unit tests                                 | 24    | `node src/assistant/__tests__/useAssistantState.test.js`     |
| Contract probe unit tests                          | 25    | `node src/lib/__tests__/contractProbes.test.js`              |
| SSE parser unit tests                              | 10    | `node src/lib/__tests__/sseParser.test.js`                   |
| Adapter / integrationSource unit tests             | 6     | `node src/lib/__tests__/apiAdapter.test.js`                  |
| **Pure Node total**                                | **65**|                                                              |
| Legacy Playwright smoke + phase 46-50              | 14    | `npx playwright test e2e/smoke.spec.js e2e/phase46_50.spec.js` |
| Phase 53 — assistant sidebar hardening             | 5     | `npx playwright test e2e/phase53_assistant_hardening.spec.js` |
| Phase 54 — live-integration adapter                | 4     | `npx playwright test e2e/phase54_live_integration.spec.js`  |
| **Playwright total**                               | **23**| `npx playwright test`                                        |
| Production build                                   | —     | `npm run build` (342 modules, ~3 s, ~712 KB)                 |

Manual verification pass (both required for merge):

- **Default mock pass**: boot the dev server, navigate to `/`, `/my-day`,
  `/control-plane`. Assistant rail mounts, quick actions render, launch
  → stream → final response, Integration tab shows all surfaces `mock`.
- **Degraded live-override pass**: in devtools,
  `localStorage.setItem("rex.assistant.use_mocks", "false")`, reload.
  Every surface in Integration shows `unavailable` with a readable
  error. Assistant rail still renders against mock-fallback data.
  Quick actions still launch (backed by mock catalog fallback). No
  crashes, no white screens.

---

## 14. Quick index

| Topic                           | File                                                          |
|---------------------------------|---------------------------------------------------------------|
| Adapter layer                   | `frontend/src/lib/api.js`                                     |
| Mode switch                     | `shouldUseMocks()` in `frontend/src/lib/api.js`               |
| Source-state registry           | `frontend/src/lib/integrationSource.js`                       |
| Contract probes                 | `frontend/src/lib/contractProbes.js`                          |
| Live SSE path + buffer          | `frontend/src/lib/sse.js`                                     |
| Pure SSE parser                 | `frontend/src/lib/sseParser.js`                               |
| Assistant reducer               | `frontend/src/assistant/useAssistantState.js`                 |
| Assistant client hook           | `frontend/src/assistant/useAssistantClient.js`                |
| Persistent sidebar              | `frontend/src/assistant/AssistantSidebar.jsx`                 |
| Diagnostics panel               | `frontend/src/controlPlane/IntegrationDiagnosticsPanel.jsx`   |
| Control Plane shell             | `frontend/src/controlPlane/ControlPlaneHome.jsx`              |
| Mock fixtures                   | `frontend/src/lib/mock*.js`                                   |
| Cutover tests                   | `frontend/e2e/phase54_live_integration.spec.js`               |

---

End of handoff.
