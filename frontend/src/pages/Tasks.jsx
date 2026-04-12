import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

function priorityBadge(p) {
  if (p === "high") return <span className="rex-badge rex-badge-red">{p}</span>;
  if (p === "medium") return <span className="rex-badge rex-badge-amber">{p}</span>;
  if (p === "low") return <span className="rex-badge rex-badge-gray">{p}</span>;
  return p ? <span className="rex-badge rex-badge-gray">{p}</span> : "—";
}

export default function Tasks() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null);
    api(`/tasks?project_id=${selectedId}&limit=200`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [selectedId]);

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.tasks || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q
        || (r.title || "").toLowerCase().includes(q)
        || (r.description || "").toLowerCase().includes(q);
      const matchStatus = !statusFilter || r.status === statusFilter;
      const matchPriority = !priorityFilter || r.priority === priorityFilter;
      const matchCategory = !categoryFilter || r.category === categoryFilter;
      return matchSearch && matchStatus && matchPriority && matchCategory;
    });
  }, [items, search, statusFilter, priorityFilter, categoryFilter]);

  const statuses = useMemo(() => [...new Set(items.map((r) => r.status).filter(Boolean))], [items]);
  const priorities = useMemo(() => [...new Set(items.map((r) => r.priority).filter(Boolean))], [items]);
  const categories = useMemo(() => [...new Set(items.map((r) => r.category).filter(Boolean))], [items]);

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const summary = useMemo(() => {
    const openItems = items.filter((r) => r.status === "open" || r.status === "in_progress");
    const overdue = openItems.filter((r) => r.due_date && new Date(r.due_date) < today).length;
    const completed = items.filter((r) => r.status === "complete").length;
    const highPriority = items.filter((r) => r.priority === "high" && r.status !== "complete" && r.status !== "void").length;
    return { total: items.length, open: openItems.length, overdue, completed, highPriority };
  }, [items]);

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading tasks..." />;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Tasks &amp; Actions</h1>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Tasks" value={summary.total} />
        <StatCard label="Open" value={summary.open} color={summary.open > 0 ? "amber" : ""} />
        <StatCard label="Overdue" value={summary.overdue} color={summary.overdue > 0 ? "red" : ""} />
        <StatCard label="Completed" value={summary.completed} color="green" />
        <StatCard label="High Priority" value={summary.highPriority} color={summary.highPriority > 0 ? "red" : ""} />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search title or description..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 260 }}
        />
        <select className="rex-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: 150 }}>
          <option value="">All Statuses</option>
          {statuses.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <select className="rex-input" value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)} style={{ width: 140 }}>
          <option value="">All Priorities</option>
          {priorities.map((p) => <option key={p} value={p}>{p.replace(/_/g, " ")}</option>)}
        </select>
        <select className="rex-input" value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} style={{ width: 150 }}>
          <option value="">All Categories</option>
          {categories.map((c) => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
        </select>
        <span className="rex-muted">{filtered.length} record{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No tasks found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Task #</th>
                <th>Title</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Category</th>
                <th>Assigned To</th>
                <th>Due Date</th>
                <th>Completed</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => {
                const isOpen = row.status === "open" || row.status === "in_progress";
                const isOverdue = isOpen && row.due_date && new Date(row.due_date) < today;
                return (
                  <tr key={row.id || i} onClick={() => setSelected(selected?.id === row.id ? null : row)}>
                    <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.task_number || "—"}</span></td>
                    <td>{row.title || "—"}</td>
                    <td><Badge status={row.status} /></td>
                    <td>{priorityBadge(row.priority)}</td>
                    <td>{row.category ? <span className="rex-badge rex-badge-gray">{row.category.replace(/_/g, " ")}</span> : "—"}</td>
                    <td>{row.assigned_to ? <span style={{ fontFamily: "monospace", fontSize: 11 }}>{row.assigned_to.slice(0, 8)}…</span> : "—"}</td>
                    <td style={{ color: isOverdue ? "var(--rex-red)" : "inherit" }}>{fmtDate(row.due_date)}</td>
                    <td>{fmtDate(row.completed_date)}</td>
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
              <div className="rex-h3">Task #{selected.task_number} — {selected.title}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Badge status={selected.status} />
                {priorityBadge(selected.priority)}
              </div>
            </div>
            <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>×</button>
          </div>
          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Task Info">
              <Row label="Task #" value={selected.task_number || "—"} />
              <Row label="Title" value={selected.title || "—"} />
              <Row label="Status" value={<Badge status={selected.status} />} />
              <Row label="Priority" value={priorityBadge(selected.priority)} />
              <Row label="Category" value={selected.category?.replace(/_/g, " ") || "—"} />
            </Card>
            <Card title="Assignment">
              <Row label="Assigned To" value={selected.assigned_to || "—"} />
              <Row label="Company" value={selected.assigned_company_id || "—"} />
              <Row label="Created By" value={selected.created_by || "—"} />
            </Card>
            <Card title="Dates">
              <Row label="Created" value={selected.created_at ? new Date(selected.created_at).toLocaleDateString() : "—"} />
              <Row label="Due Date" value={fmtDate(selected.due_date)} />
              <Row label="Completed" value={fmtDate(selected.completed_date)} />
            </Card>
          </div>
          {selected.description && (
            <Card title="Description">
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.description}</p>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
