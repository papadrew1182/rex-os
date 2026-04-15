// contractProbes — thin developer-readable shape validators.
//
// Each probe takes a raw response body and returns:
//
//   { ok: true,  issues: [] }
//   { ok: false, issues: ["missing X", "Y should be array", ...] }
//
// Probes are deliberately NOT JSON-schema-complete — they check the
// minimum set of fields the frontend actually reads, and return
// human-readable strings a developer can scan. They do NOT throw.
// They do NOT mutate. They do NOT normalize — normalization lives in
// lib/api.js next to the fetch call that owns it.
//
// The contracts are pulled verbatim from Session 3 charter
// §/api/me, §/api/me/permissions, §/api/context/current,
// §/api/assistant/catalog, §/api/assistant/conversations,
// §/api/assistant/conversations/{id}, and the POST /assistant/chat ack.
//
// When the backend team updates a contract, the one place that needs
// to move is this file — the wrapper in lib/api.js keeps flowing.

const CANONICAL_ROLES = new Set([
  "VP", "PM", "GENERAL_SUPER", "LEAD_SUPER", "ASSISTANT_SUPER", "ACCOUNTANT",
]);

const READINESS_STATES = new Set([
  "live", "alpha", "adapter_pending", "writeback_pending", "blocked", "disabled",
]);

function ok() {
  return { ok: true, issues: [] };
}

function fail(issues) {
  return { ok: false, issues: Array.isArray(issues) ? issues : [issues] };
}

function missingKeys(obj, keys) {
  return keys.filter((k) => obj[k] === undefined);
}

// ── Identity / permissions / context ──────────────────────────────────

export function probeMeShape(raw) {
  if (!raw || typeof raw !== "object") return fail("response is not an object");
  // Contract wraps user in { user: {...} } envelope.
  const user = raw.user ?? raw; // accept both { user } and a bare user for tolerance
  const issues = [];
  const missing = missingKeys(user, [
    "id", "email", "full_name", "primary_role_key", "role_keys",
    "project_ids", "feature_flags",
  ]);
  for (const k of missing) issues.push(`missing user.${k}`);
  if (user.role_keys && !Array.isArray(user.role_keys)) {
    issues.push("user.role_keys should be an array");
  }
  if (user.project_ids && !Array.isArray(user.project_ids)) {
    issues.push("user.project_ids should be an array");
  }
  if (user.primary_role_key && !CANONICAL_ROLES.has(user.primary_role_key)) {
    issues.push(`user.primary_role_key '${user.primary_role_key}' is not canonical`);
  }
  if (Array.isArray(user.role_keys)) {
    for (const r of user.role_keys) {
      if (!CANONICAL_ROLES.has(r)) issues.push(`role_keys contains non-canonical '${r}'`);
    }
  }
  return issues.length === 0 ? ok() : fail(issues);
}

export function probePermissionsShape(raw) {
  if (!raw || typeof raw !== "object") return fail("response is not an object");
  if (!Array.isArray(raw.permissions)) return fail("missing permissions array");
  const bad = raw.permissions.filter((p) => typeof p !== "string");
  if (bad.length) return fail(`permissions array contains non-string entries: ${bad.length}`);
  return ok();
}

export function probeCurrentContextShape(raw) {
  if (!raw || typeof raw !== "object") return fail("response is not an object");
  const issues = [];
  if (raw.project !== null && raw.project !== undefined && typeof raw.project !== "object") {
    issues.push("project should be an object or null");
  }
  if (!raw.route || typeof raw.route !== "object") issues.push("missing route object");
  else {
    if (typeof raw.route.name !== "string") issues.push("route.name should be a string");
    if (typeof raw.route.path !== "string") issues.push("route.path should be a string");
  }
  if (!raw.page_context || typeof raw.page_context !== "object") {
    issues.push("missing page_context object");
  }
  if (!raw.assistant_defaults || typeof raw.assistant_defaults !== "object") {
    issues.push("missing assistant_defaults");
  } else if (!Array.isArray(raw.assistant_defaults.suggested_action_slugs)) {
    issues.push("assistant_defaults.suggested_action_slugs should be an array");
  }
  return issues.length === 0 ? ok() : fail(issues);
}

// ── Assistant catalog / conversations / chat ─────────────────────────

export function probeCatalogShape(raw) {
  if (!raw || typeof raw !== "object") return fail("response is not an object");
  const issues = [];
  if (typeof raw.version !== "string") issues.push("missing string catalog.version");
  if (!Array.isArray(raw.categories)) issues.push("missing catalog.categories array");
  if (!Array.isArray(raw.actions)) return fail("missing catalog.actions array");

  raw.actions.forEach((action, i) => {
    const tag = `actions[${i}]`;
    if (!action || typeof action !== "object") {
      issues.push(`${tag} is not an object`);
      return;
    }
    if (typeof action.slug !== "string") issues.push(`${tag}.slug missing/non-string`);
    if (typeof action.label !== "string") issues.push(`${tag}.label missing/non-string`);
    if (typeof action.category !== "string") issues.push(`${tag}.category missing/non-string`);
    if (action.readiness_state && !READINESS_STATES.has(action.readiness_state)) {
      issues.push(`${tag}.readiness_state '${action.readiness_state}' not in vocabulary`);
    }
    if (action.role_visibility && !Array.isArray(action.role_visibility)) {
      issues.push(`${tag}.role_visibility should be an array`);
    } else if (Array.isArray(action.role_visibility)) {
      for (const r of action.role_visibility) {
        if (!CANONICAL_ROLES.has(r)) issues.push(`${tag}.role_visibility has non-canonical '${r}'`);
      }
    }
    if (action.params_schema && !Array.isArray(action.params_schema)) {
      issues.push(`${tag}.params_schema should be an array`);
    }
    if (action.required_connectors && !Array.isArray(action.required_connectors)) {
      issues.push(`${tag}.required_connectors should be an array`);
    }
  });
  return issues.length === 0 ? ok() : fail(issues);
}

export function probeConversationsListShape(raw) {
  if (!raw || typeof raw !== "object") return fail("response is not an object");
  if (!Array.isArray(raw.items)) return fail("missing items array");
  const issues = [];
  raw.items.forEach((c, i) => {
    const tag = `items[${i}]`;
    if (!c || typeof c !== "object") { issues.push(`${tag} not an object`); return; }
    if (typeof c.id !== "string") issues.push(`${tag}.id missing/non-string`);
    if (c.title !== null && c.title !== undefined && typeof c.title !== "string") {
      issues.push(`${tag}.title should be string or null`);
    }
  });
  return issues.length === 0 ? ok() : fail(issues);
}

export function probeConversationDetailShape(raw) {
  if (!raw || typeof raw !== "object") return fail("response is not an object");
  const issues = [];
  if (!raw.conversation || typeof raw.conversation !== "object") {
    issues.push("missing conversation object");
  } else if (typeof raw.conversation.id !== "string") {
    issues.push("conversation.id missing/non-string");
  }
  if (!Array.isArray(raw.messages)) {
    issues.push("missing messages array");
  } else {
    raw.messages.forEach((m, i) => {
      const tag = `messages[${i}]`;
      if (!m || typeof m !== "object") { issues.push(`${tag} not an object`); return; }
      if (typeof m.id !== "string") issues.push(`${tag}.id missing/non-string`);
      if (m.sender_type !== "user" && m.sender_type !== "assistant") {
        issues.push(`${tag}.sender_type must be 'user' or 'assistant'`);
      }
    });
  }
  return issues.length === 0 ? ok() : fail(issues);
}

export function probeChatAckShape(raw) {
  if (!raw || typeof raw !== "object") return fail("response is not an object");
  if (raw.accepted !== true) return fail("ack.accepted !== true");
  // conversation_id is optional on first ack (backend may assign it
  // inside the SSE stream via conversation.created).
  return ok();
}

// ── Control plane ─────────────────────────────────────────────────────

export function probeConnectorsShape(raw) {
  if (!raw || typeof raw !== "object") return fail("response is not an object");
  if (!Array.isArray(raw.items)) return fail("missing items array");
  const issues = [];
  raw.items.forEach((c, i) => {
    const tag = `items[${i}]`;
    if (!c || typeof c !== "object") { issues.push(`${tag} not an object`); return; }
    if (typeof c.key !== "string") issues.push(`${tag}.key missing/non-string`);
  });
  return issues.length === 0 ? ok() : fail(issues);
}

export function probeAutomationsShape(raw) {
  if (!raw || typeof raw !== "object") return fail("response is not an object");
  if (!Array.isArray(raw.items)) return fail("missing items array");
  const issues = [];
  raw.items.forEach((a, i) => {
    const tag = `items[${i}]`;
    if (!a || typeof a !== "object") { issues.push(`${tag} not an object`); return; }
    if (typeof a.slug !== "string") issues.push(`${tag}.slug missing/non-string`);
    if (a.readiness_state && !READINESS_STATES.has(a.readiness_state)) {
      issues.push(`${tag}.readiness_state '${a.readiness_state}' not in vocabulary`);
    }
  });
  return issues.length === 0 ? ok() : fail(issues);
}

// Vocabulary check for SSE event names — used by lib/sse.js when it
// sees a live event name, so non-canonical names get reported once
// without breaking the dispatcher.
const SSE_EVENTS = new Set([
  "conversation.created",
  "message.started",
  "message.delta",
  "message.completed",
  "followups.generated",
  "action.suggestions",
  "error",
]);

export function isKnownSseEvent(name) {
  return SSE_EVENTS.has(name);
}
