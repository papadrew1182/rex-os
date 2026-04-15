// useCurrentContext — contract-driven hook for GET /api/context/current.
//
// The Session 3 contract returns:
//
//   {
//     project: { id, name, status } | null,
//     route: { name, path },
//     page_context: { surface, entity_type, entity_id, filters },
//     assistant_defaults: { suggested_action_slugs }
//   }
//
// For the first pass we synthesize this client-side from React Router's
// `useLocation` + the existing `useProject()` hook so the assistant can
// attach real context to every `POST /api/assistant/chat` request
// immediately — no backend dependency. Once Session 2 lands
// `/api/context/current`, callers can switch to the server-side
// derivation without changing this hook's public return shape.

import { useMemo } from "react";
import { useLocation } from "react-router-dom";
import { useProject } from "../project";
import { useMe } from "./useMe";

// Route name resolution — tightly bounded so we don't guess on every
// path. Extend as the sidebar-shell lanes add more canonical surfaces.
const ROUTE_NAME_MAP = {
  "/": "portfolio",
  "/my-day": "my_day",
  "/control-plane": "control_plane",
  "/projects": "project_list",
  "/notifications": "notifications",
  "/photos": "photos",
  "/rfis": "rfis",
  "/punch-list": "punch_list",
  "/submittals": "submittals",
  "/schedule": "schedule",
  "/checklists": "checklists",
};

function resolveRouteName(pathname) {
  if (ROUTE_NAME_MAP[pathname]) return ROUTE_NAME_MAP[pathname];
  for (const prefix of Object.keys(ROUTE_NAME_MAP)) {
    if (prefix !== "/" && pathname.startsWith(prefix + "/")) return ROUTE_NAME_MAP[prefix];
  }
  if (pathname.startsWith("/projects/")) return "project_dashboard";
  return "shell";
}

export function useCurrentContext() {
  const location = useLocation();
  const { selected: project } = useProject();
  const { me } = useMe();

  return useMemo(() => {
    const routeName = resolveRouteName(location.pathname);
    const surface = routeName === "my_day" ? "my_day"
      : routeName === "control_plane" ? "control_plane"
      : routeName === "project_dashboard" ? "project_dashboard"
      : "shell";

    const entity_type = routeName === "project_dashboard" || project ? "project" : null;
    const entity_id = project?.id || null;

    return {
      project: project ? {
        id: project.id,
        name: project.name,
        status: project.status || "active",
      } : null,
      route: {
        name: routeName,
        path: location.pathname,
      },
      page_context: {
        surface,
        entity_type,
        entity_id,
        filters: {},
      },
      assistant_defaults: {
        // Default suggestions are role-aware. VPs see portfolio-level
        // suggestions; field roles see operational defaults. The
        // backend version will derive this from role + recent activity.
        suggested_action_slugs: defaultSuggestionsForRole(me?.primary_role_key),
      },
    };
  }, [location.pathname, project, me?.primary_role_key]);
}

function defaultSuggestionsForRole(roleKey) {
  switch (roleKey) {
    case "VP":
      return ["portfolio_snapshot", "morning_briefing", "budget_variance"];
    case "PM":
      return ["budget_variance", "rfi_aging", "two_week_lookahead"];
    case "GENERAL_SUPER":
    case "LEAD_SUPER":
    case "ASSISTANT_SUPER":
      return ["daily_log_summary", "two_week_lookahead", "rfi_aging"];
    case "ACCOUNTANT":
      return ["budget_variance", "change_event_sweep", "invoice_lien_compliance"];
    default:
      return ["morning_briefing", "my_day_briefing"];
  }
}
