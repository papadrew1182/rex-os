// Contract-driven API client for the assistant + control plane lanes.
//
// Every read goes through `liveOrMock()` — a tiny adapter that:
//   1. decides whether to attempt the live path (global flag + runtime override)
//   2. runs the probe on the live response and either accepts it or
//      records probeIssues and falls back to the mock path
//   3. records the current source state in integrationSource so the
//      diagnostics panel has a live view of what the sidebar is
//      actually seeing
//
// Design rules:
//   - keep normalization surgical. Prefer pass-through. Record every
//     normalization performed in the returned `normalizations` list so
//     operators can see exactly what we did.
//   - do NOT silently coerce drift into looking healthy. If the probe
//     fails, the surface is reported "unavailable" (when we attempted
//     live) or "mock" (when we never attempted live).
//   - callers of the api keep returning the mock shape when live is
//     unavailable, so the UI degrades gracefully without crashing.
//   - `shouldUseMocks()` reads the constant AND a localStorage override
//     so tests can flip to live mode at runtime without editing files.

import { apiUrl, getToken } from "../api";
import { mockCatalog } from "./mockCatalog";
import { mockConversations, mockConversationMessages } from "./mockConversations";
import { mockMe, mockPermissions } from "./mockIdentity";
import { mockAutomations } from "./mockAutomations";
import {
  markLive,
  markMock,
  markUnavailable,
  markPending,
} from "./integrationSource";
import {
  probeMeShape,
  probePermissionsShape,
  probeCurrentContextShape,
  probeCatalogShape,
  probeConversationsListShape,
  probeConversationDetailShape,
  probeChatAckShape,
  probeConnectorsShape,
  probeAutomationsShape,
} from "./contractProbes";

// ── Master switch ─────────────────────────────────────────────────────
//
// Flip to false once Session 1 + Session 2 backend lanes land the real
// endpoints. Individual calls can be force-routed to live by passing
// `{ live: true }` in their options, which makes the swap surgical.
export const USE_ASSISTANT_MOCKS = true;

// Runtime override lets tests / operators switch modes without editing
// code. Precedence: option > localStorage > compile-time constant.
//
//   localStorage.setItem("rex.assistant.use_mocks", "false")  // go live
//   localStorage.setItem("rex.assistant.use_mocks", "true")   // force mocks
//
// Any other value (or missing key) falls through to USE_ASSISTANT_MOCKS.
export function shouldUseMocks(opts = {}) {
  if (opts.live === true) return false;
  if (opts.mock === true) return true;
  try {
    if (typeof localStorage !== "undefined") {
      const v = localStorage.getItem("rex.assistant.use_mocks");
      if (v === "true") return true;
      if (v === "false") return false;
    }
  } catch { /* no-op */ }
  return USE_ASSISTANT_MOCKS;
}

async function jsonFetch(path, opts = {}) {
  const token = getToken();
  const headers = { ...(opts.headers || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (opts.body && !(opts.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  const res = await fetch(apiUrl(path), { ...opts, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("json") ? res.json() : res;
}

// Core adapter. Every fetch goes through this so source state + probe
// handling is centralized. Returns the probed-and-normalized payload
// the caller expects. On unavailable live, returns mockFn().
//
//   surface       — integrationSource key
//   probe         — (raw) => { ok, issues }
//   livePath      — async () => raw response body (throws on network err)
//   normalizePath — (raw) => { result, normalizations: [] }  (optional)
//   mockPath      — () => the mock payload shaped as the caller expects
//   opts          — { live, mock } overrides (passed from caller)
async function liveOrMock({
  surface, probe, livePath, normalizePath, mockPath, opts = {},
}) {
  markPending(surface);
  if (shouldUseMocks(opts)) {
    markMock(surface);
    return mockPath();
  }
  try {
    const raw = await livePath();
    const probeResult = probe(raw);
    if (!probeResult.ok) {
      markUnavailable(surface, {
        error: `contract probe failed: ${probeResult.issues.join("; ")}`,
        probeIssues: probeResult.issues,
      });
      // eslint-disable-next-line no-console
      console.warn(
        `[integration] ${surface} live response failed contract probe:`,
        probeResult.issues,
      );
      return mockPath();
    }
    const { result, normalizations = [] } = normalizePath
      ? normalizePath(raw)
      : { result: raw, normalizations: [] };
    markLive(surface, { normalizations });
    return result;
  } catch (err) {
    markUnavailable(surface, { error: err });
    // eslint-disable-next-line no-console
    console.warn(`[integration] ${surface} live fetch failed:`, err?.message || err);
    return mockPath();
  }
}

// Convenience: unwrap the Session 3 { user: {...} } envelope on /api/me.
// Returns { result, normalizations } so liveOrMock can log the fix.
function normalizeMeEnvelope(raw) {
  const normalizations = [];
  if (raw && raw.user) {
    return { result: { user: raw.user }, normalizations };
  }
  // Bare user response — wrap it and record the fix.
  normalizations.push("wrapped bare user response into { user }");
  return { result: { user: raw }, normalizations };
}

// ── Identity / permissions / context ──────────────────────────────────

export async function fetchMe(opts = {}) {
  return liveOrMock({
    surface: "identity",
    probe: probeMeShape,
    livePath: () => jsonFetch("/me"),
    normalizePath: normalizeMeEnvelope,
    mockPath: () => ({ user: mockMe }),
    opts,
  });
}

export async function fetchPermissions(opts = {}) {
  return liveOrMock({
    surface: "permissions",
    probe: probePermissionsShape,
    livePath: () => jsonFetch("/me/permissions"),
    mockPath: () => ({ permissions: mockPermissions }),
    opts,
  });
}

export async function fetchCurrentContext(opts = {}) {
  return liveOrMock({
    surface: "context",
    probe: probeCurrentContextShape,
    livePath: () => jsonFetch("/context/current"),
    mockPath: () => ({
      // The mock is mostly a stub — real context is synthesized in
      // useCurrentContext from the router + project selection. This
      // endpoint shape exists for the eventual backend swap.
      project: null,
      route: { name: "shell", path: "/" },
      page_context: { surface: "shell", entity_type: null, entity_id: null, filters: {} },
      assistant_defaults: { suggested_action_slugs: ["morning_briefing", "budget_variance"] },
    }),
    opts,
  });
}

// ── Assistant catalog + conversations + chat ──────────────────────────

export async function fetchAssistantCatalog(opts = {}) {
  return liveOrMock({
    surface: "catalog",
    probe: probeCatalogShape,
    livePath: () => jsonFetch("/assistant/catalog"),
    mockPath: () => mockCatalog,
    opts,
  });
}

export async function fetchAssistantConversations(opts = {}) {
  return liveOrMock({
    surface: "conversations",
    probe: probeConversationsListShape,
    livePath: () => jsonFetch("/assistant/conversations"),
    mockPath: () => ({ items: mockConversations }),
    opts,
  });
}

export async function fetchAssistantConversation(id, opts = {}) {
  return liveOrMock({
    surface: "conversationDetail",
    probe: probeConversationDetailShape,
    livePath: () => jsonFetch(`/assistant/conversations/${id}`),
    mockPath: () => {
      const conversation = mockConversations.find((c) => c.id === id);
      if (!conversation) throw new Error("Conversation not found");
      return {
        conversation: {
          id: conversation.id,
          title: conversation.title,
          project_id: conversation.project_id,
          active_action_slug: conversation.active_action_slug,
          page_context: { route: "/" },
        },
        messages: mockConversationMessages[id] || [],
      };
    },
    opts,
  });
}

export async function postAssistantChat(payload, opts = {}) {
  // The chat POST is an ack → the actual message stream flows through
  // lib/sse.js. This function's job is just to confirm the server
  // accepted the request and hand back the conversation_id (when
  // assigned synchronously) so the caller can pass it to openAssistantStream.
  if (shouldUseMocks(opts)) {
    markMock("chatStream");
    return {
      conversation_id: payload.conversation_id || "mock-conv-" + Date.now(),
      accepted: true,
      streaming: !!payload.stream,
    };
  }
  markPending("chatStream");
  try {
    const raw = await jsonFetch("/assistant/chat", { method: "POST", body: payload });
    const probeResult = probeChatAckShape(raw);
    if (!probeResult.ok) {
      markUnavailable("chatStream", {
        error: `chat ack failed contract probe: ${probeResult.issues.join("; ")}`,
        probeIssues: probeResult.issues,
      });
      throw new Error(`chat ack shape drift: ${probeResult.issues.join("; ")}`);
    }
    markLive("chatStream");
    return raw;
  } catch (err) {
    markUnavailable("chatStream", { error: err });
    throw err;
  }
}

// ── Control plane ─────────────────────────────────────────────────────

export async function fetchControlPlaneConnectors(opts = {}) {
  return liveOrMock({
    surface: "controlPlaneConnectors",
    probe: probeConnectorsShape,
    livePath: () => jsonFetch("/control-plane/connectors"),
    mockPath: () => ({
      items: [
        { key: "procore", label: "Procore", status: "adapter_pending", last_sync_at: null, health: "unknown" },
        { key: "exxir", label: "Exxir", status: "adapter_pending", last_sync_at: null, health: "unknown" },
      ],
    }),
    opts,
  });
}

export async function fetchControlPlaneAutomations(opts = {}) {
  return liveOrMock({
    surface: "controlPlaneAutomations",
    probe: probeAutomationsShape,
    livePath: () => jsonFetch("/control-plane/automations"),
    mockPath: () => ({ items: mockAutomations }),
    opts,
  });
}

export async function fetchControlPlaneQueue(opts = {}) {
  // Queue endpoint isn't contract-frozen yet — the probe is a noop.
  return liveOrMock({
    surface: "controlPlaneQueue",
    probe: () => ({ ok: true, issues: [] }),
    livePath: () => jsonFetch("/control-plane/queue"),
    mockPath: () => ({ items: [], placeholder: true }),
    opts,
  });
}

// ── My Day ────────────────────────────────────────────────────────────

export async function fetchMyDay(opts = {}) {
  return liveOrMock({
    surface: "myDayHome",
    probe: () => ({ ok: true, issues: [] }),
    livePath: () => jsonFetch("/myday/home"),
    mockPath: () => ({
      greeting: "Good morning",
      alert_count: 3,
      pending_tasks: 5,
      upcoming_meetings: 2,
      suggested_action_slugs: ["morning_briefing", "my_day_briefing"],
      placeholder: true,
    }),
    opts,
  });
}
