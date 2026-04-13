/**
 * AlertCallout — small page-level surface that fetches active notifications
 * for the current page context and renders them inline.
 *
 * Props:
 *   - notificationTypes: string[] of notification_type values to filter
 *   - title?: string, default "Active Alerts"
 *   - emptyHidden?: bool, default true (don't render anything when no alerts)
 */

import { useState, useEffect, useCallback } from "react";
import { api } from "./api";
import { useProject } from "./project";
import { useNotifications, severityDot, severityColor } from "./notifications";

export function AlertCallout({ notificationTypes, title = "Active alerts", emptyHidden = true }) {
  const { selectedId } = useProject();
  const { refresh: refreshUnread } = useNotifications();
  const [items, setItems] = useState(null);

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      params.set("unread", "true");
      params.set("limit", "50");
      const all = await api(`/notifications/?${params.toString()}`);
      const filtered = (Array.isArray(all) ? all : []).filter((n) => {
        if (!notificationTypes || notificationTypes.length === 0) return true;
        if (!notificationTypes.includes(n.notification_type)) return false;
        // Only show alerts for the current project OR project_id=null (global)
        if (n.project_id && selectedId && n.project_id !== selectedId) return false;
        return true;
      });
      setItems(filtered);
    } catch {
      setItems([]);
    }
  }, [selectedId, notificationTypes]);

  useEffect(() => { load(); }, [load]);

  if (items === null) return null;
  if (emptyHidden && items.length === 0) return null;

  async function handleDismiss(id) {
    try {
      await api(`/notifications/${id}/dismiss`, { method: "PATCH" });
      setItems((prev) => prev.filter((n) => n.id !== id));
      refreshUnread();
    } catch {}
  }

  async function handleOpen(notif) {
    if (!notif.read_at) {
      try {
        await api(`/notifications/${notif.id}/read`, { method: "PATCH" });
        refreshUnread();
      } catch {}
    }
    if (notif.action_path) {
      window.location.hash = notif.action_path.replace(/^\/?#?\/?/, "/");
    }
  }

  return (
    <div className="rex-card" style={{ marginBottom: 16, padding: "10px 14px", background: "var(--rex-accent-lighter)", borderLeft: "3px solid var(--rex-accent)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <span className="rex-h4" style={{ margin: 0, color: "var(--rex-accent-dark)" }}>{title}</span>
        <span className="rex-muted" style={{ fontSize: 11 }}>{items.length} unread</span>
      </div>
      {items.length === 0 ? (
        <div className="rex-muted" style={{ fontSize: 12 }}>No active alerts</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {items.slice(0, 5).map((n) => {
            const dot = severityDot(n.severity);
            return (
              <div
                key={n.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "6px 8px",
                  background: "var(--rex-bg-card)",
                  border: "1px solid var(--rex-border)",
                  borderLeft: `3px solid ${dot}`,
                  borderRadius: 4,
                  fontSize: 12,
                }}
              >
                <span className={`rex-badge ${severityColor(n.severity)}`} style={{ fontSize: 9, padding: "1px 5px" }}>{n.severity}</span>
                <span style={{ flex: 1, fontWeight: 600, color: "var(--rex-text-bold)" }}>{n.title}</span>
                {n.action_path && (
                  <button
                    onClick={() => handleOpen(n)}
                    className="rex-btn rex-btn-outline"
                    style={{ fontSize: 10, padding: "2px 8px" }}
                  >
                    Open
                  </button>
                )}
                <button
                  onClick={() => handleDismiss(n.id)}
                  className="rex-btn rex-btn-outline"
                  style={{ fontSize: 10, padding: "2px 8px" }}
                >
                  Dismiss
                </button>
              </div>
            );
          })}
          {items.length > 5 && (
            <a href="/#/notifications" className="rex-muted" style={{ fontSize: 11, marginTop: 4 }}>
              View {items.length - 5} more &rarr;
            </a>
          )}
        </div>
      )}
    </div>
  );
}
