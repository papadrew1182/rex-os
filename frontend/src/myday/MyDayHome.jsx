// MyDayHome — starter personalized home surface.
//
// First-pass content: greeting, role/project context, suggested
// quick actions pulled from the current-context assistant_defaults,
// and a CTA that launches the My Day Briefing action through the
// persistent assistant sidebar.
//
// Phase 8 of the roadmap builds this out into alerts, upcoming
// meetings, weather impact, top priorities, and digest history.
// That work slots in here without restructuring the route.

import { useMemo } from "react";
import { useMe } from "../hooks/useMe";
import { useCurrentContext } from "../hooks/useCurrentContext";
import { useAssistantClient } from "../assistant/useAssistantClient";
import { ASSISTANT_TABS } from "../assistant/useAssistantState";

function timeOfDayGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export default function MyDayHome() {
  const { me } = useMe();
  const currentContext = useCurrentContext();
  const { assistant, launchAction, setTab, setCollapsed } = useAssistantClient();

  const suggestedSlugs = currentContext.assistant_defaults?.suggested_action_slugs || [];
  const catalogActions = assistant.catalog.data?.actions || [];
  const suggestedActions = useMemo(() => {
    return suggestedSlugs
      .map((slug) => catalogActions.find((a) => a.slug === slug))
      .filter(Boolean);
  }, [suggestedSlugs, catalogActions]);

  const firstName = useMemo(() => {
    if (!me?.full_name) return "";
    return me.full_name.split(" ")[0] || me.full_name;
  }, [me]);

  const openAssistant = (action) => {
    setCollapsed(false);
    setTab(ASSISTANT_TABS.QUICK_ACTIONS);
    if (action) launchAction(action);
  };

  return (
    <div className="rex-myday">
      <header className="rex-myday__header">
        <h1 className="rex-h1" style={{ margin: 0 }}>
          {timeOfDayGreeting()}{firstName ? `, ${firstName}` : ""}
        </h1>
        <p className="rex-muted" style={{ marginTop: 6 }}>
          Your personalized operations home. Phase 8 will fill this with alerts,
          upcoming meetings, field weather, and top priorities.
        </p>
      </header>

      <div className="rex-grid-3" style={{ marginBottom: 18 }}>
        <div className="rex-stat-card">
          <div className="rex-stat-label">Your role</div>
          <div className="rex-stat-num" style={{ fontSize: 22 }}>{me?.primary_role_key || "—"}</div>
          <div className="rex-stat-sub">canonical role key</div>
        </div>
        <div className="rex-stat-card">
          <div className="rex-stat-label">Accessible projects</div>
          <div className="rex-stat-num">{(me?.project_ids || []).length}</div>
          <div className="rex-stat-sub">from /api/me.project_ids</div>
        </div>
        <div className="rex-stat-card amber">
          <div className="rex-stat-label">Open alerts</div>
          <div className="rex-stat-num amber">—</div>
          <div className="rex-stat-sub">Phase 8 alerts pipeline</div>
        </div>
      </div>

      <section className="rex-myday__section">
        <h2 className="rex-h3">Suggested for you</h2>
        <p className="rex-muted" style={{ fontSize: 13, marginBottom: 12 }}>
          These suggestions come from your role + current context. The list is
          backend-driven — the frontend does not invent them.
        </p>
        {suggestedActions.length === 0 ? (
          <div className="rex-empty">
            <div className="rex-empty-icon">◎</div>
            The catalog is still loading or has no actions visible to your role.
          </div>
        ) : (
          <div className="rex-grid-2">
            {suggestedActions.map((action) => (
              <button
                key={action.slug}
                type="button"
                className="rex-myday__action-card"
                onClick={() => openAssistant(action)}
              >
                <div className="rex-myday__action-card-title">{action.label}</div>
                <div className="rex-myday__action-card-desc">{action.description}</div>
                <div className="rex-myday__action-card-footer">
                  <span className={`rex-readiness rex-readiness--${action.readiness_state}`}>
                    {action.readiness_state}
                  </span>
                  <span className="rex-muted" style={{ fontSize: 11 }}>Launch in assistant →</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      <section className="rex-myday__section">
        <h2 className="rex-h3">Quick launch</h2>
        <p className="rex-muted" style={{ fontSize: 13, marginBottom: 12 }}>
          Open the assistant with a starter action.
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button
            type="button"
            className="rex-btn rex-btn-primary"
            onClick={() => {
              const action = catalogActions.find((a) => a.slug === "my_day_briefing");
              openAssistant(action);
            }}
          >
            Run My Day Briefing
          </button>
          <button
            type="button"
            className="rex-btn rex-btn-outline"
            onClick={() => {
              setCollapsed(false);
              setTab(ASSISTANT_TABS.QUICK_ACTIONS);
            }}
          >
            Browse all actions
          </button>
          <button
            type="button"
            className="rex-btn rex-btn-outline"
            onClick={() => {
              setCollapsed(false);
              setTab(ASSISTANT_TABS.COMMAND);
            }}
          >
            Open command mode
          </button>
        </div>
      </section>
    </div>
  );
}
