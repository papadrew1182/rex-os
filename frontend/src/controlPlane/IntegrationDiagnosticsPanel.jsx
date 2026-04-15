// IntegrationDiagnosticsPanel — operator-facing integration status.
//
// Reads the source-state store in `lib/integrationSource.js` and
// renders a compact table: one row per surface (identity, permissions,
// context, catalog, conversations, chat stream, control-plane
// connectors/automations/queue, my day home) with its current source
// (live/mock/unavailable/pending), last successful fetch time, last
// error, and any normalization performed.
//
// Also shows the master switch + a runtime override toggle so
// operators can flip between mock and live modes without a rebuild.
// The runtime override writes to localStorage and immediately triggers
// a reload so all surfaces re-resolve their source state cleanly.
//
// Design notes:
//   - this is a read-only diagnostic; it never writes backend state
//   - it never fabricates data — if a surface is `pending`, it shows so
//   - it lives in Control Plane so demo flows don't see it
//   - it does not depend on react state libraries — subscribes to the
//     tiny pub/sub store and keeps a local useState for the snapshot

import { useEffect, useState, useMemo } from "react";
import {
  subscribe,
  getSnapshot,
  SOURCE_SURFACES,
} from "../lib/integrationSource";
import { USE_ASSISTANT_MOCKS, shouldUseMocks } from "../lib/api";

const SURFACE_LABEL = {
  identity: "GET /api/me",
  permissions: "GET /api/me/permissions",
  context: "GET /api/context/current",
  catalog: "GET /api/assistant/catalog",
  conversations: "GET /api/assistant/conversations",
  conversationDetail: "GET /api/assistant/conversations/{id}",
  chatStream: "POST /api/assistant/chat (SSE)",
  controlPlaneConnectors: "GET /api/control-plane/connectors",
  controlPlaneAutomations: "GET /api/control-plane/automations",
  controlPlaneQueue: "GET /api/control-plane/queue",
  myDayHome: "GET /api/myday/home",
};

const SOURCE_BADGE = {
  live: { label: "live", cls: "rex-readiness rex-readiness--live" },
  mock: { label: "mock", cls: "rex-readiness rex-readiness--adapter" },
  unavailable: { label: "unavailable", cls: "rex-readiness rex-readiness--blocked" },
  pending: { label: "pending", cls: "rex-readiness rex-readiness--unknown" },
};

function formatRelative(iso) {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  const diff = Date.now() - then;
  if (diff < 1000) return "just now";
  if (diff < 60000) return `${Math.round(diff / 1000)}s ago`;
  if (diff < 3600000) return `${Math.round(diff / 60000)}m ago`;
  return new Date(iso).toLocaleTimeString();
}

function readOverride() {
  try {
    return typeof localStorage !== "undefined"
      ? localStorage.getItem("rex.assistant.use_mocks")
      : null;
  } catch { return null; }
}

export default function IntegrationDiagnosticsPanel() {
  const [snapshot, setSnapshot] = useState(() => getSnapshot());
  const [overrideValue, setOverrideValue] = useState(() => readOverride());

  useEffect(() => {
    const unsub = subscribe((snap) => setSnapshot(snap));
    // Force an initial paint of the already-resolved surfaces so the
    // panel doesn't look empty on first mount.
    setSnapshot(getSnapshot());
    return unsub;
  }, []);

  const effectiveMode = useMemo(() => (shouldUseMocks() ? "mock" : "live"), [overrideValue]);

  // Roll-up: partially live = some surfaces live + some mock/unavailable
  const rollup = useMemo(() => {
    const counts = { live: 0, mock: 0, unavailable: 0, pending: 0 };
    for (const k of SOURCE_SURFACES) counts[snapshot[k]?.source || "pending"] += 1;
    if (counts.live > 0 && counts.mock === 0 && counts.unavailable === 0) return "fully live";
    if (counts.mock > 0 && counts.live === 0 && counts.unavailable === 0) return "fully mocked";
    if (counts.unavailable > 0 && counts.live === 0) return "live unavailable — running on mocks";
    if (counts.live > 0 && (counts.mock > 0 || counts.unavailable > 0)) return "partially live";
    return "resolving…";
  }, [snapshot]);

  const setMockOverride = (val) => {
    try {
      if (val === null) localStorage.removeItem("rex.assistant.use_mocks");
      else localStorage.setItem("rex.assistant.use_mocks", val);
    } catch { /* ignore */ }
    setOverrideValue(val);
    // Reload so all surface fetches re-resolve cleanly. The operator
    // expects a hard state transition, not a half-populated view.
    if (typeof window !== "undefined") window.location.reload();
  };

  return (
    <div>
      <div className="rex-integration-summary">
        <div>
          <div className="rex-stat-label">Effective mode</div>
          <div className="rex-stat-num" style={{ fontSize: 18 }}>{effectiveMode}</div>
          <div className="rex-stat-sub">
            compile-time flag: <code>USE_ASSISTANT_MOCKS = {String(USE_ASSISTANT_MOCKS)}</code>
          </div>
        </div>
        <div>
          <div className="rex-stat-label">Runtime override</div>
          <div className="rex-stat-num" style={{ fontSize: 18 }}>
            {overrideValue === null ? "—" : overrideValue}
          </div>
          <div className="rex-stat-sub">
            localStorage key <code>rex.assistant.use_mocks</code>
          </div>
          <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
            <button
              type="button"
              className="rex-btn rex-btn-outline"
              onClick={() => setMockOverride("true")}
              disabled={overrideValue === "true"}
            >
              Force mock
            </button>
            <button
              type="button"
              className="rex-btn rex-btn-outline"
              onClick={() => setMockOverride("false")}
              disabled={overrideValue === "false"}
            >
              Go live
            </button>
            <button
              type="button"
              className="rex-btn rex-btn-outline"
              onClick={() => setMockOverride(null)}
              disabled={overrideValue === null}
            >
              Clear override
            </button>
          </div>
        </div>
        <div>
          <div className="rex-stat-label">Assistant rollup</div>
          <div className="rex-stat-num" style={{ fontSize: 18 }}>{rollup}</div>
          <div className="rex-stat-sub">
            across {SOURCE_SURFACES.length} contract surfaces
          </div>
        </div>
      </div>

      <p className="rex-muted" style={{ fontSize: 12, marginTop: 12 }}>
        Each row reflects the most recent fetch for that surface. <b>live</b> means
        a real backend call succeeded and matched the frozen contract;
        <b> mock</b> means the mock path was used (either because mocks are
        forced on or the master switch is on); <b>unavailable</b> means the live
        call failed the contract probe or the network — the surface then falls
        back to the mock shape so the UI degrades gracefully.
      </p>

      <div className="rex-table-wrap">
        <div className="rex-table-scroll">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Surface</th>
                <th>Source</th>
                <th>Last fetch</th>
                <th>Last error</th>
                <th>Normalizations / issues</th>
              </tr>
            </thead>
            <tbody>
              {SOURCE_SURFACES.map((key) => {
                const row = snapshot[key] || {};
                const badge = SOURCE_BADGE[row.source || "pending"];
                const details = [
                  ...(row.normalizations || []).map((n) => `normalized: ${n}`),
                  ...(row.probeIssues || []).map((n) => `probe: ${n}`),
                ];
                return (
                  <tr key={key}>
                    <td style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
                      {SURFACE_LABEL[key] || key}
                    </td>
                    <td>
                      <span className={badge.cls}>{badge.label}</span>
                    </td>
                    <td style={{ fontSize: 12 }}>{formatRelative(row.lastFetchAt)}</td>
                    <td style={{ fontSize: 11, maxWidth: 220, wordBreak: "break-word" }}>
                      {row.lastError || "—"}
                    </td>
                    <td style={{ fontSize: 11, maxWidth: 260, wordBreak: "break-word" }}>
                      {details.length === 0 ? (
                        <span className="rex-muted">—</span>
                      ) : (
                        <ul style={{ margin: 0, paddingLeft: 14 }}>
                          {details.map((d, i) => <li key={i}>{d}</li>)}
                        </ul>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
