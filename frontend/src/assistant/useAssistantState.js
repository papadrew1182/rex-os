// Assistant reducer — the single source of truth for assistant UI state.
//
// Buckets managed here:
//   catalog            — { loading, error, data }
//   conversations      — { loading, error, items }
//   activeConversation — { id, conversation, messages, streaming,
//                           followups, actionSuggestions, lastError,
//                           lastFailedMessage }
//   ui                 — { collapsed, activeTab, workspaceMode,
//                           activeActionSlug, pending }
//
// Reducer is pure: no context reads, no fetches, no timers. The
// fetches live in `app/AppContext.jsx` which dispatches actions into
// this reducer. The pure shape means this file is test-friendly from
// Node + assert alone (see __tests__/useAssistantState.test.js).

import { loadUiPrefs } from "./uiPrefs.js";

export const ASSISTANT_ACTIONS = {
  // catalog
  CATALOG_LOADING: "catalog/loading",
  CATALOG_LOADED: "catalog/loaded",
  CATALOG_ERROR: "catalog/error",

  // conversations
  CONVERSATIONS_LOADING: "conversations/loading",
  CONVERSATIONS_LOADED: "conversations/loaded",
  CONVERSATIONS_ERROR: "conversations/error",

  // active conversation
  ACTIVE_CONVERSATION_LOADING: "activeConversation/loading",
  ACTIVE_CONVERSATION_LOADED: "activeConversation/loaded",
  ACTIVE_CONVERSATION_ERROR: "activeConversation/error",
  ACTIVE_CONVERSATION_CLEAR: "activeConversation/clear",

  // optimistic local append + last-send bookkeeping for retry/regenerate
  APPEND_LOCAL_USER_MESSAGE: "activeConversation/appendUserMessage",
  REMOVE_LOCAL_USER_MESSAGE: "activeConversation/removeUserMessage",
  SET_LAST_FAILED_MESSAGE: "activeConversation/setLastFailedMessage",
  CLEAR_LAST_FAILED_MESSAGE: "activeConversation/clearLastFailedMessage",

  // send lifecycle (duplicate-send guard + cancel-in-flight)
  SEND_PENDING: "send/pending",
  SEND_SETTLED: "send/settled",

  // SSE streaming updates
  STREAM_STARTED: "stream/started",
  STREAM_DELTA: "stream/delta",
  STREAM_COMPLETED: "stream/completed",
  STREAM_FOLLOWUPS: "stream/followups",
  STREAM_ACTION_SUGGESTIONS: "stream/actionSuggestions",
  STREAM_ERROR: "stream/error",
  STREAM_CLOSED: "stream/closed",
  STREAM_ABORT: "stream/abort",

  // UI
  UI_TOGGLE_COLLAPSED: "ui/toggleCollapsed",
  UI_SET_COLLAPSED: "ui/setCollapsed",
  UI_SET_TAB: "ui/setTab",
  UI_TOGGLE_WORKSPACE_MODE: "ui/toggleWorkspaceMode",
  UI_SET_WORKSPACE_MODE: "ui/setWorkspaceMode",
  UI_SET_ACTIVE_ACTION: "ui/setActiveAction",
};

export const ASSISTANT_TABS = {
  CONVERSATIONS: "conversations",
  THREAD: "thread",
  QUICK_ACTIONS: "quick_actions",
  COMMAND: "command",
};

const TAB_ORDER = [
  ASSISTANT_TABS.QUICK_ACTIONS,
  ASSISTANT_TABS.THREAD,
  ASSISTANT_TABS.CONVERSATIONS,
  ASSISTANT_TABS.COMMAND,
];

// Simple deterministic id generator (no Date.now collisions in reducer).
let _idCounter = 0;
function nextLocalId(prefix) {
  _idCounter += 1;
  return `${prefix}-${_idCounter}`;
}

export const initialAssistantState = {
  catalog: {
    loading: false,
    error: null,
    data: null,
  },
  conversations: {
    loading: false,
    error: null,
    items: [],
  },
  activeConversation: {
    loading: false,
    error: null,
    id: null,
    conversation: null,
    messages: [],
    streaming: false,
    followups: [],
    // action.suggestions SSE event result. Defensive rendering — the
    // shape is intentionally loose because Session 1 has not frozen
    // the payload yet.
    actionSuggestions: [],
    // Last send that failed — surfaces a retry affordance in ChatThread.
    lastFailedMessage: null,
  },
  ui: {
    collapsed: false,
    activeTab: ASSISTANT_TABS.QUICK_ACTIONS,
    workspaceMode: false,
    activeActionSlug: null,
    // Duplicate-send guard. When pending=true, ChatComposer +
    // QuickActionLauncher disable their submit buttons.
    pending: false,
  },
};

// Build initial state with persisted UI prefs applied. Called once at
// reducer init in AppContext so reloads restore collapsed/tab/workspaceMode.
export function buildInitialAssistantState() {
  const persisted = loadUiPrefs();
  return {
    ...initialAssistantState,
    ui: {
      ...initialAssistantState.ui,
      ...persisted,
    },
  };
}

// ── Helpers ──────────────────────────────────────────────────────────────

function findLastStreamingAssistantIndex(messages) {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].sender_type === "assistant" && messages[i].streaming) {
      return i;
    }
  }
  return -1;
}

function extractFollowups(messages) {
  if (!messages || messages.length === 0) return [];
  const last = messages[messages.length - 1];
  if (last.sender_type !== "assistant") return [];
  return last.structured_payload?.followups || [];
}

function safeActionSuggestions(payload) {
  // Session 1 has not frozen this payload shape. Accept either
  // { suggestions: [{ slug, reason }] } or a plain array of strings or
  // a plain array of {slug} objects. Anything else → empty.
  if (!payload) return [];
  if (Array.isArray(payload)) return payload.filter(Boolean);
  if (Array.isArray(payload.suggestions)) return payload.suggestions.filter(Boolean);
  return [];
}

// ── Reducer ──────────────────────────────────────────────────────────────

export function assistantReducer(state, action) {
  switch (action.type) {
    // ── catalog ───────────────────────────────────────────────────────
    case ASSISTANT_ACTIONS.CATALOG_LOADING:
      return { ...state, catalog: { ...state.catalog, loading: true, error: null } };
    case ASSISTANT_ACTIONS.CATALOG_LOADED:
      return { ...state, catalog: { loading: false, error: null, data: action.payload } };
    case ASSISTANT_ACTIONS.CATALOG_ERROR:
      return { ...state, catalog: { ...state.catalog, loading: false, error: action.payload } };

    // ── conversations ────────────────────────────────────────────────
    case ASSISTANT_ACTIONS.CONVERSATIONS_LOADING:
      return { ...state, conversations: { ...state.conversations, loading: true, error: null } };
    case ASSISTANT_ACTIONS.CONVERSATIONS_LOADED:
      return { ...state, conversations: { loading: false, error: null, items: action.payload } };
    case ASSISTANT_ACTIONS.CONVERSATIONS_ERROR:
      return { ...state, conversations: { ...state.conversations, loading: false, error: action.payload } };

    // ── active conversation ──────────────────────────────────────────
    case ASSISTANT_ACTIONS.ACTIVE_CONVERSATION_LOADING:
      return {
        ...state,
        activeConversation: {
          ...initialAssistantState.activeConversation,
          loading: true,
          id: action.payload,
        },
      };
    case ASSISTANT_ACTIONS.ACTIVE_CONVERSATION_LOADED:
      return {
        ...state,
        activeConversation: {
          loading: false,
          error: null,
          id: action.payload.conversation?.id || state.activeConversation.id,
          conversation: action.payload.conversation,
          messages: action.payload.messages || [],
          streaming: false,
          followups: extractFollowups(action.payload.messages),
          actionSuggestions: [],
          lastFailedMessage: null,
        },
      };
    case ASSISTANT_ACTIONS.ACTIVE_CONVERSATION_ERROR:
      return {
        ...state,
        activeConversation: { ...state.activeConversation, loading: false, error: action.payload },
      };
    case ASSISTANT_ACTIONS.ACTIVE_CONVERSATION_CLEAR:
      return {
        ...state,
        activeConversation: initialAssistantState.activeConversation,
        ui: { ...state.ui, activeActionSlug: null },
      };

    // ── optimistic local user message append ─────────────────────────
    case ASSISTANT_ACTIONS.APPEND_LOCAL_USER_MESSAGE: {
      const localId = action.payload.localId || nextLocalId("local");
      return {
        ...state,
        activeConversation: {
          ...state.activeConversation,
          messages: [
            ...state.activeConversation.messages,
            {
              id: localId,
              sender_type: "user",
              content: action.payload.content,
              created_at: action.payload.created_at || new Date().toISOString(),
              local: true,
            },
          ],
          followups: [],
          actionSuggestions: [],
          lastFailedMessage: null,
        },
      };
    }
    case ASSISTANT_ACTIONS.REMOVE_LOCAL_USER_MESSAGE: {
      const filtered = state.activeConversation.messages.filter(
        (m) => m.id !== action.payload.localId
      );
      return {
        ...state,
        activeConversation: { ...state.activeConversation, messages: filtered },
      };
    }
    case ASSISTANT_ACTIONS.SET_LAST_FAILED_MESSAGE:
      return {
        ...state,
        activeConversation: {
          ...state.activeConversation,
          lastFailedMessage: action.payload,
        },
      };
    case ASSISTANT_ACTIONS.CLEAR_LAST_FAILED_MESSAGE:
      return {
        ...state,
        activeConversation: { ...state.activeConversation, lastFailedMessage: null },
      };

    // ── send lifecycle ───────────────────────────────────────────────
    case ASSISTANT_ACTIONS.SEND_PENDING:
      return { ...state, ui: { ...state.ui, pending: true } };
    case ASSISTANT_ACTIONS.SEND_SETTLED:
      return { ...state, ui: { ...state.ui, pending: false } };

    // ── SSE stream updates ───────────────────────────────────────────
    case ASSISTANT_ACTIONS.STREAM_STARTED: {
      const tail = state.activeConversation.messages[state.activeConversation.messages.length - 1];
      if (tail && tail.sender_type === "assistant" && tail.streaming) {
        return { ...state, activeConversation: { ...state.activeConversation, streaming: true } };
      }
      const placeholder = {
        id: nextLocalId("stream"),
        sender_type: "assistant",
        content: "",
        streaming: true,
        created_at: new Date().toISOString(),
      };
      return {
        ...state,
        activeConversation: {
          ...state.activeConversation,
          streaming: true,
          messages: [...state.activeConversation.messages, placeholder],
          error: null,
        },
      };
    }
    case ASSISTANT_ACTIONS.STREAM_DELTA: {
      const idx = findLastStreamingAssistantIndex(state.activeConversation.messages);
      if (idx < 0) {
        const placeholder = {
          id: nextLocalId("stream"),
          sender_type: "assistant",
          content: action.payload.accumulated ?? (action.payload.delta || ""),
          streaming: true,
          created_at: new Date().toISOString(),
        };
        return {
          ...state,
          activeConversation: {
            ...state.activeConversation,
            streaming: true,
            messages: [...state.activeConversation.messages, placeholder],
          },
        };
      }
      const msgs = state.activeConversation.messages.slice();
      const prev = msgs[idx];
      msgs[idx] = {
        ...prev,
        content: action.payload.accumulated ?? (prev.content + (action.payload.delta || "")),
      };
      return {
        ...state,
        activeConversation: { ...state.activeConversation, messages: msgs },
      };
    }
    case ASSISTANT_ACTIONS.STREAM_COMPLETED: {
      const idx = findLastStreamingAssistantIndex(state.activeConversation.messages);
      if (idx < 0) {
        return {
          ...state,
          activeConversation: { ...state.activeConversation, streaming: false },
        };
      }
      const msgs = state.activeConversation.messages.slice();
      msgs[idx] = {
        ...msgs[idx],
        content: action.payload?.content ?? msgs[idx].content,
        streaming: false,
      };
      return {
        ...state,
        activeConversation: { ...state.activeConversation, messages: msgs, streaming: false },
      };
    }
    case ASSISTANT_ACTIONS.STREAM_FOLLOWUPS:
      return {
        ...state,
        activeConversation: {
          ...state.activeConversation,
          followups: action.payload?.followups || [],
        },
      };
    case ASSISTANT_ACTIONS.STREAM_ACTION_SUGGESTIONS:
      return {
        ...state,
        activeConversation: {
          ...state.activeConversation,
          actionSuggestions: safeActionSuggestions(action.payload),
        },
      };
    case ASSISTANT_ACTIONS.STREAM_ERROR: {
      const idx = findLastStreamingAssistantIndex(state.activeConversation.messages);
      const msgs = state.activeConversation.messages.slice();
      if (idx >= 0) {
        msgs[idx] = { ...msgs[idx], streaming: false, error: true };
      }
      return {
        ...state,
        activeConversation: {
          ...state.activeConversation,
          messages: msgs,
          streaming: false,
          error: typeof action.payload === "string" ? action.payload : action.payload?.message || "Stream error",
        },
      };
    }
    case ASSISTANT_ACTIONS.STREAM_CLOSED:
      return {
        ...state,
        activeConversation: { ...state.activeConversation, streaming: false },
      };
    case ASSISTANT_ACTIONS.STREAM_ABORT: {
      const idx = findLastStreamingAssistantIndex(state.activeConversation.messages);
      const msgs = state.activeConversation.messages.slice();
      if (idx >= 0) {
        msgs[idx] = { ...msgs[idx], streaming: false, aborted: true };
      }
      return {
        ...state,
        activeConversation: { ...state.activeConversation, messages: msgs, streaming: false },
      };
    }

    // ── UI ────────────────────────────────────────────────────────────
    case ASSISTANT_ACTIONS.UI_TOGGLE_COLLAPSED:
      return { ...state, ui: { ...state.ui, collapsed: !state.ui.collapsed } };
    case ASSISTANT_ACTIONS.UI_SET_COLLAPSED:
      return { ...state, ui: { ...state.ui, collapsed: !!action.payload } };
    case ASSISTANT_ACTIONS.UI_SET_TAB:
      if (action.payload === "next" || action.payload === "prev") {
        const idx = TAB_ORDER.indexOf(state.ui.activeTab);
        const base = idx < 0 ? 0 : idx;
        const delta = action.payload === "next" ? 1 : -1;
        const nextIdx = (base + delta + TAB_ORDER.length) % TAB_ORDER.length;
        return { ...state, ui: { ...state.ui, activeTab: TAB_ORDER[nextIdx] } };
      }
      return { ...state, ui: { ...state.ui, activeTab: action.payload } };
    case ASSISTANT_ACTIONS.UI_TOGGLE_WORKSPACE_MODE: {
      const nextMode = !state.ui.workspaceMode;
      return {
        ...state,
        ui: {
          ...state.ui,
          workspaceMode: nextMode,
          collapsed: nextMode ? false : state.ui.collapsed,
        },
      };
    }
    case ASSISTANT_ACTIONS.UI_SET_WORKSPACE_MODE: {
      const nextMode = !!action.payload;
      return {
        ...state,
        ui: {
          ...state.ui,
          workspaceMode: nextMode,
          collapsed: nextMode ? false : state.ui.collapsed,
        },
      };
    }
    case ASSISTANT_ACTIONS.UI_SET_ACTIVE_ACTION:
      return { ...state, ui: { ...state.ui, activeActionSlug: action.payload } };

    default:
      return state;
  }
}

// Test-only helper — reset the local id counter so snapshots stay stable.
export function __resetIdCounterForTests() {
  _idCounter = 0;
}
