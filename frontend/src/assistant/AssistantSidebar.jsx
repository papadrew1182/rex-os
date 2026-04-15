// AssistantSidebar — the persistent right rail.
//
// Mounted by app/Shell.jsx on every route. Sections:
//   Header — collapse/expand toggle, current route + project context
//   Tabs   — Conversations | Thread | Quick Actions | Command
//   Body   — one of the four panels depending on activeTab
//
// Collapse behavior:
//   - Expanded: 360px wide, full content
//   - Collapsed: 44px wide, icon-only rail with a single "expand" button
//   - Hidden entirely if feature_flags.assistant_sidebar is false
//
// Narrow viewports: the existing rex-theme media queries at 1100/900/560
// hide the rail by default; the hamburger in the topbar can surface it
// as a drawer later. For this first pass the rail is desktop-only.

import { useMemo } from "react";
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
  const {
    assistant,
    toggleCollapsed,
    setTab,
    startNewConversation,
  } = useAssistantClient();

  // Feature flag gate — if assistant_sidebar is disabled, render nothing.
  if (meLoading) return null;
  if (me?.feature_flags?.assistant_sidebar === false) return null;
  if (!can("assistant.chat")) return null;

  const collapsed = assistant.ui.collapsed;
  const activeTab = assistant.ui.activeTab;

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
        <div className="rex-assistant-rail__collapsed-label" aria-hidden="true">AI</div>
      </aside>
    );
  }

  return (
    <aside className="rex-assistant-rail" aria-label="Assistant sidebar">
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
            onClick={toggleCollapsed}
            aria-label="Collapse assistant"
            title="Collapse"
          >
            ▶
          </button>
        </div>
      </header>

      <nav className="rex-assistant-rail__tabs" aria-label="Assistant sections">
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
