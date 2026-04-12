import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";
import { FormDrawer, useFormState, Field, NumberField, DateField, TimeField, TextArea, Select, Checkbox, WriteButton, cleanPayload } from "../forms";
import { usePermissions } from "../permissions";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

function severityBadge(s) {
  if (s === "critical") return <span className="rex-badge rex-badge-red">{s}</span>;
  if (s === "serious") return <span className="rex-badge rex-badge-red">{s}</span>;
  if (s === "moderate") return <span className="rex-badge rex-badge-amber">{s}</span>;
  if (s === "minor") return <span className="rex-badge rex-badge-gray">{s}</span>;
  return s ? <span className="rex-badge rex-badge-gray">{s}</span> : "—";
}

const INCIDENT_TYPES = ["near_miss", "first_aid", "recordable", "lost_time", "property_damage", "environmental"];
const SEVERITIES = ["minor", "moderate", "serious", "critical"];
const STATUSES = ["open", "under_investigation", "corrective_action", "closed"];

export default function SafetyIncidents() {
  const { selected: project, selectedId } = useProject();
  const { canWrite } = usePermissions();

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [severityFilter, setSeverityFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [oshaOnly, setOshaOnly] = useState(false);
  const [selected, setSelected] = useState(null);
  const [people, setPeople] = useState([]);
  const [companies, setCompanies] = useState([]);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState("create");
  const [editing, setEditing] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const form = useFormState({});

  const refresh = useCallback(() => {
    if (!selectedId) return;
    api(`/safety-incidents?project_id=${selectedId}&limit=200`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null);
    refresh();
  }, [selectedId, refresh]);

  useEffect(() => {
    if (!selectedId) return;
    Promise.all([
      api(`/people?limit=500`).catch(() => []),
      api(`/companies?limit=500`).catch(() => []),
    ]).then(([p, c]) => {
      setPeople(Array.isArray(p) ? p : []);
      setCompanies(Array.isArray(c) ? c : []);
    });
  }, [selectedId]);

  const peopleOptions = useMemo(() => people.map((p) => ({ value: p.id, label: `${p.first_name} ${p.last_name}` })), [people]);
  const companyOptions = useMemo(() => companies.map((c) => ({ value: c.id, label: c.name })), [companies]);

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

  function openCreate() {
    setDrawerMode("create");
    setEditing(null);
    form.setAll({ status: "open", severity: "minor", is_osha_recordable: false });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  function openEdit(row) {
    setDrawerMode("edit");
    setEditing(row);
    form.setAll({ ...row });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  async function onSubmit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const payload = cleanPayload(form.values);
      if (drawerMode === "create") {
        await api("/safety-incidents/", { method: "POST", body: { ...payload, project_id: selectedId } });
      } else {
        const { project_id, ...updateOnly } = payload;
        await api(`/safety-incidents/${editing.id}`, { method: "PATCH", body: updateOnly });
      }
      setDrawerOpen(false);
      refresh();
      setSelected(null);
    } catch (e) {
      setSubmitError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading safety incidents..." />;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <h1 className="rex-h1">Safety Incidents</h1>
        <WriteButton onClick={openCreate}>+ New Incident</WriteButton>
      </div>
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
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {canWrite && (
                <button className="rex-btn rex-btn-outline" onClick={() => openEdit(selected)}>
                  Edit
                </button>
              )}
              <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>×</button>
            </div>
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

      {/* Safety Incident Drawer */}
      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerMode === "create" ? "New Safety Incident" : "Edit Safety Incident"}
        mode={drawerMode}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
        width={560}
      >
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Field label="Incident Number" name="incident_number" value={form.values.incident_number} onChange={form.setField} required autoFocus />
          <DateField label="Incident Date" name="incident_date" value={form.values.incident_date} onChange={form.setField} required />
        </div>
        <Field label="Title" name="title" value={form.values.title} onChange={form.setField} required />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <TimeField label="Incident Time" name="incident_time" value={form.values.incident_time} onChange={form.setField} />
          <Field label="Location" name="location" value={form.values.location} onChange={form.setField} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Select label="Incident Type" name="incident_type" value={form.values.incident_type} onChange={form.setField} options={INCIDENT_TYPES} required />
          <Select label="Severity" name="severity" value={form.values.severity} onChange={form.setField} options={SEVERITIES} required />
        </div>
        <Select label="Status" name="status" value={form.values.status} onChange={form.setField} options={STATUSES} />
        <TextArea label="Description" name="description" value={form.values.description} onChange={form.setField} rows={3} required />
        <TextArea label="Root Cause" name="root_cause" value={form.values.root_cause} onChange={form.setField} rows={2} />
        <TextArea label="Corrective Action" name="corrective_action" value={form.values.corrective_action} onChange={form.setField} rows={2} />
        <Select label="Reported By" name="reported_by" value={form.values.reported_by} onChange={form.setField} options={peopleOptions} />
        <Select label="Affected Person" name="affected_person_id" value={form.values.affected_person_id} onChange={form.setField} options={peopleOptions} />
        <Select label="Affected Company" name="affected_company_id" value={form.values.affected_company_id} onChange={form.setField} options={companyOptions} />
        <NumberField label="Lost Time Days" name="lost_time_days" value={form.values.lost_time_days} onChange={form.setField} step={1} />
        <div>
          <Checkbox label="OSHA Recordable" name="is_osha_recordable" value={form.values.is_osha_recordable} onChange={form.setField} />
          {form.values.is_osha_recordable && (
            <p style={{ margin: "4px 0 0 24px", fontSize: 12, color: "var(--rex-red)", fontWeight: 600 }}>
              OSHA Recordable — this incident will appear on OSHA 300 log
            </p>
          )}
        </div>
      </FormDrawer>
    </div>
  );
}
