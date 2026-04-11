import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";
const fmt = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function daysOpen(createdAt) {
  if (!createdAt) return null;
  const ms = Date.now() - new Date(createdAt).getTime();
  return Math.max(0, Math.floor(ms / 86400000));
}

export default function RfiManagement() {
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
    api(`/rfis?project_id=${selectedId}&limit=200`).then(setData).catch((e) => setError(e.message));
  }, [selectedId]);

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.rfis || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q || (r.number || "").toString().toLowerCase().includes(q) || (r.subject || r.title || "").toLowerCase().includes(q);
      const matchStatus = !statusFilter || r.status === statusFilter;
      const matchPriority = !priorityFilter || r.priority === priorityFilter;
      return matchSearch && matchStatus && matchPriority;
    });
  }, [items, search, statusFilter, priorityFilter]);

  const statuses = useMemo(() => [...new Set(items.map((r) => r.status).filter(Boolean))], [items]);
  const priorities = useMemo(() => [...new Set(items.map((r) => r.priority).filter(Boolean))], [items]);

  const summary = useMemo(() => {
    const open = items.filter((r) => r.status === "open" || r.status === "in_progress");
    const today = new Date();
    const overdue = items.filter((r) => {
      if (r.status === "closed" || r.status === "complete") return false;
      if (!r.due_date) return false;
      return new Date(r.due_date) < today;
    });
    const daysArr = open.map((r) => daysOpen(r.created_at)).filter((d) => d != null);
    const avgDays = daysArr.length ? Math.round(daysArr.reduce((s, d) => s + d, 0) / daysArr.length) : 0;
    return { total: items.length, open: open.length, overdue: overdue.length, avgDays };
  }, [items]);

  function priorityColor(p) {
    if (p === "critical" || p === "high") return "rex-badge-red";
    if (p === "medium" || p === "normal") return "rex-badge-amber";
    return "rex-badge-gray";
  }

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading RFIs..." />;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>RFI Management</h1>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-4" style={{ marginBottom: 24 }}>
        <StatCard label="Total RFIs" value={summary.total} />
        <StatCard label="Open" value={summary.open} color={summary.open > 0 ? "amber" : ""} />
        <StatCard label="Overdue" value={summary.overdue} color={summary.overdue > 0 ? "red" : ""} />
        <StatCard label="Avg Days Open" value={summary.avgDays} sub="for open RFIs" />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search RFI # or subject..."
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
        <div className="rex-empty"><div className="rex-empty-icon">❓</div>No RFIs found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>RFI #</th>
                <th>Subject</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Assigned To</th>
                <th>Ball in Court</th>
                <th style={{ textAlign: "right" }}>Days Open</th>
                <th>Due Date</th>
                <th>Cost Impact</th>
                <th>Sched Impact</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => {
                const days = daysOpen(row.created_at);
                const isOverdue = row.due_date && new Date(row.due_date) < new Date() && row.status !== "closed";
                return (
                  <tr key={row.id || i} onClick={() => setSelected(selected?.id === row.id ? null : row)}>
                    <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.number || "—"}</span></td>
                    <td>{row.subject || row.title || "—"}</td>
                    <td><Badge status={row.status} /></td>
                    <td>{row.priority ? <span className={`rex-badge ${priorityColor(row.priority)}`}>{row.priority}</span> : "—"}</td>
                    <td>{row.assigned_to || row.assignee || "—"}</td>
                    <td>{row.ball_in_court || "—"}</td>
                    <td style={{ textAlign: "right", color: days > 14 ? "var(--rex-red)" : "inherit" }}>{days ?? "—"}</td>
                    <td style={{ color: isOverdue ? "var(--rex-red)" : "inherit" }}>{fmtDate(row.due_date)}</td>
                    <td>{row.cost_impact != null ? <span className="rex-badge rex-badge-amber">YES</span> : <span className="rex-badge rex-badge-gray">NO</span>}</td>
                    <td>{row.schedule_impact != null ? <span className="rex-badge rex-badge-amber">YES</span> : <span className="rex-badge rex-badge-gray">NO</span>}</td>
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
              <div className="rex-h3">RFI #{selected.number} — {selected.subject || selected.title}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Badge status={selected.status} />
                {selected.priority && <span className={`rex-badge ${priorityColor(selected.priority)}`}>{selected.priority}</span>}
              </div>
            </div>
            <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>×</button>
          </div>
          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Details">
              <Row label="Assigned To" value={selected.assigned_to || selected.assignee || "—"} />
              <Row label="Ball in Court" value={selected.ball_in_court || "—"} />
              <Row label="Due Date" value={fmtDate(selected.due_date)} />
              <Row label="Days Open" value={daysOpen(selected.created_at) ?? "—"} />
            </Card>
            <Card title="Impact">
              <Row label="Cost Impact" value={selected.cost_impact != null ? fmt(selected.cost_impact) : "None"} />
              <Row label="Schedule Impact" value={selected.schedule_impact != null ? `${selected.schedule_impact} days` : "None"} />
            </Card>
            <Card title="Dates">
              <Row label="Created" value={fmtDate(selected.created_at)} />
              <Row label="Submitted" value={fmtDate(selected.submitted_at)} />
              <Row label="Answered" value={fmtDate(selected.answered_at)} />
              <Row label="Closed" value={fmtDate(selected.closed_at)} />
            </Card>
          </div>
          {selected.question && (
            <Card title="Question" style={{ marginBottom: 12 }}>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.question}</p>
            </Card>
          )}
          {selected.answer && (
            <Card title="Answer">
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.answer}</p>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
