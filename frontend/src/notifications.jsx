/**
 * Notification context + UI primitives.
 *
 * Provides:
 *   - NotificationProvider — wraps the app, polls /unread-count every 60s
 *   - useNotifications() — returns { unreadCount, refresh }
 *   - NotificationBell — topbar bell with badge that opens the drawer
 *   - severityColor(severity) — maps to badge css class
 *   - severityDot(severity) — maps to CSS color var
 */

import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { Link } from "react-router-dom";
import { api } from "./api";
import { useAuth } from "./auth";
import { Spinner } from "./ui";

const NotificationCtx = createContext(null);

const POLL_INTERVAL_MS = 60_000;

export function NotificationProvider({ children }) {
  const { user } = useAuth();
  const [unreadCount, setUnreadCount] = useState(0);
  const intervalRef = useRef(null);

  const refresh = useCallback(async () => {
    if (!user) return;
    try {
      const r = await api("/notifications/unread-count");
      setUnreadCount(r.unread_count || 0);
    } catch {}
  }, [user]);

  useEffect(() => {
    if (!user) {
      setUnreadCount(0);
      return;
    }
    refresh();
    intervalRef.current = setInterval(refresh, POLL_INTERVAL_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [user, refresh]);

  return (
    <NotificationCtx.Provider value={{ unreadCount, refresh }}>
      {children}
    </NotificationCtx.Provider>
  );
}

export function useNotifications() {
  return useContext(NotificationCtx) || { unreadCount: 0, refresh: () => {} };
}

export function severityColor(severity) {
  switch (severity) {
    case "critical": return "rex-badge-red";
    case "warning":  return "rex-badge-amber";
    case "success":  return "rex-badge-green";
    case "info":
    default:         return "rex-badge-purple";
  }
}

export function severityDot(severity) {
  switch (severity) {
    case "critical": return "var(--rex-red)";
    case "warning":  return "var(--rex-amber)";
    case "success":  return "var(--rex-green)";
    default:         return "var(--rex-accent)";
  }
}

const fmtRelative = (iso) => {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
};

/**
 * NotificationBell — topbar bell button that opens the drawer.
 */
export function NotificationBell() {
  const { user } = useAuth();
  const { unreadCount, refresh } = useNotifications();
  const [open, setOpen] = useState(false);

  if (!user) return null;

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="rex-bell"
        title={unreadCount > 0 ? `${unreadCount} unread notification${unreadCount !== 1 ? "s" : ""}` : "No new notifications"}
        style={{
          background: "none",
          border: "none",
          cursor: "pointer",
          position: "relative",
          padding: "6px 10px",
          color: "var(--rex-text)",
          fontSize: 18,
          lineHeight: 1,
        }}
      >
        <span aria-hidden="true">🔔</span>
        {unreadCount > 0 && (
          <span style={{
            position: "absolute",
            top: 0,
            right: 0,
            background: "var(--rex-red)",
            color: "#fff",
            fontSize: 10,
            fontWeight: 700,
            borderRadius: 8,
            minWidth: 16,
            height: 16,
            display: "inline-flex",
            alignItems: "center",
            justifyContent: "center",
            padding: "0 4px",
          }}>{unreadCount > 99 ? "99+" : unreadCount}</span>
        )}
      </button>
      {open && <NotificationDrawer onClose={() => { setOpen(false); refresh(); }} />}
    </>
  );
}

function NotificationDrawer({ onClose }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const { refresh: refreshUnread } = useNotifications();

  const load = useCallback(async () => {
    setItems(null); setError(null);
    try {
      const list = await api("/notifications/?limit=20");
      setItems(Array.isArray(list) ? list : []);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // ESC to close
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function handleMarkRead(id) {
    try {
      await api(`/notifications/${id}/read`, { method: "PATCH" });
      setItems((prev) => prev.map((n) => n.id === id ? { ...n, read_at: new Date().toISOString() } : n));
      refreshUnread();
    } catch {}
  }

  async function handleDismiss(id) {
    try {
      await api(`/notifications/${id}/dismiss`, { method: "PATCH" });
      setItems((prev) => prev.filter((n) => n.id !== id));
      refreshUnread();
    } catch {}
  }

  async function handleReadAll() {
    try {
      await api(`/notifications/read-all`, { method: "PATCH" });
      setItems((prev) => prev.map((n) => ({ ...n, read_at: n.read_at || new Date().toISOString() })));
      refreshUnread();
    } catch {}
  }

  return (
    <div className="rex-drawer-overlay" onClick={onClose}>
      <div className="rex-drawer" onClick={(e) => e.stopPropagation()} style={{ width: 440, display: "flex", flexDirection: "column" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12, paddingBottom: 12, borderBottom: "1px solid var(--rex-border)" }}>
          <div>
            <div className="rex-h3">Notifications</div>
            <div className="rex-muted" style={{ fontSize: 12, marginTop: 2 }}>Most recent</div>
          </div>
          <button className="rex-detail-panel-close" onClick={onClose}>×</button>
        </div>

        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <button className="rex-btn rex-btn-outline" onClick={handleReadAll} style={{ fontSize: 12 }}>Mark all read</button>
          <Link to="/notifications" onClick={onClose} className="rex-btn rex-btn-outline" style={{ fontSize: 12 }}>View all</Link>
        </div>

        {items === null && !error && (
          <div style={{ textAlign: "center", padding: 32 }}><Spinner size={20} /></div>
        )}
        {error && (
          <div className="rex-empty"><div className="rex-empty-icon">!</div>{error}</div>
        )}
        {items && items.length === 0 && (
          <div className="rex-empty"><div className="rex-empty-icon">○</div>No notifications</div>
        )}

        {items && items.length > 0 && (
          <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
            {items.map((n) => {
              const unread = !n.read_at;
              const dot = severityDot(n.severity);
              return (
                <div
                  key={n.id}
                  style={{
                    background: unread ? "var(--rex-accent-light)" : "var(--rex-bg-card)",
                    border: "1px solid var(--rex-border)",
                    borderLeft: `3px solid ${dot}`,
                    borderRadius: 6,
                    padding: 10,
                    fontSize: 13,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: unread ? 700 : 500, color: "var(--rex-text-bold)" }}>{n.title}</div>
                      {n.body && <div className="rex-muted" style={{ fontSize: 12, marginTop: 2 }}>{n.body}</div>}
                      <div className="rex-muted" style={{ fontSize: 11, marginTop: 4, display: "flex", gap: 6, alignItems: "center" }}>
                        <span className={`rex-badge ${severityColor(n.severity)}`} style={{ fontSize: 9, padding: "1px 5px" }}>{n.severity}</span>
                        <span>{fmtRelative(n.created_at)}</span>
                      </div>
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                    {n.action_path && (
                      <a
                        href={n.action_path}
                        onClick={() => { handleMarkRead(n.id); onClose(); }}
                        className="rex-btn rex-btn-outline"
                        style={{ fontSize: 11, padding: "3px 8px" }}
                      >Open</a>
                    )}
                    {unread && (
                      <button onClick={() => handleMarkRead(n.id)} className="rex-btn rex-btn-outline" style={{ fontSize: 11, padding: "3px 8px" }}>Mark read</button>
                    )}
                    <button onClick={() => handleDismiss(n.id)} className="rex-btn rex-btn-outline" style={{ fontSize: 11, padding: "3px 8px" }}>Dismiss</button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
