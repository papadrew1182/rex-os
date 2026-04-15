// AppContext — top-level provider for the assistant-lane state model.
//
// Buckets:
//   me                    — from GET /api/me
//   permissions           — from GET /api/me/permissions
//   assistantCatalog      — from GET /api/assistant/catalog
//   assistantConversations — from GET /api/assistant/conversations
//   activeConversation    — full thread once selected
//   assistantUIState      — collapsed, activeTab, workspaceMode, streaming
//
// Deliberately kept small: React context + reducer, no Redux / Zustand /
// Jotai / Recoil. The assistant reducer lives in
// `assistant/useAssistantState.js` and is wired into this provider.

import { createContext, useState, useEffect, useCallback, useMemo, useReducer } from "react";
import {
  fetchMe,
  fetchPermissions,
  fetchAssistantCatalog,
  fetchAssistantConversations,
  fetchAssistantConversation,
} from "../lib/api";
import {
  assistantReducer,
  initialAssistantState,
  buildInitialAssistantState,
  ASSISTANT_ACTIONS,
} from "../assistant/useAssistantState";
import { saveUiPrefs } from "../assistant/uiPrefs";

export const AppContext = createContext({
  // identity
  me: null,
  meLoading: true,
  meError: null,
  refetchMe: () => {},
  // permissions
  permissions: [],
  permissionsLoading: true,
  permissionsError: null,
  refetchPermissions: () => {},
  // assistant state
  assistant: initialAssistantState,
  assistantDispatch: () => {},
  // assistant data loaders
  loadCatalog: () => {},
  loadConversations: () => {},
  loadConversation: (id) => {},
});

export function AppProvider({ children }) {
  // ── Identity ──────────────────────────────────────────────────────────
  const [me, setMe] = useState(null);
  const [meLoading, setMeLoading] = useState(true);
  const [meError, setMeError] = useState(null);

  const refetchMe = useCallback(() => {
    setMeLoading(true);
    setMeError(null);
    fetchMe()
      .then((body) => setMe(body.user))
      .catch((e) => setMeError(e.message || String(e)))
      .finally(() => setMeLoading(false));
  }, []);

  useEffect(() => { refetchMe(); }, [refetchMe]);

  // ── Permissions ───────────────────────────────────────────────────────
  const [permissions, setPermissions] = useState([]);
  const [permissionsLoading, setPermissionsLoading] = useState(true);
  const [permissionsError, setPermissionsError] = useState(null);

  const refetchPermissions = useCallback(() => {
    setPermissionsLoading(true);
    setPermissionsError(null);
    fetchPermissions()
      .then((body) => setPermissions(body.permissions || []))
      .catch((e) => setPermissionsError(e.message || String(e)))
      .finally(() => setPermissionsLoading(false));
  }, []);

  useEffect(() => { refetchPermissions(); }, [refetchPermissions]);

  // ── Assistant state (reducer + persistence) ──────────────────────────
  // buildInitialAssistantState rehydrates UI prefs from localStorage
  // (collapsed / activeTab / workspaceMode) so a reload restores the
  // user's last layout. An effect below writes them back on every
  // ui change so the persistence is eventually consistent.
  const [assistant, assistantDispatch] = useReducer(
    assistantReducer,
    undefined,
    buildInitialAssistantState,
  );

  useEffect(() => {
    saveUiPrefs(assistant.ui);
  }, [assistant.ui.collapsed, assistant.ui.activeTab, assistant.ui.workspaceMode]);

  const loadCatalog = useCallback(async () => {
    assistantDispatch({ type: ASSISTANT_ACTIONS.CATALOG_LOADING });
    try {
      const body = await fetchAssistantCatalog();
      assistantDispatch({ type: ASSISTANT_ACTIONS.CATALOG_LOADED, payload: body });
    } catch (e) {
      assistantDispatch({ type: ASSISTANT_ACTIONS.CATALOG_ERROR, payload: e.message || String(e) });
    }
  }, []);

  const loadConversations = useCallback(async () => {
    assistantDispatch({ type: ASSISTANT_ACTIONS.CONVERSATIONS_LOADING });
    try {
      const body = await fetchAssistantConversations();
      assistantDispatch({ type: ASSISTANT_ACTIONS.CONVERSATIONS_LOADED, payload: body.items || [] });
    } catch (e) {
      assistantDispatch({ type: ASSISTANT_ACTIONS.CONVERSATIONS_ERROR, payload: e.message || String(e) });
    }
  }, []);

  const loadConversation = useCallback(async (id) => {
    assistantDispatch({ type: ASSISTANT_ACTIONS.ACTIVE_CONVERSATION_LOADING, payload: id });
    try {
      const body = await fetchAssistantConversation(id);
      assistantDispatch({ type: ASSISTANT_ACTIONS.ACTIVE_CONVERSATION_LOADED, payload: body });
    } catch (e) {
      assistantDispatch({ type: ASSISTANT_ACTIONS.ACTIVE_CONVERSATION_ERROR, payload: e.message || String(e) });
    }
  }, []);

  // Bootstrap: load catalog + conversation list once identity is known,
  // and only if the assistant_sidebar feature flag is true.
  useEffect(() => {
    if (!me) return;
    if (me.feature_flags?.assistant_sidebar === false) return;
    loadCatalog();
    loadConversations();
  }, [me, loadCatalog, loadConversations]);

  const value = useMemo(() => ({
    me,
    meLoading,
    meError,
    refetchMe,
    permissions,
    permissionsLoading,
    permissionsError,
    refetchPermissions,
    assistant,
    assistantDispatch,
    loadCatalog,
    loadConversations,
    loadConversation,
  }), [
    me, meLoading, meError, refetchMe,
    permissions, permissionsLoading, permissionsError, refetchPermissions,
    assistant, loadCatalog, loadConversations, loadConversation,
  ]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
