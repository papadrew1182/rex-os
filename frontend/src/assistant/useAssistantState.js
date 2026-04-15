// Assistant reducer — the single source of truth for assistant UI state.
//
// Buckets managed here:
//   catalog          — { loading, error, data }
//   conversations    — { loading, error, items }
//   activeConversation — { loading, error, id, conversation, messages, streaming, followups }
//   ui               — { collapsed, activeTab, workspaceMode }
//
// Reducer-only: no context reads, no fetches. The fetches live in
// `app/AppContext.jsx` which dispatches actions into this reducer.

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

  // local optimistic message append (before SSE completes)
  APPEND_LOCAL_USER_MESSAGE: "activeConversation/appendUserMessage",

  // SSE streaming updates
  STREAM_STARTED: "stream/started",
  STREAM_DELTA: "stream/delta",
  STREAM_COMPLETED: "stream/completed",
  STREAM_FOLLOWUPS: "stream/followups",
  STREAM_ERROR: "stream/error",
  STREAM_CLOSED: "stream/closed",

  // UI
  UI_TOGGLE_COLLAPSED: "ui/toggleCollapsed",
  UI_SET_COLLAPSED: "ui/setCollapsed",
  UI_SET_TAB: "ui/setTab",
  UI_SET_WORKSPACE_MODE: "ui/setWorkspaceMode",
  UI_SET_ACTIVE_ACTION: "ui/setActiveAction",
};

export const ASSISTANT_TABS = {
  CONVERSATIONS: "conversations",
  THREAD: "thread",
  QUICK_ACTIONS: "quick_actions",
  COMMAND: "command",
};

export const initialAssistantState = {
  catalog: {
    loading: false,
    error: null,
    data: null, // { version, categories, actions }
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
  },
  ui: {
    collapsed: false,
    activeTab: ASSISTANT_TABS.QUICK_ACTIONS,
    workspaceMode: false,
    activeActionSlug: null,
  },
};

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
        },
      };
    case ASSISTANT_ACTIONS.ACTIVE_CONVERSATION_ERROR:
      return {
        ...state,
        activeConversation: { ...state.activeConversation, loading: false, error: action.payload },
      };
    case ASSISTANT_ACTIONS.ACTIVE_CONVERSATION_CLEAR:
      return { ...state, activeConversation: initialAssistantState.activeConversation };

    // ── optimistic local user message append ─────────────────────────
    case ASSISTANT_ACTIONS.APPEND_LOCAL_USER_MESSAGE:
      return {
        ...state,
        activeConversation: {
          ...state.activeConversation,
          messages: [
            ...state.activeConversation.messages,
            {
              id: `local-${Date.now()}`,
              sender_type: "user",
              content: action.payload.content,
              created_at: new Date().toISOString(),
            },
          ],
          followups: [],
        },
      };

    // ── SSE stream updates ───────────────────────────────────────────
    case ASSISTANT_ACTIONS.STREAM_STARTED: {
      // Append a placeholder assistant message that will be filled via deltas
      const placeholder = {
        id: `stream-${Date.now()}`,
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
        },
      };
    }
    case ASSISTANT_ACTIONS.STREAM_DELTA: {
      const msgs = state.activeConversation.messages.slice();
      // Find the last streaming assistant message and append delta
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].sender_type === "assistant" && msgs[i].streaming) {
          msgs[i] = { ...msgs[i], content: action.payload.accumulated ?? (msgs[i].content + (action.payload.delta || "")) };
          break;
        }
      }
      return {
        ...state,
        activeConversation: { ...state.activeConversation, messages: msgs },
      };
    }
    case ASSISTANT_ACTIONS.STREAM_COMPLETED: {
      const msgs = state.activeConversation.messages.slice();
      for (let i = msgs.length - 1; i >= 0; i--) {
        if (msgs[i].sender_type === "assistant" && msgs[i].streaming) {
          msgs[i] = { ...msgs[i], content: action.payload?.content ?? msgs[i].content, streaming: false };
          break;
        }
      }
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
    case ASSISTANT_ACTIONS.STREAM_ERROR:
      return {
        ...state,
        activeConversation: {
          ...state.activeConversation,
          streaming: false,
          error: action.payload,
        },
      };
    case ASSISTANT_ACTIONS.STREAM_CLOSED:
      return {
        ...state,
        activeConversation: { ...state.activeConversation, streaming: false },
      };

    // ── UI ────────────────────────────────────────────────────────────
    case ASSISTANT_ACTIONS.UI_TOGGLE_COLLAPSED:
      return { ...state, ui: { ...state.ui, collapsed: !state.ui.collapsed } };
    case ASSISTANT_ACTIONS.UI_SET_COLLAPSED:
      return { ...state, ui: { ...state.ui, collapsed: !!action.payload } };
    case ASSISTANT_ACTIONS.UI_SET_TAB:
      return { ...state, ui: { ...state.ui, activeTab: action.payload } };
    case ASSISTANT_ACTIONS.UI_SET_WORKSPACE_MODE:
      return { ...state, ui: { ...state.ui, workspaceMode: !!action.payload } };
    case ASSISTANT_ACTIONS.UI_SET_ACTIVE_ACTION:
      return { ...state, ui: { ...state.ui, activeActionSlug: action.payload } };

    default:
      return state;
  }
}

function extractFollowups(messages) {
  if (!messages || messages.length === 0) return [];
  const last = messages[messages.length - 1];
  if (last.sender_type !== "assistant") return [];
  return last.structured_payload?.followups || [];
}
