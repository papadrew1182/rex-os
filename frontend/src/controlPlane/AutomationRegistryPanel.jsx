// AutomationRegistryPanel — scheduled automation job registry.
//
// Derived shape from Session 1's automation inventory. Shows enabled
// flag, schedule, last run/success/failure, and readiness state.

import { useEffect, useState } from "react";
import { fetchControlPlaneAutomations } from "../lib/api";

const READINESS_CLASS = {
  live: "rex-readiness rex-readiness--live",
  alpha: "rex-readiness rex-readiness--alpha",
  adapter_pending: "rex-readiness rex-readiness--adapter",
  writeback_pending: "rex-readiness rex-readiness--writeback",
  blocked: "rex-readiness rex-readiness--blocked",
  disabled: "rex-readiness rex-readiness--disabled",
};

export default function AutomationRegistryPanel() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchControlPlaneAutomations()
      .then((body) => setItems(body.items || []))
      .catch((e) => setError(e.message || String(e)));
  }, []);

  if (error) return <div className="rex-alert rex-alert-red">Couldn't load automations: {error}</div>;
  if (!items) return <p className="rex-muted">Loading automation registry…</p>;
  if (items.length === 0) {
    return (
      <div className="rex-empty">
        <div className="rex-empty-icon">⟳</div>
        No automations registered yet.
      </div>
    );
  }

  return (
    <div className="rex-table-wrap">
      <div className="rex-table-scroll">
        <table className="rex-table">
          <thead>
            <tr>
              <th>Slug</th>
              <th>Label</th>
              <th>Category</th>
              <th>Schedule</th>
              <th>Execution</th>
              <th>Enabled</th>
              <th>Readiness</th>
              <th>Last run</th>
            </tr>
          </thead>
          <tbody>
            {items.map((j) => (
              <tr key={j.slug}>
                <td style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>{j.slug}</td>
                <td style={{ fontWeight: 600 }}>{j.label}</td>
                <td>{j.category || "—"}</td>
                <td style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>{j.schedule_cron || "—"}</td>
                <td style={{ fontSize: 12 }}>{j.execution_type || "—"}</td>
                <td>{j.enabled ? "yes" : "no"}</td>
                <td>
                  <span className={READINESS_CLASS[j.readiness_state] || "rex-readiness rex-readiness--unknown"}>
                    {j.readiness_state || "unknown"}
                  </span>
                </td>
                <td style={{ fontSize: 12 }}>{j.last_success_at || j.last_run_at || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
