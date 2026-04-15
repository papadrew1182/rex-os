// ConnectorHealthPanel — lists connector adapters and sync state.
//
// Data source: GET /api/control-plane/connectors (mocked for now).
// Landing fields from Session 2: { key, label, status, health,
// last_sync_at, last_error, readiness_state }.
//
// Also renders a "dependent actions" column computed client-side from
// the assistant catalog: for each connector, show which catalog
// actions list that connector in their `required_connectors`. This
// makes the blast-radius of a connector outage obvious to operators.

import { useContext, useEffect, useMemo, useState } from "react";
import { fetchControlPlaneConnectors } from "../lib/api";
import { AppContext } from "../app/AppContext";

export default function ConnectorHealthPanel() {
  const { assistant } = useContext(AppContext);
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchControlPlaneConnectors()
      .then((body) => setItems(body.items || []))
      .catch((e) => setError(e.message || String(e)));
  }, []);

  // Build connector → [action slugs] map from the catalog payload.
  // Pure derivation — no backend round trip. When Session 2 ships the
  // real control_plane endpoint with first-class dependency data, this
  // derivation gets replaced by a direct field read.
  const connectorActionMap = useMemo(() => {
    const actions = assistant.catalog.data?.actions || [];
    const map = {};
    for (const action of actions) {
      for (const conn of action.required_connectors || []) {
        if (!map[conn]) map[conn] = [];
        map[conn].push(action.slug);
      }
    }
    return map;
  }, [assistant.catalog.data]);

  if (error) {
    return (
      <div className="rex-alert rex-alert-red">
        Couldn't load connectors: {error}
      </div>
    );
  }
  if (!items) {
    return <p className="rex-muted">Loading connectors…</p>;
  }

  if (items.length === 0) {
    return (
      <div className="rex-empty">
        <div className="rex-empty-icon">⚙</div>
        No connectors registered yet.
      </div>
    );
  }

  return (
    <>
      <p className="rex-muted" style={{ marginBottom: 12, fontSize: 12 }}>
        Connectors ingest external system data into <code>rex</code> canonical
        tables. The "dependent actions" column shows which catalog actions
        require each connector's adapter to be live — a blocked connector
        cascades readiness into those actions.
      </p>
      <div className="rex-table-wrap">
        <div className="rex-table-scroll">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Connector</th>
                <th>Status</th>
                <th>Health</th>
                <th>Last sync</th>
                <th>Dependent actions</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {items.map((c) => {
                const deps = connectorActionMap[c.key] || [];
                return (
                  <tr key={c.key}>
                    <td style={{ fontWeight: 600 }}>{c.label || c.key}</td>
                    <td>{c.status}</td>
                    <td>{c.health || "—"}</td>
                    <td style={{ fontSize: 12 }}>{c.last_sync_at || "—"}</td>
                    <td>
                      {deps.length === 0 ? (
                        <span className="rex-muted" style={{ fontSize: 11 }}>—</span>
                      ) : (
                        <div className="rex-control-connector__deps">
                          {deps.map((slug) => (
                            <span key={slug} className="rex-control-connector__dep">{slug}</span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="rex-muted" style={{ fontSize: 12 }}>
                      {c.status === "adapter_pending" && "Adapter wiring lands in Session 2."}
                      {c.status === "blocked" && "Unblock before flipping dependent actions to live."}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
