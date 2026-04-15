// AssistantSidebar — the persistent right rail.
//
// Mounted by App.jsx on every route. Sections:
//   Header — context badge, workspace toggle, new-conversation,
//            collapse/expand
//   Tabs   — Actions | Chat | History | Command
//            (keyboard Alt+[ / Alt+] to rotate)
//   Body   — one of the four panels depending on activeTab
//   Footer — ChatComposer, visible on Actions and Chat tabs
//
// Widths:
//   Collapsed       — 44px icon-only rail with expand button
//   Normal expanded — 360px right rail
//   Workspace mode  — 560px right rail (wider surface for longer chats)
//
// Lifecycle:
//   - unmount aborts any in-flight stream (handled by useAssistantClient)
//   - route change aborts the in-flight stream (useEffect on pathname)
//   - feature-flag gated on me.feature_flags.assistant_sidebar
//   - permission-gated on can("assistant.chat")

import { useEffect, useMemo, useRef } from "react";
import { useLocation } from "react-router-dom";
import { useMe } from "../hooks/useMe";
import { usePermissions } from "../hooks/usePermissions";
import { useCurrentContext } from "../hooks/useCurrentContext";
import { useAssistantClient } from "./useAssistantClient";
import { ASSISTANT_TABS } from "./useAssistantState";
import ConversationList from "./ConversationList";
import ChatThread from "./ChatThread";
import ChatComposer from "./ChatComposer";
import QuickActionLauncher from "./QuickActionLauncher";
import CommandModePanel from "./CommandModePanel";

export default function AssistantSidebar() {
  const { me, loading: meLoading } = useMe();
  const { can } = usePermissions();
  const currentContext = useCurrentContext();
  const location = useLocation();
  const {
    assistant,
    toggleCollapsed,
    setTab,
    startNewConversation,
    toggleWorkspaceMode,
    setWorkspaceMode,
    abortCurrent,
  } = useAssistantClient();

  const collapsed = assistant.ui.collapsed;
  const workspaceMode = assistant.ui.workspaceMode;
  const activeTab = assistant.ui.activeTab;
  const railRef = useRef(null);

  // Abort any in-flight stream when the route changes. The reducer
  // leaves partial content as-is and tags the bubble as aborted.
  useEffect(() => {
    abortCurrent();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  // Global keyboard shortcuts:
  //   Escape         — exit workspace mode (if active)
  //   Alt+[ / Alt+]  — rotate tabs (only outside form inputs)
  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape" && workspaceMode) {
        setWorkspaceMode(false);
        return;
      }
      const tag = document.activeElement?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") return;
      if (!e.altKey) return;
      if (e.key === "]") setTab("next");
      else if (e.key === "[") setTab("prev");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [workspaceMode, setWorkspaceMode, setTab]);

  if (meLoading) return null;
  if (me?.feature_flags?.assistant_sidebar === false) return null;
  if (!can("assistant.chat")) return null;

  if (collapsed) {
    return (
      <aside className="rex-assistant-rail rex-assistant-rail--collapsed" aria-label="Assistant sidebar collapsed">
        <button
          type="button"
          className="rex-assistant-rail__expand"
          onClick={toggleCollapsed}
          aria-label="Expand assistant"
          title="Expand assistant"
        >
          ◀
        </button>
        <div className="rex-assistant-rail__collapsed-label" aria-hidden="true">REX AI</div>
      </aside>
    );
  }

  const railClass = [
    "rex-assistant-rail",
    workspaceMode ? "rex-assistant-rail--workspace" : "",
  ].filter(Boolean).join(" ");

  return (
    <aside ref={railRef} className={railClass} aria-label="Assistant sidebar">
      <header className="rex-assistant-rail__header">
        <div className="rex-assistant-rail__header-title">
          <span className="rex-assistant-rail__brand">REX AI</span>
          <ContextBadge context={currentContext} />
        </div>
        <div className="rex-assistant-rail__header-actions">
          <button
            type="button"
            className="rex-assistant-rail__icon-btn"
            onClick={startNewConversation}
            aria-label="Start new conversation"
            title="New conversation"
          >
            +
          </button>
          <button
            type="button"
            className="rex-assistant-rail__icon-btn"
            onClick={toggleWorkspaceMode}
            aria-label={workspaceMode ? "Exit workspace mode" : "Enter workspace mode"}
            title={workspaceMode ? "Exit workspace (Esc)" : "Workspace mode"}
            aria-pressed={workspaceMode}
          >
            {workspaceMode ? "◧" : "⊞"}
          </button>
          <button
            type="button"
            className="rex-assistant-rail__icon-btn"
            onClick={toggleCollapsed}
            aria-label="Collapse assistant"
            title="Collapse"
          >
            ▶
          </button>
        </div>
      </header>

      <nav className="rex-assistant-rail__tabs" role="tablist" aria-label="Assistant sections">
        <TabButton active={activeTab === ASSISTANT_TABS.QUICK_ACTIONS} onClick={() => setTab(ASSISTANT_TABS.QUICK_ACTIONS)}>
          Actions
        </TabButton>
        <TabButton active={activeTab === ASSISTANT_TABS.THREAD} onClick={() => setTab(ASSISTANT_TABS.THREAD)}>
          Chat
        </TabButton>
        <TabButton active={activeTab === ASSISTANT_TABS.CONVERSATIONS} onClick={() => setTab(ASSISTANT_TABS.CONVERSATIONS)}>
          History
        </TabButton>
        <TabButton active={activeTab === ASSISTANT_TABS.COMMAND} onClick={() => setTab(ASSISTANT_TABS.COMMAND)}>
          Command
        </TabButton>
      </nav>

      <div className="rex-assistant-rail__body">
        {activeTab === ASSISTANT_TABS.QUICK_ACTIONS && <QuickActionLauncher />}
        {activeTab === ASSISTANT_TABS.THREAD && <ChatThread />}
        {activeTab === ASSISTANT_TABS.CONVERSATIONS && <ConversationList />}
        {activeTab === ASSISTANT_TABS.COMMAND && <CommandModePanel />}
      </div>

      {(activeTab === ASSISTANT_TABS.THREAD || activeTab === ASSISTANT_TABS.QUICK_ACTIONS) && (
        <footer className="rex-assistant-rail__footer">
          <ChatComposer />
        </footer>
      )}
    </aside>
  );
}

function TabButton({ active, onClick, children }) {
  return (
    <button
      type="button"
      className={`rex-assistant-tab${active ? " rex-assistant-tab--active" : ""}`}
      onClick={onClick}
      aria-selected={active}
      role="tab"
      tabIndex={active ? 0 : -1}
    >
      {children}
    </button>
  );
}

function ContextBadge({ context }) {
  const label = useMemo(() => {
    if (context.project?.name) return context.project.name;
    if (context.route?.name === "my_day") return "My Day";
    if (context.route?.name === "control_plane") return "Control Plane";
    return "No project";
  }, [context]);

  return (
    <span className="rex-assistant-rail__context" title={`${context.route.name} · ${context.route.path}`}>
      <span className="rex-assistant-rail__context-dot" aria-hidden="true" />
      {label}
    </span>
  );
}
