// Assistant UI preference persistence.
//
// Persists three keys across reloads via localStorage:
//   collapsed      — boolean
//   activeTab      — string (one of ASSISTANT_TABS)
//   workspaceMode  — boolean
//
// Deliberately minimal: no JSON schema validation, no versioning, no
// namespace beyond a flat "rex.assistant.ui" key. If localStorage is
// unavailable (SSR, sandboxed iframe, private mode) all functions
// no-op and return the defaults — persistence is a quality-of-life
// feature, never a requirement.

const STORAGE_KEY = "rex.assistant.ui";

function isLocalStorageAvailable() {
  try {
    if (typeof window === "undefined" || !window.localStorage) return false;
    const testKey = "__rex_ls_probe__";
    window.localStorage.setItem(testKey, "1");
    window.localStorage.removeItem(testKey);
    return true;
  } catch {
    return false;
  }
}

export function loadUiPrefs() {
  if (!isLocalStorageAvailable()) return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    const out = {};
    if (typeof parsed.collapsed === "boolean") out.collapsed = parsed.collapsed;
    if (typeof parsed.activeTab === "string") out.activeTab = parsed.activeTab;
    if (typeof parsed.workspaceMode === "boolean") out.workspaceMode = parsed.workspaceMode;
    return out;
  } catch {
    return {};
  }
}

export function saveUiPrefs(ui) {
  if (!isLocalStorageAvailable()) return;
  try {
    const payload = {
      collapsed: !!ui.collapsed,
      activeTab: ui.activeTab,
      workspaceMode: !!ui.workspaceMode,
    };
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    /* ignore — persistence is best-effort */
  }
}
