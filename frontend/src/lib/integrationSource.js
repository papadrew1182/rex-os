// integrationSource — the single source-state registry.
//
// Every contract-driven data surface (identity, permissions, context,
// catalog, conversations, chat, control plane, my day) reports its
// current source here. The reported source is one of:
//
//   "live"        — a real backend call succeeded and matched contract
//   "mock"        — mocks are in use because USE_ASSISTANT_MOCKS is on
//                   (or a runtime override set it)
//   "unavailable" — we attempted live and it failed / drifted
//   "pending"     — nothing has resolved yet (initial state)
//
// The registry is a tiny pub/sub store (no state library). The
// diagnostics panel subscribes; lib/api.js calls set() on each call.
//
// Record fields per surface:
//   source             — current source ("live" | "mock" | "unavailable" | "pending")
//   lastFetchAt        — ISO timestamp of last successful read
//   lastErrorAt        — ISO timestamp of last error (live path)
//   lastError          — human-readable error message from most recent failure
//   normalizations     — array of short strings describing shape fixes applied
//   probeIssues        — array of contract-probe issues (populated on drift)
//   attemptedLive      — true once the live path was tried at least once
//
// Subscription is optional; the diagnostics panel passes a React state
// setter so it repaints when any surface flips.

const SURFACES = [
  "identity",
  "permissions",
  "context",
  "catalog",
  "conversations",
  "conversationDetail",
  "chatStream",
  "controlPlaneConnectors",
  "controlPlaneAutomations",
  "controlPlaneQueue",
  "myDayHome",
];

function makeBlank() {
  return {
    source: "pending",
    lastFetchAt: null,
    lastErrorAt: null,
    lastError: null,
    normalizations: [],
    probeIssues: [],
    attemptedLive: false,
  };
}

const state = Object.fromEntries(SURFACES.map((s) => [s, makeBlank()]));
const listeners = new Set();

export const SOURCE_SURFACES = SURFACES;

export function subscribe(fn) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function notify() {
  for (const fn of listeners) {
    try { fn(getSnapshot()); } catch { /* listener errors are not our problem */ }
  }
}

export function getSnapshot() {
  // Return a shallow copy so React equality checks behave.
  const out = {};
  for (const k of SURFACES) out[k] = { ...state[k] };
  return out;
}

export function getSurface(surface) {
  return state[surface] ? { ...state[surface] } : null;
}

export function markPending(surface) {
  if (!state[surface]) return;
  state[surface] = { ...state[surface], source: "pending" };
  notify();
}

export function markMock(surface, opts = {}) {
  if (!state[surface]) return;
  state[surface] = {
    ...state[surface],
    source: "mock",
    lastFetchAt: new Date().toISOString(),
    // mock reads don't clear prior live errors — they stay in the record
    // so the operator can see "last live attempt failed N minutes ago"
    attemptedLive: state[surface].attemptedLive || !!opts.attemptedLive,
  };
  notify();
}

export function markLive(surface, { normalizations = [] } = {}) {
  if (!state[surface]) return;
  state[surface] = {
    ...state[surface],
    source: "live",
    lastFetchAt: new Date().toISOString(),
    lastError: null,
    lastErrorAt: null,
    normalizations,
    probeIssues: [],
    attemptedLive: true,
  };
  notify();
}

export function markUnavailable(surface, { error, probeIssues = [] } = {}) {
  if (!state[surface]) return;
  state[surface] = {
    ...state[surface],
    source: "unavailable",
    lastError: typeof error === "string" ? error : error?.message || String(error),
    lastErrorAt: new Date().toISOString(),
    probeIssues,
    attemptedLive: true,
  };
  notify();
}

// Dev helper so tests can reset between runs.
export function __resetIntegrationSourceForTests() {
  for (const k of SURFACES) state[k] = makeBlank();
  listeners.clear();
}
