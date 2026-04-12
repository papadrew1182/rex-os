import { useAuth } from "./auth";

/**
 * Permission helper hook.
 *
 * Returns role-aware capabilities for the current user.
 * Backend is the source of truth — this is purely for UI affordance hiding.
 * The backend will still 403/404 if a non-permitted action sneaks through.
 *
 * Rules (mirrors backend dependencies.py):
 *   - is_admin OR global_role === "vp" → full write everywhere
 *   - any authenticated user → can read what they have project access to
 *   - frontend cannot know per-project ranks without an extra fetch, so we
 *     optimistically allow project members to attempt writes; backend gates
 */
export function usePermissions() {
  const { user } = useAuth();
  const isAdmin = !!(user && user.is_admin);
  const isVp = !!(user && user.global_role === "vp");
  const isAdminOrVp = isAdmin || isVp;

  return {
    user,
    isAdmin,
    isVp,
    isAdminOrVp,
    // Project-scoped writes — admin/VP always; others optimistic
    canWrite: isAdminOrVp,
    canFieldWrite: isAdminOrVp,
    canDelete: isAdminOrVp,
  };
}
