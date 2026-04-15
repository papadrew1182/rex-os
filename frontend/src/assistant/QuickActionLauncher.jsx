// QuickActionLauncher — browse the assistant catalog + launch actions.
//
// Contract rules (NON-NEGOTIABLE):
//   - visibility comes from `role_visibility` array in the backend payload,
//     intersected with the user's `role_keys`
//   - runnability comes from `can_run` + `enabled` flags in the payload
//   - readiness comes from `readiness_state` — frontend only renders it,
//     never calculates it
//   - action identity is the `slug`; legacy C-* aliases are displayed
//     for operator memory only and never used for routing
//
// The frontend NEVER invents permission logic or synthesizes its own
// readiness state. If the backend says don't show it, it doesn't show.

import { useState, useMemo } from "react";
import { useMe } from "../hooks/useMe";
import { useCurrentContext } from "../hooks/useCurrentContext";
import { useAssistantClient } from "./useAssistantClient";
import ParamForm from "./ParamForm";

// Readiness vocabulary is contract-frozen — no invented values.
const READINESS_LABEL = {
  live: "Live",
  alpha: "Alpha",
  adapter_pending: "Adapter pending",
  writeback_pending: "Writeback pending",
  blocked: "Blocked",
  disabled: "Disabled",
};

const READINESS_CLASS = {
  live: "rex-readiness rex-readiness--live",
  alpha: "rex-readiness rex-readiness--alpha",
  adapter_pending: "rex-readiness rex-readiness--adapter",
  writeback_pending: "rex-readiness rex-readiness--writeback",
  blocked: "rex-readiness rex-readiness--blocked",
  disabled: "rex-readiness rex-readiness--disabled",
};

export default function QuickActionLauncher() {
  const { me } = useMe();
  const currentContext = useCurrentContext();
  const { assistant, launchAction } = useAssistantClient();
  const [selectedCategory, setSelectedCategory] = useState("ALL");
  const [expandedSlug, setExpandedSlug] = useState(null);

  const catalog = assistant.catalog.data;
  const catalogLoading = assistant.catalog.loading;
  const catalogError = assistant.catalog.error;

  const visibleActions = useMemo(() => {
    if (!catalog?.actions) return [];
    const userRoles = new Set(me?.role_keys || []);
    return catalog.actions.filter((action) => {
      // Role visibility from backend. If user has no overlap with
      // role_visibility, the action is hidden.
      if (action.role_visibility && action.role_visibility.length > 0) {
        const overlap = action.role_visibility.some((r) => userRoles.has(r));
        if (!overlap) return false;
      }
      // Hidden if backend explicitly disabled the action
      if (action.enabled === false) return false;
      return true;
    });
  }, [catalog, me?.role_keys]);

  const categories = catalog?.categories || [];
  const suggested = currentContext.assistant_defaults?.suggested_action_slugs || [];

  const filteredActions = useMemo(() => {
    if (selectedCategory === "ALL") return visibleActions;
    if (selectedCategory === "SUGGESTED") {
      return visibleActions.filter((a) => suggested.includes(a.slug));
    }
    return visibleActions.filter((a) => a.category === selectedCategory);
  }, [visibleActions, selectedCategory, suggested]);

  if (catalogLoading && !catalog) {
    return (
      <div className="rex-assistant-catalog rex-assistant-catalog--loading">
        <p className="rex-muted" style={{ fontSize: 12 }}>Loading action catalog…</p>
      </div>
    );
  }

  if (catalogError) {
    return (
      <div className="rex-assistant-catalog rex-assistant-catalog--error">
        <p className="rex-muted" style={{ fontSize: 12, color: "var(--rex-red)" }}>
          Couldn't load the catalog: {catalogError}
        </p>
      </div>
    );
  }

  if (!visibleActions.length) {
    return (
      <div className="rex-assistant-catalog rex-assistant-catalog--empty">
        <p className="rex-muted" style={{ fontSize: 12 }}>
          No actions are visible to your role yet. The catalog is registry-driven —
          actions will appear here as they become available to {me?.primary_role_key || "your role"}.
        </p>
      </div>
    );
  }

  return (
    <div className="rex-assistant-catalog">
      <div className="rex-assistant-catalog__filters" role="tablist" aria-label="Action category filter">
        <CategoryChip active={selectedCategory === "SUGGESTED"} onClick={() => setSelectedCategory("SUGGESTED")} count={suggested.length}>
          Suggested
        </CategoryChip>
        <CategoryChip active={selectedCategory === "ALL"} onClick={() => setSelectedCategory("ALL")}>
          All
        </CategoryChip>
        {categories.map((cat) => (
          <CategoryChip
            key={cat.key}
            active={selectedCategory === cat.key}
            onClick={() => setSelectedCategory(cat.key)}
          >
            {cat.label}
          </CategoryChip>
        ))}
      </div>

      <ul className="rex-assistant-catalog__list" role="list">
        {filteredActions.length === 0 && (
          <li className="rex-assistant-catalog__empty">
            <p className="rex-muted" style={{ fontSize: 12 }}>
              Nothing matches this filter.
            </p>
          </li>
        )}
        {filteredActions.map((action) => (
          <ActionCard
            key={action.slug}
            action={action}
            expanded={expandedSlug === action.slug}
            onToggle={() => setExpandedSlug((prev) => prev === action.slug ? null : action.slug)}
            onLaunch={(params) => launchAction(action, params)}
            currentContext={currentContext}
          />
        ))}
      </ul>
    </div>
  );
}

function CategoryChip({ active, onClick, children, count }) {
  return (
    <button
      type="button"
      className={`rex-assistant-catalog__chip${active ? " rex-assistant-catalog__chip--active" : ""}`}
      onClick={onClick}
      role="tab"
      aria-selected={active}
    >
      {children}
      {typeof count === "number" && count > 0 && (
        <span className="rex-assistant-catalog__chip-count">{count}</span>
      )}
    </button>
  );
}

function ActionCard({ action, expanded, onToggle, onLaunch, currentContext }) {
  const canRun = action.can_run !== false;
  const readinessLabel = READINESS_LABEL[action.readiness_state] || action.readiness_state || "unknown";
  const readinessCls = READINESS_CLASS[action.readiness_state] || "rex-readiness rex-readiness--unknown";

  const hasParams = action.params_schema && action.params_schema.length > 0;

  return (
    <li className={`rex-action-card${expanded ? " rex-action-card--expanded" : ""}`}>
      <button
        type="button"
        className="rex-action-card__header"
        onClick={onToggle}
        aria-expanded={expanded}
      >
        <div className="rex-action-card__title-row">
          <span className="rex-action-card__label">{action.label}</span>
          <span className={readinessCls}>{readinessLabel}</span>
        </div>
        <div className="rex-action-card__description">{action.description}</div>
        {action.legacy_aliases && action.legacy_aliases.length > 0 && (
          <div className="rex-action-card__aliases" title="Legacy quick-action IDs (informational only)">
            {action.legacy_aliases.join(" · ")}
          </div>
        )}
      </button>
      {expanded && (
        <div className="rex-action-card__body">
          {!canRun && (
            <div className="rex-action-card__not-runnable">
              Not runnable yet — {describeBlockReason(action)}
            </div>
          )}
          {hasParams ? (
            <ParamForm
              schema={action.params_schema}
              currentContext={currentContext}
              disabled={!canRun}
              onSubmit={(params) => onLaunch(params)}
              submitLabel={canRun ? `Run ${action.label}` : "Unavailable"}
            />
          ) : (
            <button
              type="button"
              className="rex-action-card__launch"
              disabled={!canRun}
              onClick={() => onLaunch({})}
            >
              {canRun ? `Run ${action.label}` : "Unavailable"}
            </button>
          )}
          {action.required_connectors && action.required_connectors.length > 0 && (
            <div className="rex-action-card__connectors">
              Requires: {action.required_connectors.join(", ")}
            </div>
          )}
        </div>
      )}
    </li>
  );
}

function describeBlockReason(action) {
  if (action.readiness_state === "adapter_pending") return "the connector adapter isn't live yet.";
  if (action.readiness_state === "writeback_pending") return "the writeback path isn't wired yet.";
  if (action.readiness_state === "blocked") return "a dependency is blocking this action.";
  if (action.readiness_state === "disabled") return "it's disabled in the registry.";
  return "not runnable for your current context.";
}
