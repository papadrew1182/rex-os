// useMe — contract-driven hook for GET /api/me.
//
// Returns `{ me, loading, error, refetch }` where `me` matches the
// Session 3 contract exactly:
//
//   {
//     id, email, full_name,
//     primary_role_key,
//     role_keys,
//     legacy_role_aliases,
//     project_ids,
//     feature_flags
//   }
//
// The identity load is done once at the AppProvider level and cached
// via React context; this hook just reads the cached value. The fetch
// itself is handled by `AppContext`.

import { useContext } from "react";
import { AppContext } from "../app/AppContext";

export function useMe() {
  const ctx = useContext(AppContext);
  return {
    me: ctx.me,
    loading: ctx.meLoading,
    error: ctx.meError,
    refetch: ctx.refetchMe,
  };
}
