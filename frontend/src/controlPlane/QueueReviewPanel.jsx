// QueueReviewPanel — placeholder for the writeback/action approval queue.
//
// Phase 6 scope: action queue, writeback queue, auto queue, approval
// rules, reverse-sync outbox. All land after Session 1/Session 2.
// This first pass is a mounted placeholder so the control plane tab
// exists in the shell from day one.

import { useEffect, useState } from "react";
import { fetchControlPlaneQueue } from "../lib/api";

export default function QueueReviewPanel() {
  const [items, setItems] = useState(null);

  useEffect(() => {
    fetchControlPlaneQueue()
      .then((body) => setItems(body.items || []))
      .catch(() => setItems([]));
  }, []);

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
          <div className="rex-stat-num amber">0</div>
          <div className="rex-stat-sub">not yet wired</div>
        </div>
        <div className="rex-stat-card green">
          <div className="rex-stat-label">Auto-pass-through</div>
          <div className="rex-stat-num green">0</div>
          <div className="rex-stat-sub">tasks, notes, drafts</div>
        </div>
      </div>

      <div className="rex-empty">
        <div className="rex-empty-icon">✓</div>
        No items in the queue. Command mode + writeback rails will populate this surface.
      </div>
    </div>
  );
}
