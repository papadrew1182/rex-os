// useAssistantClient — high-level assistant action hook.
//
// Exposes:
//   sendMessage(text, opts)  — POST /api/assistant/chat + SSE stream
//   selectConversation(id)   — load a conversation into activeConversation
//   startNewConversation()   — clear activeConversation and focus composer
//   launchAction(slug, params) — run a catalog action via sendMessage
//   toggleCollapsed(), setTab(), setWorkspaceMode()
//
// The hook is stateless in the React sense — all state lives in the
// reducer managed by AppContext. This just wires user intents to
// dispatches + the SSE client + optional POST.
//
// Contract note: every `sendMessage` call attaches the current
// `page_context` + `client_context` derived from `useCurrentContext`
// so the backend has enough grounding to answer even before the
// route-aware context endpoint lands.

import { useContext, useCallback, useRef } from "react";
import { AppContext } from "../app/AppContext";
import { ASSISTANT_ACTIONS, ASSISTANT_TABS } from "./useAssistantState";
import { openAssistantStream } from "../lib/sse";
import { postAssistantChat } from "../lib/api";
import { useCurrentContext } from "../hooks/useCurrentContext";

export function useAssistantClient() {
  const ctx = useContext(AppContext);
  const currentContext = useCurrentContext();
  const streamRef = useRef(null);

  const sendMessage = useCallback(async (text, opts = {}) => {
    if (!text || !text.trim()) return;

    // Close any existing stream before opening a new one
    if (streamRef.current) {
      streamRef.current.close();
      streamRef.current = null;
    }

    const payload = {
      conversation_id: ctx.assistant.activeConversation.id || null,
      message: text,
      project_id: currentContext.project?.id || null,
      active_action_slug: opts.activeActionSlug || ctx.assistant.ui.activeActionSlug || null,
      mode: opts.mode || "chat",
      params: opts.params || {},
      page_context: {
        route: currentContext.route.path,
        surface: "assistant_sidebar",
        entity_type: currentContext.page_context.entity_type,
        entity_id: currentContext.page_context.entity_id,
      },
      client_context: {
        selected_project_id: currentContext.project?.id || null,
        route_name: currentContext.route.name,
      },
      stream: true,
    };

    // Optimistic user message + thread placeholder
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.APPEND_LOCAL_USER_MESSAGE, payload: { content: text } });
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_SET_TAB, payload: ASSISTANT_TABS.THREAD });

    // POST (mocked) — returns the conversation_id to use
    let accepted;
    try {
      accepted = await postAssistantChat(payload);
    } catch (e) {
      ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.STREAM_ERROR, payload: e.message || String(e) });
      return;
    }

    // Open streaming response
    streamRef.current = openAssistantStream({ ...payload, conversation_id: accepted.conversation_id }, {
      onEvent: (eventName, data) => {
        switch (eventName) {
          case "conversation.created":
            // If this was a fresh conversation, attach the new id now
            if (!ctx.assistant.activeConversation.id) {
              ctx.assistantDispatch({
                type: ASSISTANT_ACTIONS.ACTIVE_CONVERSATION_LOADED,
                payload: {
                  conversation: {
                    id: data.conversation_id,
                    title: text.slice(0, 50),
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
            // TODO: dispatch into a dedicated bucket once there's a surface for it
            break;
          case "error":
            ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.STREAM_ERROR, payload: data?.message || "stream error" });
            break;
          default:
            break;
        }
      },
      onError: (err) => {
        ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.STREAM_ERROR, payload: err.message || String(err) });
      },
      onClose: () => {
        ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.STREAM_CLOSED });
        streamRef.current = null;
      },
    });
  }, [ctx, currentContext]);

  const selectConversation = useCallback((id) => {
    ctx.loadConversation(id);
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_SET_TAB, payload: ASSISTANT_TABS.THREAD });
  }, [ctx]);

  const startNewConversation = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.close();
      streamRef.current = null;
    }
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.ACTIVE_CONVERSATION_CLEAR });
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_SET_ACTIVE_ACTION, payload: null });
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_SET_TAB, payload: ASSISTANT_TABS.THREAD });
  }, [ctx]);

  const launchAction = useCallback(async (action, params = {}) => {
    if (!action) return;
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_SET_ACTIVE_ACTION, payload: action.slug });
    // Promptless launch: send a synthesized message the user can follow up on
    const text = `Run ${action.label}${Object.keys(params).length ? ` (${Object.keys(params).join(", ")})` : ""}`;
    await sendMessage(text, { activeActionSlug: action.slug, params });
  }, [ctx, sendMessage]);

  const toggleCollapsed = useCallback(() => {
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_TOGGLE_COLLAPSED });
  }, [ctx]);

  const setCollapsed = useCallback((value) => {
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_SET_COLLAPSED, payload: value });
  }, [ctx]);

  const setTab = useCallback((tab) => {
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_SET_TAB, payload: tab });
  }, [ctx]);

  const setWorkspaceMode = useCallback((value) => {
    ctx.assistantDispatch({ type: ASSISTANT_ACTIONS.UI_SET_WORKSPACE_MODE, payload: value });
  }, [ctx]);

  return {
    // state accessors
    assistant: ctx.assistant,
    // actions
    sendMessage,
    selectConversation,
    startNewConversation,
    launchAction,
    toggleCollapsed,
    setCollapsed,
    setTab,
    setWorkspaceMode,
  };
}
