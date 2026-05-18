// QueueReviewPanel — placeholder for the writeback/action approval queue.
//
// Phase 6 scope: action queue, writeback queue, auto queue, approval
// rules, reverse-sync outbox. All land after Session 1/Session 2.
// This first pass is a mounted placeholder so the control plane tab
// exists in the shell from day one.

import { useEffect, useState } from "react";
import {
  approveAction,
  discardAction,
  fetchControlPlaneQueue,
  fetchPendingActions,
} from "../lib/api";

export default function QueueReviewPanel() {
  const [items, setItems] = useState(null);
  const [pending, setPending] = useState(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");

  async function loadPending() {
    try {
      const body = await fetchPendingActions();
      setPending(body.items || []);
      setError("");
    } catch (err) {
      setPending([]);
      setError(err?.message || "Failed to load pending actions.");
    }
  }

  useEffect(() => {
    fetchControlPlaneQueue()
      .then((body) => setItems(body.items || []))
      .catch(() => setItems([]));
    loadPending();
  }, []);

  async function runAction(kind, actionId) {
    setBusyId(actionId);
    try {
      if (kind === "approve") await approveAction(actionId);
      if (kind === "discard") await discardAction(actionId);
      await loadPending();
    } catch (err) {
      setError(err?.message || `Failed to ${kind} action.`);
    } finally {
      setBusyId("");
    }
  }

  return (
    <div className="rex-control-queue">
      <div className="rex-alert rex-alert-amber" style={{ marginBottom: 16 }}>
        <span style={{ flex: 1 }}>
          The writeback + action approval queue lands in Phase 6 (Session 1
          action router + Session 2 connector adapters must be live first).
          This panel is mounted now so approvals have a home when the
          infrastructure arrives.
        </span>
      </div>

      <div className="rex-grid-3" style={{ marginBottom: 16 }}>
        <div className="rex-stat-card">
          <div className="rex-stat-label">Pending actions</div>
          <div className="rex-stat-num">{items ? items.length : "—"}</div>
          <div className="rex-stat-sub">writeback_pending</div>
        </div>
        <div className="rex-stat-card amber">
          <div className="rex-stat-label">Awaiting approval</div>
          <div className="rex-stat-num amber">{pending ? pending.length : "—"}</div>
          <div className="rex-stat-sub">live `/api/actions/pending`</div>
        </div>
        <div className="rex-stat-card green">
          <div className="rex-stat-label">Auto-pass-through</div>
          <div className="rex-stat-num green">0</div>
          <div className="rex-stat-sub">tasks, notes, drafts</div>
        </div>
      </div>

      {error ? (
        <div className="rex-alert rex-alert-red" style={{ marginBottom: 16 }}>
          {error}
        </div>
      ) : null}

      {pending && pending.length > 0 ? (
        <div className="rex-table-wrap" style={{ marginBottom: 16 }}>
          <div className="rex-table-scroll">
            <table className="rex-table">
              <thead>
                <tr>
                  <th>Tool</th>
                  <th>Status</th>
                  <th>Created</th>
                  <th>Risk</th>
                  <th style={{ width: 180 }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {pending.map((row) => {
                  const isBusy = busyId === row.id;
                  return (
                    <tr key={row.id}>
                      <td style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}>
                        {row.tool_slug}
                      </td>
                      <td>{row.status}</td>
                      <td>{row.created_at ? new Date(row.created_at).toLocaleString() : "—"}</td>
                      <td>{row.blast_radius?.risk_tier || "unknown"}</td>
                      <td>
                        <div style={{ display: "flex", gap: 8 }}>
                          <button
                            type="button"
                            className="rex-btn"
                            onClick={() => runAction("approve", row.id)}
                            disabled={isBusy}
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            className="rex-btn secondary"
                            onClick={() => runAction("discard", row.id)}
                            disabled={isBusy}
                          >
                            Discard
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      <div className="rex-empty">
        <div className="rex-empty-icon">✓</div>
        {!pending ? "Loading queue…" : "No items in the queue. Command mode + writeback rails will populate this surface."}
      </div>
    </div>
  );
}
