// usePermissions — contract-driven hook for GET /api/me/permissions.
//
// Returns a flat list of permission strings plus a `can(permission)`
// helper. This is the assistant-lane permission gate; it intentionally
// does NOT replace the legacy `src/permissions.js` hook which is still
// used by the 32-page product shell for project-write affordance
// hiding. Import paths disambiguate the two:
//
//   from "../permissions"         → legacy { canWrite, isAdminOrVp, ... }
//   from "../hooks/usePermissions" → this file, returns { permissions, can, ... }
//
// The permission strings must match the backend-issued slugs exactly —
// do not introduce frontend-only permission names.

import { useContext, useCallback } from "react";
import { AppContext } from "../app/AppContext";

export function usePermissions() {
  const ctx = useContext(AppContext);
  const permissions = ctx.permissions || [];

  const can = useCallback(
    (permission) => permissions.includes(permission),
    [permissions],
  );

  return {
    permissions,
    can,
    loading: ctx.permissionsLoading,
    error: ctx.permissionsError,
    refetch: ctx.refetchPermissions,
  };
}
