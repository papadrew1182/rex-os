// ConnectorHealthPanel — lists connector adapters and sync state.
//
// Data source: GET /api/control-plane/connectors (mocked for now).
// Landing fields from Session 2: { key, label, status, health,
// last_sync_at, last_error, readiness_state }.

import { useEffect, useState } from "react";
import { fetchControlPlaneConnectors } from "../lib/api";

export default function ConnectorHealthPanel() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchControlPlaneConnectors()
      .then((body) => setItems(body.items || []))
      .catch((e) => setError(e.message || String(e)));
  }, []);

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
    <div className="rex-table-wrap">
      <div className="rex-table-scroll">
        <table className="rex-table">
          <thead>
            <tr>
              <th>Connector</th>
              <th>Status</th>
              <th>Health</th>
              <th>Last sync</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {items.map((c) => (
              <tr key={c.key}>
                <td style={{ fontWeight: 600 }}>{c.label || c.key}</td>
                <td>{c.status}</td>
                <td>{c.health || "—"}</td>
                <td>{c.last_sync_at || "—"}</td>
                <td className="rex-muted" style={{ fontSize: 12 }}>
                  {c.status === "adapter_pending" && "Adapter wiring lands in Session 2."}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
