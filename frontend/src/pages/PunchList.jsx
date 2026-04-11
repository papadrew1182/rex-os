import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";
const fmt = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function daysOpen(createdAt) {
  if (!createdAt) return null;
  return Math.max(0, Math.floor((Date.now() - new Date(createdAt).getTime()) / 86400000));
}

export default function PunchList() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null);
    api(`/punch-items?project_id=${selectedId}&limit=200`).then(setData).catch((e) => setError(e.message));
  }, [selectedId]);

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.punch_items || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q || (r.number || "").toString().toLowerCase().includes(q) || (r.title || r.description || "").toLowerCase().includes(q) || (r.location || "").toLowerCase().includes(q);
      const matchStatus = !statusFilter || r.status === statusFilter;
      const matchPriority = !priorityFilter || r.priority === priorityFilter;
      return matchSearch && matchStatus && matchPriority;
    });
  }, [items, search, statusFilter, priorityFilter]);

  const statuses = useMemo(() => [...new Set(items.map((r) => r.status).filter(Boolean))], [items]);
  const priorities = useMemo(() => [...new Set(items.map((r) => r.priority).filter(Boolean))], [items]);

  const summary = useMemo(() => {
    const open = items.filter((r) => r.status !== "closed" && r.status !== "complete");
    const closed = items.filter((r) => r.status === "closed" || r.status === "complete");
    const critical = items.filter((r) => r.priority === "critical" && r.status !== "closed");
    const daysArr = open.map((r) => daysOpen(r.created_at)).filter((d) => d != null);
    const avgDays = daysArr.length ? Math.round(daysArr.reduce((s, d) => s + d, 0) / daysArr.length) : 0;
    return { total: items.length, open: open.length, closed: closed.length, avgDays, critical: critical.length };
  }, [items]);

  function priorityColor(p) {
    if (p === "critical") return "rex-badge-red";
    if (p === "high") return "rex-badge-amber";
    if (p === "medium" || p === "normal") return "rex-badge-purple";
    return "rex-badge-gray";
  }

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading punch list..." />;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Punch List</h1>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Items" value={summary.total} />
        <StatCard label="Open" value={summary.open} color={summary.open > 0 ? "amber" : ""} />
        <StatCard label="Closed" value={summary.closed} color="green" />
        <StatCard label="Avg Days Open" value={summary.avgDays} sub="for open items" />
        <StatCard label="Critical Open" value={summary.critical} color={summary.critical > 0 ? "red" : ""} />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search # , title, or location..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 260 }}
        />
        <select className="rex-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: 150 }}>
          <option value="">All Statuses</option>
          {statuses.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <select className="rex-input" value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)} style={{ width: 150 }}>
          <option value="">All Priorities</option>
          {priorities.map((p) => <option key={p} value={p}>{p.replace(/_/g, " ")}</option>)}
        </select>
        <span className="rex-muted">{filtered.length} record{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">✅</div>No punch items found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Punch #</th>
                <th>Title</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Location</th>
                <th>Assigned To</th>
                <th style={{ textAlign: "right" }}>Days Open</th>
                <th>Due Date</th>
                <th style={{ textAlign: "right" }}>Cost Impact</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => {
                const days = daysOpen(row.created_at);
                const isOverdue = row.due_date && new Date(row.due_date) < new Date() && row.status !== "closed";
                return (
                  <tr key={row.id || i} onClick={() => setSelected(selected?.id === row.id ? null : row)}>
                    <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.number || "—"}</span></td>
                    <td>{row.title || row.description || "—"}</td>
                    <td><Badge status={row.status} /></td>
                    <td>{row.priority ? <span className={`rex-badge ${priorityColor(row.priority)}`}>{row.priority}</span> : "—"}</td>
                    <td>{row.location || "—"}</td>
                    <td>{row.assigned_to || row.assignee || "—"}</td>
                    <td style={{ textAlign: "right", color: days > 21 ? "var(--rex-red)" : "inherit" }}>{days ?? "—"}</td>
                    <td style={{ color: isOverdue ? "var(--rex-red)" : "inherit" }}>{fmtDate(row.due_date)}</td>
                    <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.cost_impact)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <div className="rex-detail-panel">
          <div className="rex-detail-panel-header">
            <div>
              <div className="rex-h3">Punch #{selected.number} — {selected.title || selected.description}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Badge status={selected.status} />
                {selected.priority && <span className={`rex-badge ${priorityColor(selected.priority)}`}>{selected.priority}</span>}
              </div>
            </div>
            <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>×</button>
          </div>
          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Details">
              <Row label="Location" value={selected.location || "—"} />
              <Row label="Assigned To" value={selected.assigned_to || selected.assignee || "—"} />
              <Row label="Trade" value={selected.trade || "—"} />
              <Row label="Cost Impact" value={fmt(selected.cost_impact)} />
            </Card>
            <Card title="Dates">
              <Row label="Created" value={fmtDate(selected.created_at)} />
              <Row label="Due Date" value={fmtDate(selected.due_date)} />
              <Row label="Completed" value={fmtDate(selected.completed_at)} />
              <Row label="Days Open" value={daysOpen(selected.created_at) ?? "—"} />
            </Card>
            <Card title="Resolution">
              <Row label="Inspector" value={selected.inspector || "—"} />
              <Row label="Inspection Date" value={fmtDate(selected.inspection_date)} />
              <Row label="Closed By" value={selected.closed_by || "—"} />
            </Card>
          </div>
          {selected.description && selected.description !== selected.title && (
            <Card title="Description">
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.description}</p>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
