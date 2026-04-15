// Contract-driven API client for the assistant + control plane lanes.
//
// This module intentionally duplicates the minimum useful surface from the
// legacy `src/api.js` so the assistant lane can evolve its own adapters
// (mocked → live swap) without touching the 32-page product shell or its
// write flows. The existing `src/api.js` continues to serve the legacy
// pages; this file is the new entry point for assistant / catalog /
// control-plane / context endpoints.
//
// All methods return promises resolving to the shape defined in the
// Session 3 packet API contracts. When `REX_ASSISTANT_USE_MOCKS` is true
// (default for now), the methods hand back mock fixtures instead of
// hitting the network — so the frontend lane can move while Sessions 1/2
// are still in flight.

import { apiUrl, getToken } from "../api";
import { mockCatalog } from "./mockCatalog";
import { mockConversations, mockConversationMessages } from "./mockConversations";
import { mockMe, mockPermissions } from "./mockIdentity";
import { mockAutomations } from "./mockAutomations";

// Flip to false once Session 1 + Session 2 backend lanes land the real
// endpoints. Individual calls can be force-routed to live by passing
// `{ live: true }` in their options, which makes the swap surgical.
export const USE_ASSISTANT_MOCKS = true;

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

// ── Identity / permissions / context ──────────────────────────────────────

export async function fetchMe(opts = {}) {
  if (USE_ASSISTANT_MOCKS && !opts.live) return { user: mockMe };
  return jsonFetch("/me");
}

export async function fetchPermissions(opts = {}) {
  if (USE_ASSISTANT_MOCKS && !opts.live) return { permissions: mockPermissions };
  return jsonFetch("/me/permissions");
}

export async function fetchCurrentContext(opts = {}) {
  if (USE_ASSISTANT_MOCKS && !opts.live) {
    // The mock is mostly a stub — real context is synthesized in
    // useCurrentContext from the router + project selection. This
    // endpoint shape exists for the eventual backend swap.
    return {
      project: null,
      route: { name: "shell", path: "/" },
      page_context: { surface: "shell", entity_type: null, entity_id: null, filters: {} },
      assistant_defaults: { suggested_action_slugs: ["morning_briefing", "budget_variance"] },
    };
  }
  return jsonFetch("/context/current");
}

// ── Assistant catalog + conversations + chat ──────────────────────────────

export async function fetchAssistantCatalog(opts = {}) {
  if (USE_ASSISTANT_MOCKS && !opts.live) return mockCatalog;
  return jsonFetch("/assistant/catalog");
}

export async function fetchAssistantConversations(opts = {}) {
  if (USE_ASSISTANT_MOCKS && !opts.live) return { items: mockConversations };
  return jsonFetch("/assistant/conversations");
}

export async function fetchAssistantConversation(id, opts = {}) {
  if (USE_ASSISTANT_MOCKS && !opts.live) {
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
  }
  return jsonFetch(`/assistant/conversations/${id}`);
}

export async function postAssistantChat(payload, opts = {}) {
  // Real POST — mocked here. Returns the same envelope the SSE stream
  // helper (lib/sse.js) will emit so callers can swap without rewriting.
  if (USE_ASSISTANT_MOCKS && !opts.live) {
    return {
      conversation_id: payload.conversation_id || "mock-conv-" + Date.now(),
      accepted: true,
      streaming: !!payload.stream,
    };
  }
  return jsonFetch("/assistant/chat", { method: "POST", body: payload });
}

// ── Control plane ─────────────────────────────────────────────────────────

export async function fetchControlPlaneConnectors(opts = {}) {
  if (USE_ASSISTANT_MOCKS && !opts.live) {
    return {
      items: [
        { key: "procore", label: "Procore", status: "adapter_pending", last_sync_at: null, health: "unknown" },
        { key: "exxir", label: "Exxir", status: "adapter_pending", last_sync_at: null, health: "unknown" },
      ],
    };
  }
  return jsonFetch("/control-plane/connectors");
}

export async function fetchControlPlaneAutomations(opts = {}) {
  if (USE_ASSISTANT_MOCKS && !opts.live) return { items: mockAutomations };
  return jsonFetch("/control-plane/automations");
}

export async function fetchControlPlaneQueue(opts = {}) {
  if (USE_ASSISTANT_MOCKS && !opts.live) {
    return { items: [], placeholder: true };
  }
  return jsonFetch("/control-plane/queue");
}

// ── My Day ────────────────────────────────────────────────────────────────

export async function fetchMyDay(opts = {}) {
  if (USE_ASSISTANT_MOCKS && !opts.live) {
    return {
      greeting: "Good morning",
      alert_count: 3,
      pending_tasks: 5,
      upcoming_meetings: 2,
      suggested_action_slugs: ["morning_briefing", "my_day_briefing"],
      placeholder: true,
    };
  }
  return jsonFetch("/myday/home");
}
