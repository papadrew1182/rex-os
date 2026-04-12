import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

function severityBadge(s) {
  if (s === "critical") return <span className="rex-badge rex-badge-red">{s}</span>;
  if (s === "serious") return <span className="rex-badge rex-badge-red">{s}</span>;
  if (s === "moderate") return <span className="rex-badge rex-badge-amber">{s}</span>;
  if (s === "minor") return <span className="rex-badge rex-badge-gray">{s}</span>;
  return s ? <span className="rex-badge rex-badge-gray">{s}</span> : "—";
}

export default function SafetyIncidents() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [oshaOnly, setOshaOnly] = useState(false);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null);
    api(`/safety-incidents?project_id=${selectedId}&limit=200`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [selectedId]);

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.safety_incidents || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q
        || (r.title || "").toLowerCase().includes(q)
        || (r.description || "").toLowerCase().includes(q)
        || (r.incident_number || "").toLowerCase().includes(q);
      const matchType = !typeFilter || r.incident_type === typeFilter;
      const matchSeverity = !severityFilter || r.severity === severityFilter;
      const matchStatus = !statusFilter || r.status === statusFilter;
      const matchOsha = !oshaOnly || r.is_osha_recordable === true;
      return matchSearch && matchType && matchSeverity && matchStatus && matchOsha;
    });
  }, [items, search, typeFilter, severityFilter, statusFilter, oshaOnly]);

  const types = useMemo(() => [...new Set(items.map((r) => r.incident_type).filter(Boolean))].sort(), [items]);
  const severities = useMemo(() => [...new Set(items.map((r) => r.severity).filter(Boolean))].sort(), [items]);
  const statuses = useMemo(() => [...new Set(items.map((r) => r.status).filter(Boolean))].sort(), [items]);

  const summary = useMemo(() => {
    const openItems = items.filter((r) => r.status !== "closed").length;
    const oshaRecordable = items.filter((r) => r.is_osha_recordable === true).length;
    const severeCritical = items.filter((r) => r.severity === "serious" || r.severity === "critical").length;
    const lostTimeDays = items.reduce((s, r) => s + (r.lost_time_days || 0), 0);
    return { total: items.length, openItems, oshaRecordable, severeCritical, lostTimeDays };
  }, [items]);

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading safety incidents..." />;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Safety Incidents</h1>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Incidents" value={summary.total} />
        <StatCard label="Open" value={summary.openItems} color={summary.openItems > 0 ? "amber" : ""} />
        <StatCard label="OSHA Recordable" value={summary.oshaRecordable} color={summary.oshaRecordable > 0 ? "red" : ""} />
        <StatCard label="Serious / Critical" value={summary.severeCritical} color={summary.severeCritical > 0 ? "red" : ""} />
        <StatCard label="Lost Time Days" value={summary.lostTimeDays} color={summary.lostTimeDays > 0 ? "red" : ""} />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search title, description, or number..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 280 }}
        />
        <select className="rex-input" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} style={{ width: 160 }}>
          <option value="">All Types</option>
          {types.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
        </select>
        <select className="rex-input" value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)} style={{ width: 150 }}>
          <option value="">All Severities</option>
          {severities.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <select className="rex-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: 150 }}>
          <option value="">All Statuses</option>
          {statuses.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: "pointer", color: "var(--rex-text-muted)" }}>
          <input
            type="checkbox"
            checked={oshaOnly}
            onChange={(e) => setOshaOnly(e.target.checked)}
          />
          OSHA Only
        </label>
        <span className="rex-muted">{filtered.length} record{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No safety incidents found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Incident #</th>
                <th>Title</th>
                <th>Date</th>
                <th>Type</th>
                <th>Severity</th>
                <th>Status</th>
                <th>OSHA</th>
                <th style={{ textAlign: "right" }}>Lost Days</th>
                <th>Reported By</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr
                  key={row.id || i}
                  onClick={() => setSelected(selected?.id === row.id ? null : row)}
                  style={row.is_osha_recordable ? { background: "var(--rex-red-bg)" } : undefined}
                >
                  <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.incident_number || "—"}</span></td>
                  <td>{row.title || "—"}</td>
                  <td>{fmtDate(row.incident_date)}</td>
                  <td>
                    {row.incident_type
                      ? <span className="rex-badge rex-badge-gray">{row.incident_type.replace(/_/g, " ")}</span>
                      : "—"}
                  </td>
                  <td>{severityBadge(row.severity)}</td>
                  <td><Badge status={row.status} /></td>
                  <td>
                    {row.is_osha_recordable
                      ? <span className="rex-badge rex-badge-red">OSHA</span>
                      : <span className="rex-badge rex-badge-gray">—</span>}
                  </td>
                  <td style={{ textAlign: "right", color: row.lost_time_days > 0 ? "var(--rex-red)" : "inherit" }}>
                    {row.lost_time_days ?? "—"}
                  </td>
                  <td>
                    {row.reported_by
                      ? <span style={{ fontFamily: "monospace", fontSize: 11 }}>{row.reported_by.slice(0, 8)}…</span>
                      : "—"}
                  </td>
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
              <div className="rex-h3">#{selected.incident_number} — {selected.title}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Badge status={selected.status} />
                {severityBadge(selected.severity)}
                {selected.is_osha_recordable && <span className="rex-badge rex-badge-red">OSHA RECORDABLE</span>}
              </div>
            </div>
            <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>×</button>
          </div>

          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Incident Info">
              <Row label="Number" value={selected.incident_number || "—"} />
              <Row label="Title" value={selected.title || "—"} />
              <Row label="Date" value={fmtDate(selected.incident_date)} />
              <Row label="Time" value={selected.incident_time || "—"} />
              <Row label="Location" value={selected.location || "—"} />
            </Card>
            <Card title="Classification">
              <Row label="Type" value={selected.incident_type?.replace(/_/g, " ") || "—"} />
              <Row label="Severity" value={severityBadge(selected.severity)} />
              <Row label="Status" value={<Badge status={selected.status} />} />
              <Row label="OSHA Recordable" value={
                selected.is_osha_recordable
                  ? <span className="rex-badge rex-badge-red">Yes</span>
                  : <span className="rex-badge rex-badge-gray">No</span>
              } />
            </Card>
            <Card title="Affected">
              <Row label="Affected Person" value={selected.affected_person_id || "—"} />
              <Row label="Affected Company" value={selected.affected_company_id || "—"} />
              <Row label="Reported By" value={selected.reported_by || "—"} />
            </Card>
          </div>

          <div className="rex-grid-2" style={{ marginBottom: 14 }}>
            <Card title="Impact">
              <Row label="Lost Time Days" value={
                selected.lost_time_days != null
                  ? <span style={{ color: selected.lost_time_days > 0 ? "var(--rex-red)" : "inherit" }}>
                      {selected.lost_time_days}
                    </span>
                  : "—"
              } />
              <Row label="Severity" value={severityBadge(selected.severity)} />
            </Card>
          </div>

          {selected.description && (
            <Card title="Description" style={{ marginBottom: 12 }}>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.description}</p>
            </Card>
          )}

          {selected.root_cause && (
            <Card title="Root Cause" style={{ marginBottom: 12 }}>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.root_cause}</p>
            </Card>
          )}

          {selected.corrective_action && (
            <Card title="Corrective Action" style={{ marginBottom: 12 }}>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.corrective_action}</p>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
