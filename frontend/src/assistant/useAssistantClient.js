// useAssistantClient — high-level assistant action hook.
//
// Exposes:
//   sendMessage(text, opts)      — POST /api/assistant/chat + open SSE
//   retryLastFailed()            — re-send the last failed message
//   selectConversation(id)       — load a conversation
//   startNewConversation()       — clear state (incl. active action + params)
//   launchAction(action, params) — run a catalog action via sendMessage
//   runCommand(text)             — sendMessage in mode="command"
//   toggleCollapsed(), setCollapsed(), setTab(),
//   toggleWorkspaceMode(), setWorkspaceMode(),
//   abortCurrent()               — cancel any in-flight stream
//
// Invariants:
//   - one request builder (buildChatRequest) powers quick-action,
//     freeform chat, and command mode so the POST body shape is
//     identical across all three and any backend change touches one
//     place
//   - any call to sendMessage/launchAction/runCommand aborts any
//     currently-running stream before starting a new one (no double
//     streams against the same conversation)
//   - a pending-send flag in the reducer prevents duplicate clicks
//   - on unmount (hook cleanup effect), any in-flight stream is aborted
//   - route change aborts in-flight stream via AssistantSidebar's
//     location effect, not this hook

import { useContext, useCallback, useRef, useEffect } from "react";
import { AppContext } from "../app/AppContext";
import { ASSISTANT_ACTIONS, ASSISTANT_TABS } from "./useAssistantState";
import { openAssistantStream } from "../lib/sse";
import { postAssistantChat } from "../lib/api";
import { useCurrentContext } from "../hooks/useCurrentContext";

// ── Request builder (single source of truth for POST body shape) ─────
//
// Keeping this pure so it can be unit-tested independently of React.
// Exported for tests; UI components should use the hook methods, not
// call this directly.
export function buildChatRequest({
  text,
  mode = "chat",
  activeActionSlug = null,
  params = {},
  conversationId = null,
  currentContext,
}) {
  const projectId = currentContext?.project?.id || null;
  return {
    conversation_id: conversationId || null,
    message: text,
    project_id: projectId,
    active_action_slug: activeActionSlug,
    mode,
    params: params || {},
    page_context: {
      route: currentContext?.route?.path || "/",
      surface: "assistant_sidebar",
      entity_type: currentContext?.page_context?.entity_type ?? null,
      entity_id: currentContext?.page_context?.entity_id ?? null,
    },
    client_context: {
      selected_project_id: projectId,
      route_name: currentContext?.route?.name || "shell",
    },
    stream: true,
  };
}

export function useAssistantClient() {
  const ctx = useContext(AppContext);
  const currentContext = useCurrentContext();
  const streamRef = useRef(null);

  // Abort any in-flight stream — safe to call from cleanup paths.
  const abortCurrent = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.close();
      streamRef.current = null;
      ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.STREAM_ABORT });
      ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.SEND_SETTLED });
    }
  }, [ctx]);

  // Abort on unmount. Prevents stream callbacks from firing into a
  // dispatched reducer of a dead React tree.
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.close();
        streamRef.current = null;
      }
    };
  }, []);

  // Core send. Used by freeform chat (text + opts), quick action
  // (text synthesized from action.label), and command mode.
  const sendMessage = useCallback(async (text, opts = {}) => {
    if (!text || !text.trim()) return;

    // Duplicate-send guard.
    if (ctx.assistant.ui.pending) return;

    // Close any existing stream before opening a new one.
    if (streamRef.current) {
      streamRef.current.close();
      streamRef.current = null;
    }

    const conversationId = ctx.assistant.activeConversation.id || null;
    const payload = buildChatRequest({
      text,
      mode: opts.mode || "chat",
      activeActionSlug: opts.activeActionSlug || ctx.assistant.ui.activeActionSlug || null,
      params: opts.params || {},
      conversationId,
      currentContext,
    });

    const localId = `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

    ctx.assistantDispatch({
      type: ASSISTANT_ACTIONS.APPEND_LOCAL_USER_MESSAGE,
      payload: { content: text, localId },
    });
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_SET_TAB, payload: ASSISTANT_TABS.THREAD });
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.CLEAR_LAST_FAILED_MESSAGE });
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.SEND_PENDING });

    let accepted;
    try {
      accepted = await postAssistantChat(payload);
    } catch (e) {
      ctx.assistantDispatch({
        type: ASSISTANT_ACTIONS.SET_LAST_FAILED_MESSAGE,
        payload: { text, opts, localId, error: e.message || String(e) },
      });
      ctx.assistantDispatch({
        type: ASSISTANT_ACTIONS.STREAM_ERROR,
        payload: e.message || String(e),
      });
      ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.SEND_SETTLED });
      return;
    }

    streamRef.current = openAssistantStream(
      { ...payload, conversation_id: accepted.conversation_id || conversationId },
      {
        onEvent: (eventName, data) => {
          switch (eventName) {
            case "conversation.created":
              if (!ctx.assistant.activeConversation.id) {
                ctx.assistantDispatch({
                  type: ASSISTANT_ACTIONS.ACTIVE_CONVERSATION_LOADED,
                  payload: {
                    conversation: {
                      id: data.conversation_id,
                      title: text.slice(0, 60),
                      project_id: currentContext.project?.id || null,
                      active_action_slug: payload.active_action_slug,
                      page_context: payload.page_context,
                    },
                    messages: ctx.assistant.activeConversation.messages,
                  },
                });
              }
              break;
            case "message.started":
              ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.STREAM_STARTED, payload: data });
              break;
            case "message.delta":
              ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.STREAM_DELTA, payload: data });
              break;
            case "message.completed":
              ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.STREAM_COMPLETED, payload: data });
              break;
            case "followups.generated":
              ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.STREAM_FOLLOWUPS, payload: data });
              break;
            case "action.suggestions":
              // Session 1 has not frozen the payload shape.
              // Reducer's STREAM_ACTION_SUGGESTIONS handler uses
              // safeActionSuggestions() to accept several shapes
              // defensively and ignore anything else.
              ctx.assistantDispatch({
                type: ASSISTANT_ACTIONS.STREAM_ACTION_SUGGESTIONS,
                payload: data,
              });
              break;
            case "error":
              ctx.assistantDispatch({
                type: ASSISTANT_ACTIONS.STREAM_ERROR,
                payload: data?.message || "stream error",
              });
              ctx.assistantDispatch({
                type: ASSISTANT_ACTIONS.SET_LAST_FAILED_MESSAGE,
                payload: { text, opts, localId, error: data?.message || "stream error" },
              });
              break;
            case "action_proposed":
              ctx.assistantDispatch({
                type: ASSISTANT_ACTIONS.ACTION_PROPOSED,
                payload: data,
              });
              break;
            case "action_auto_committed":
              ctx.assistantDispatch({
                type: ASSISTANT_ACTIONS.ACTION_AUTO_COMMITTED,
                payload: data,
              });
              break;
            case "action_failed":
              ctx.assistantDispatch({
                type: ASSISTANT_ACTIONS.ACTION_FAILED,
                payload: data,
              });
              break;
            default:
              break;
          }
        },
        onError: (err) => {
          ctx.assistantDispatch({
            type: ASSISTANT_ACTIONS.STREAM_ERROR,
            payload: err?.message || String(err),
          });
          ctx.assistantDispatch({
            type: ASSISTANT_ACTIONS.SET_LAST_FAILED_MESSAGE,
            payload: { text, opts, localId, error: err?.message || String(err) },
          });
        },
        onClose: () => {
          ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.STREAM_CLOSED });
          ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.SEND_SETTLED });
          streamRef.current = null;
        },
      },
    );
  }, [ctx, currentContext]);

  const retryLastFailed = useCallback(async () => {
    const failed = ctx.assistant.activeConversation.lastFailedMessage;
    if (!failed) return;
    ctx.assistantDispatch({
      type: ASSISTANT_ACTIONS.REMOVE_LOCAL_USER_MESSAGE,
      payload: { localId: failed.localId },
    });
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.CLEAR_LAST_FAILED_MESSAGE });
    await sendMessage(failed.text, failed.opts || {});
  }, [ctx, sendMessage]);

  const selectConversation = useCallback((id) => {
    // Switching conversations always aborts in-flight stream so deltas
    // from the old conversation can't leak into the new one.
    if (streamRef.current) {
      streamRef.current.close();
      streamRef.current = null;
    }
    ctx.loadConversation(id);
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_SET_TAB, payload: ASSISTANT_TABS.THREAD });
  }, [ctx]);

  const startNewConversation = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.close();
      streamRef.current = null;
    }
    // ACTIVE_CONVERSATION_CLEAR also resets ui.activeActionSlug in the
    // reducer — so a new conversation starts with the action picker
    // cleared and the param form blank.
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.ACTIVE_CONVERSATION_CLEAR });
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_SET_TAB, payload: ASSISTANT_TABS.THREAD });
  }, [ctx]);

  const launchAction = useCallback(async (action, params = {}) => {
    if (!action) return;
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_SET_ACTIVE_ACTION, payload: action.slug });
    const paramSummary = Object.keys(params).length > 0
      ? ` (${Object.entries(params).map(([k]) => k).join(", ")})`
      : "";
    const text = `Run ${action.label}${paramSummary}`;
    await sendMessage(text, { activeActionSlug: action.slug, params });
  }, [ctx, sendMessage]);

  const runCommand = useCallback(async (text) => {
    await sendMessage(text, { mode: "command" });
  }, [sendMessage]);

  const toggleCollapsed = useCallback(() => {
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_TOGGLE_COLLAPSED });
  }, [ctx]);

  const setCollapsed = useCallback((value) => {
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_SET_COLLAPSED, payload: value });
  }, [ctx]);

  const setTab = useCallback((tab) => {
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_SET_TAB, payload: tab });
  }, [ctx]);

  const toggleWorkspaceMode = useCallback(() => {
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_TOGGLE_WORKSPACE_MODE });
  }, [ctx]);

  const setWorkspaceMode = useCallback((value) => {
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_SET_WORKSPACE_MODE, payload: value });
  }, [ctx]);

  return {
    // state accessors
    assistant: ctx.assistant,
    // actions
    sendMessage,
    retryLastFailed,
    selectConversation,
    startNewConversation,
    launchAction,
    runCommand,
    toggleCollapsed,
    setCollapsed,
    setTab,
    toggleWorkspaceMode,
    setWorkspaceMode,
    abortCurrent,
  };
}
