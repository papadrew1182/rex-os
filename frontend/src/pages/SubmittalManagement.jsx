import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

function isOverdue(row) {
  if (row.status === "approved" || row.status === "closed" || row.status === "complete") return false;
  if (!row.due_date) return false;
  return new Date(row.due_date) < new Date();
}

export default function SubmittalManagement() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null);
    api(`/submittals?project_id=${selectedId}&limit=200`).then(setData).catch((e) => setError(e.message));
  }, [selectedId]);

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.submittals || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q || (r.number || "").toString().toLowerCase().includes(q) || (r.title || "").toLowerCase().includes(q) || (r.spec_section || "").toLowerCase().includes(q);
      const matchStatus = !statusFilter || r.status === statusFilter;
      const matchType = !typeFilter || r.submittal_type === typeFilter;
      return matchSearch && matchStatus && matchType;
    });
  }, [items, search, statusFilter, typeFilter]);

  const statuses = useMemo(() => [...new Set(items.map((r) => r.status).filter(Boolean))], [items]);
  const types = useMemo(() => [...new Set(items.map((r) => r.submittal_type).filter(Boolean))], [items]);

  const summary = useMemo(() => {
    const open = items.filter((r) => r.status !== "approved" && r.status !== "closed" && r.status !== "complete").length;
    const overdue = items.filter(isOverdue).length;
    const approved = items.filter((r) => r.status === "approved").length;
    return { total: items.length, open, overdue, approved };
  }, [items]);

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading submittals..." />;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Submittals</h1>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-4" style={{ marginBottom: 24 }}>
        <StatCard label="Total" value={summary.total} />
        <StatCard label="Open" value={summary.open} color={summary.open > 0 ? "amber" : ""} />
        <StatCard label="Overdue" value={summary.overdue} color={summary.overdue > 0 ? "red" : ""} />
        <StatCard label="Approved" value={summary.approved} color="green" />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search #, title, spec section..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 280 }}
        />
        <select className="rex-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: 160 }}>
          <option value="">All Statuses</option>
          {statuses.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <select className="rex-input" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} style={{ width: 160 }}>
          <option value="">All Types</option>
          {types.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
        </select>
        <span className="rex-muted">{filtered.length} record{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">📂</div>No submittals found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Submittal #</th>
                <th>Title</th>
                <th>Status</th>
                <th>Type</th>
                <th>Spec Section</th>
                <th>Ball in Court</th>
                <th>Due Date</th>
                <th style={{ textAlign: "right" }}>Lead Time</th>
                <th>Required On Site</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr key={row.id || i} onClick={() => setSelected(selected?.id === row.id ? null : row)}>
                  <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.number || "—"}</span></td>
                  <td>{row.title || "—"}</td>
                  <td><Badge status={row.status} /></td>
                  <td><span className="rex-muted" style={{ fontSize: 12 }}>{row.submittal_type || "—"}</span></td>
                  <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.spec_section || "—"}</span></td>
                  <td>{row.ball_in_court || "—"}</td>
                  <td style={{ color: isOverdue(row) ? "var(--rex-red)" : "inherit" }}>{fmtDate(row.due_date)}</td>
                  <td style={{ textAlign: "right" }}>{row.lead_time_days != null ? `${row.lead_time_days}d` : "—"}</td>
                  <td>{fmtDate(row.required_on_site_date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <div className="rex-detail-panel">
          <div className="rex-detail-panel-header">
            <div>
              <div className="rex-h3">Submittal #{selected.number} — {selected.title}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Badge status={selected.status} />
                {selected.submittal_type && <span className="rex-badge rex-badge-gray">{selected.submittal_type.replace(/_/g, " ")}</span>}
              </div>
            </div>
            <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>×</button>
          </div>
          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Details">
              <Row label="Spec Section" value={selected.spec_section || "—"} />
              <Row label="Type" value={selected.submittal_type || "—"} />
              <Row label="Revision" value={selected.revision || "—"} />
              <Row label="Ball in Court" value={selected.ball_in_court || "—"} />
            </Card>
            <Card title="Dates">
              <Row label="Created" value={fmtDate(selected.created_at)} />
              <Row label="Submitted" value={fmtDate(selected.submitted_at)} />
              <Row label="Due Date" value={fmtDate(selected.due_date)} />
              <Row label="Approved Date" value={fmtDate(selected.approved_at)} />
            </Card>
            <Card title="Procurement">
              <Row label="Lead Time" value={selected.lead_time_days != null ? `${selected.lead_time_days} days` : "—"} />
              <Row label="Required On Site" value={fmtDate(selected.required_on_site_date)} />
              <Row label="Submitted By" value={selected.submitted_by || "—"} />
              <Row label="Reviewed By" value={selected.reviewed_by || "—"} />
            </Card>
          </div>
          {selected.description && (
            <Card title="Description">
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.description}</p>
            </Card>
          )}
          {selected.review_notes && (
            <Card title="Review Notes" style={{ marginTop: 12 }}>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.review_notes}</p>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
