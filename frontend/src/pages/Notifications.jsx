import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { StatCard, PageLoader, Flash } from "../ui";
import { useNotifications, severityColor, severityDot } from "../notifications";

const fmtDate = (d) => d ? new Date(d).toLocaleString() : "—";

export default function Notifications() {
  const { selectedId } = useProject();
  const { refresh: refreshUnread } = useNotifications();
  const [items, setItems] = useState(null);
  const [error, setError] = useState(null);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [domainFilter, setDomainFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [scopeFilter, setScopeFilter] = useState("all"); // all | current_project

  const refresh = useCallback(async () => {
    setItems(null); setError(null);
    const params = new URLSearchParams();
    if (unreadOnly) params.set("unread", "true");
    if (domainFilter) params.set("domain", domainFilter);
    if (severityFilter) params.set("severity", severityFilter);
    if (scopeFilter === "current_project" && selectedId) params.set("project_id", selectedId);
    params.set("limit", "200");
    try {
      const list = await api(`/notifications/?${params.toString()}`);
      setItems(Array.isArray(list) ? list : []);
    } catch (e) {
      setError(e.message);
    }
  }, [unreadOnly, domainFilter, severityFilter, scopeFilter, selectedId]);

  useEffect(() => { refresh(); }, [refresh]);

  const summary = useMemo(() => {
    if (!items) return { total: 0, unread: 0, critical: 0, warning: 0 };
    return {
      total: items.length,
      unread: items.filter((n) => !n.read_at).length,
      critical: items.filter((n) => n.severity === "critical").length,
      warning: items.filter((n) => n.severity === "warning").length,
    };
  }, [items]);

  async function handleRead(id) {
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
      refresh();
      refreshUnread();
    } catch {}
  }

  if (error) return <Flash type="error" message={error} />;
  if (items === null) return <PageLoader text="Loading notifications..." />;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <h1 className="rex-h1">Notifications</h1>
        <button className="rex-btn rex-btn-outline" onClick={handleReadAll}>Mark all read</button>
      </div>
      <p className="rex-muted" style={{ marginBottom: 20 }}>In-app inbox for all alerts and updates.</p>

      <div className="rex-grid-4" style={{ marginBottom: 20 }}>
        <StatCard label="Total" value={summary.total} />
        <StatCard label="Unread" value={summary.unread} color={summary.unread > 0 ? "amber" : ""} />
        <StatCard label="Critical" value={summary.critical} color={summary.critical > 0 ? "red" : ""} />
        <StatCard label="Warning" value={summary.warning} color={summary.warning > 0 ? "amber" : ""} />
      </div>

      <div className="rex-search-bar">
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--rex-text)" }}>
          <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} style={{ cursor: "pointer" }} />
          Unread only
        </label>
        <select className="rex-input" value={domainFilter} onChange={(e) => setDomainFilter(e.target.value)} style={{ width: 170 }}>
          <option value="">All domains</option>
          <option value="schedule">Schedule</option>
          <option value="financials">Financials</option>
          <option value="field_ops">Field Ops</option>
          <option value="document_management">Documents</option>
          <option value="closeout">Closeout</option>
          <option value="foundation">Foundation</option>
          <option value="system">System</option>
        </select>
        <select className="rex-input" value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)} style={{ width: 150 }}>
          <option value="">All severities</option>
          <option value="critical">Critical</option>
          <option value="warning">Warning</option>
          <option value="info">Info</option>
          <option value="success">Success</option>
        </select>
        <select className="rex-input" value={scopeFilter} onChange={(e) => setScopeFilter(e.target.value)} style={{ width: 180 }}>
          <option value="all">All projects</option>
          <option value="current_project">Current project only</option>
        </select>
        <span className="rex-muted">{items.length} record{items.length !== 1 ? "s" : ""}</span>
      </div>

      {items.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No notifications</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {items.map((n) => {
            const unread = !n.read_at;
            const dot = severityDot(n.severity);
            return (
              <div
                key={n.id}
                style={{
                  background: unread ? "var(--rex-accent-light)" : "var(--rex-bg-card)",
                  border: "1px solid var(--rex-border)",
                  borderLeft: `4px solid ${dot}`,
                  borderRadius: 6,
                  padding: "12px 14px",
                  display: "flex",
                  gap: 12,
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
                    <span className={`rex-badge ${severityColor(n.severity)}`} style={{ fontSize: 10, padding: "1px 6px" }}>{n.severity}</span>
                    <span className="rex-badge rex-badge-gray" style={{ fontSize: 10, padding: "1px 6px" }}>{n.domain}</span>
                    {unread && <span className="rex-badge rex-badge-purple" style={{ fontSize: 10, padding: "1px 6px" }}>NEW</span>}
                    <span className="rex-muted" style={{ fontSize: 11, marginLeft: "auto" }}>{fmtDate(n.created_at)}</span>
                  </div>
                  <div style={{ fontSize: 14, fontWeight: unread ? 700 : 500, color: "var(--rex-text-bold)" }}>{n.title}</div>
                  {n.body && <div className="rex-muted" style={{ fontSize: 13, marginTop: 4 }}>{n.body}</div>}
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6, justifyContent: "center" }}>
                  {n.action_path && (
                    <a href={n.action_path} onClick={() => handleRead(n.id)} className="rex-btn rex-btn-primary" style={{ fontSize: 11, padding: "4px 10px" }}>Open</a>
                  )}
                  {unread && (
                    <button onClick={() => handleRead(n.id)} className="rex-btn rex-btn-outline" style={{ fontSize: 11, padding: "4px 10px" }}>Read</button>
                  )}
                  <button onClick={() => handleDismiss(n.id)} className="rex-btn rex-btn-outline" style={{ fontSize: 11, padding: "4px 10px" }}>Dismiss</button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
