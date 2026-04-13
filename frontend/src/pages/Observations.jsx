import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";
import { FormDrawer, useFormState, Field, NumberField, DateField, TextArea, Select, WriteButton, cleanPayload } from "../forms";
import { usePermissions } from "../permissions";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

const today = new Date();
today.setHours(0, 0, 0, 0);

function priorityBadge(p) {
  if (p === "critical") return <span className="rex-badge rex-badge-red">{p}</span>;
  if (p === "high") return <span className="rex-badge rex-badge-red">{p}</span>;
  if (p === "medium") return <span className="rex-badge rex-badge-amber">{p}</span>;
  if (p === "low") return <span className="rex-badge rex-badge-gray">{p}</span>;
  return p ? <span className="rex-badge rex-badge-gray">{p}</span> : "—";
}

function isOpen(status) {
  return status === "open" || status === "in_progress";
}

const OBS_TYPES = ["safety", "quality", "housekeeping", "environmental", "commissioning"];
const OBS_STATUSES = ["open", "in_progress", "closed"];
const OBS_PRIORITIES = ["low", "medium", "high", "critical"];

export default function Observations() {
  const { selected: project, selectedId } = useProject();
  const { canWrite } = usePermissions();

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [attachments, setAttachments] = useState(null);
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
    api(`/observations?project_id=${selectedId}&limit=200`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null); setAttachments(null);
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

  function handleRowClick(row) {
    if (selected?.id === row.id) { setSelected(null); setAttachments(null); return; }
    setSelected(row);
    setAttachments(null);
    api(`/attachments?source_type=observation&source_id=${row.id}`)
      .then(setAttachments)
      .catch(() => setAttachments([]));
  }

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.observations || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q
        || (r.title || "").toLowerCase().includes(q)
        || (r.description || "").toLowerCase().includes(q)
        || (r.location || "").toLowerCase().includes(q);
      const matchStatus = !statusFilter || r.status === statusFilter;
      const matchType = !typeFilter || r.observation_type === typeFilter;
      const matchPriority = !priorityFilter || r.priority === priorityFilter;
      return matchSearch && matchStatus && matchType && matchPriority;
    });
  }, [items, search, statusFilter, typeFilter, priorityFilter]);

  const statuses = useMemo(() => [...new Set(items.map((r) => r.status).filter(Boolean))].sort(), [items]);
  const types = useMemo(() => [...new Set(items.map((r) => r.observation_type).filter(Boolean))].sort(), [items]);
  const priorities = useMemo(() => [...new Set(items.map((r) => r.priority).filter(Boolean))].sort(), [items]);

  const summary = useMemo(() => {
    const openItems = items.filter((r) => isOpen(r.status));
    const overdue = openItems.filter((r) => r.due_date && new Date(r.due_date + "T00:00:00") < today).length;
    const closed = items.filter((r) => r.status === "closed").length;
    const highCritical = items.filter((r) => r.priority === "high" || r.priority === "critical").length;
    return { total: items.length, open: openItems.length, overdue, closed, highCritical };
  }, [items]);

  function openCreate() {
    setDrawerMode("create");
    setEditing(null);
    form.setAll({ status: "open", priority: "medium" });
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
        await api("/observations/", { method: "POST", body: { ...payload, project_id: selectedId } });
      } else {
        const { project_id, ...updateOnly } = payload;
        await api(`/observations/${editing.id}`, { method: "PATCH", body: updateOnly });
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
  if (!data) return <PageLoader text="Loading observations..." />;

  const attList = Array.isArray(attachments) ? attachments : (attachments?.items || []);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <h1 className="rex-h1">Observations</h1>
        <WriteButton onClick={openCreate}>+ New Observation</WriteButton>
      </div>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total" value={summary.total} />
        <StatCard label="Open" value={summary.open} color={summary.open > 0 ? "amber" : ""} />
        <StatCard label="Overdue" value={summary.overdue} color={summary.overdue > 0 ? "red" : ""} />
        <StatCard label="Closed" value={summary.closed} color="green" />
        <StatCard label="High / Critical" value={summary.highCritical} color={summary.highCritical > 0 ? "red" : ""} />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search title, description, or location..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 280 }}
        />
        <select className="rex-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: 150 }}>
          <option value="">All Statuses</option>
          {statuses.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <select className="rex-input" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} style={{ width: 160 }}>
          <option value="">All Types</option>
          {types.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
        </select>
        <select className="rex-input" value={priorityFilter} onChange={(e) => setPriorityFilter(e.target.value)} style={{ width: 150 }}>
          <option value="">All Priorities</option>
          {priorities.map((p) => <option key={p} value={p}>{p.replace(/_/g, " ")}</option>)}
        </select>
        <span className="rex-muted">{filtered.length} record{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No observations found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Number</th>
                <th>Title</th>
                <th>Type</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Assigned To</th>
                <th>Location</th>
                <th>Due Date</th>
                <th>Closed Date</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => {
                const rowIsOpen = isOpen(row.status);
                const isOverdue = rowIsOpen && row.due_date && new Date(row.due_date + "T00:00:00") < today;
                return (
                  <tr key={row.id || i} onClick={() => handleRowClick(row)}>
                    <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.observation_number || "—"}</span></td>
                    <td>{row.title || "—"}</td>
                    <td>
                      {row.observation_type
                        ? <span className="rex-badge rex-badge-gray">{row.observation_type.replace(/_/g, " ")}</span>
                        : "—"}
                    </td>
                    <td><Badge status={row.status} /></td>
                    <td>{priorityBadge(row.priority)}</td>
                    <td>
                      {row.assigned_to
                        ? <span style={{ fontFamily: "monospace", fontSize: 11 }}>{row.assigned_to.slice(0, 8)}…</span>
                        : "—"}
                    </td>
                    <td>{row.location || "—"}</td>
                    <td style={{ color: isOverdue ? "var(--rex-red)" : "inherit" }}>{fmtDate(row.due_date)}</td>
                    <td>{fmtDate(row.closed_date)}</td>
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
              <div className="rex-h3">#{selected.observation_number} — {selected.title}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Badge status={selected.status} />
                {priorityBadge(selected.priority)}
                {selected.observation_type && (
                  <span className="rex-badge rex-badge-gray">{selected.observation_type.replace(/_/g, " ")}</span>
                )}
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {canWrite && (
                <button className="rex-btn rex-btn-outline" onClick={() => openEdit(selected)}>
                  Edit
                </button>
              )}
              <button className="rex-detail-panel-close" onClick={() => { setSelected(null); setAttachments(null); }}>×</button>
            </div>
          </div>

          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Observation Info">
              <Row label="Number" value={selected.observation_number || "—"} />
              <Row label="Title" value={selected.title || "—"} />
              <Row label="Type" value={selected.observation_type?.replace(/_/g, " ") || "—"} />
              <Row label="Status" value={<Badge status={selected.status} />} />
              <Row label="Priority" value={priorityBadge(selected.priority)} />
            </Card>
            <Card title="Assignment">
              <Row label="Assigned To" value={selected.assigned_to || "—"} />
              <Row label="Company" value={selected.assigned_company_id || "—"} />
              <Row label="Location" value={selected.location || "—"} />
            </Card>
            <Card title="Dates">
              <Row label="Created" value={selected.created_at ? new Date(selected.created_at).toLocaleDateString() : "—"} />
              <Row label="Due Date" value={fmtDate(selected.due_date)} />
              <Row label="Closed Date" value={fmtDate(selected.closed_date)} />
            </Card>
          </div>

          {selected.description && (
            <Card title="Description" style={{ marginBottom: 12 }}>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.description}</p>
            </Card>
          )}

          {selected.corrective_action && (
            <Card title="Corrective Action" style={{ marginBottom: 12 }}>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.corrective_action}</p>
            </Card>
          )}

          {(selected.contributing_behavior || selected.contributing_condition) && (
            <Card title="Root Cause" style={{ marginBottom: 12 }}>
              {selected.contributing_behavior && (
                <div style={{ marginBottom: selected.contributing_condition ? 8 : 0 }}>
                  <div className="rex-muted" style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 3 }}>Contributing Behavior</div>
                  <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.contributing_behavior}</p>
                </div>
              )}
              {selected.contributing_condition && (
                <div>
                  <div className="rex-muted" style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", marginBottom: 3 }}>Contributing Condition</div>
                  <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.contributing_condition}</p>
                </div>
              )}
            </Card>
          )}

          <Card title="Attachments">
            {attachments === null ? (
              <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>Loading attachments…</p>
            ) : attList.length === 0 ? (
              <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>No attachments.</p>
            ) : (
              <>
                <p className="rex-muted" style={{ margin: "0 0 8px", fontSize: 12 }}>{attList.length} attachment{attList.length !== 1 ? "s" : ""}</p>
                <div className="rex-table-wrap">
                  <table className="rex-table">
                    <thead>
                      <tr>
                        <th>Filename</th>
                        <th style={{ textAlign: "right" }}>File Size</th>
                        <th>Content Type</th>
                      </tr>
                    </thead>
                    <tbody>
                      {attList.map((att, i) => (
                        <tr key={att.id || i}>
                          <td>{att.filename || att.file_name || "—"}</td>
                          <td style={{ textAlign: "right" }}>
                            {att.file_size != null
                              ? att.file_size >= 1048576
                                ? `${(att.file_size / 1048576).toFixed(1)} MB`
                                : `${(att.file_size / 1024).toFixed(1)} KB`
                              : "—"}
                          </td>
                          <td>{att.content_type || att.mime_type || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </Card>
        </div>
      )}

      {/* Observation Drawer */}
      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerMode === "create" ? "New Observation" : "Edit Observation"}
        mode={drawerMode}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
      >
        <NumberField label="Observation Number" name="observation_number" value={form.values.observation_number} onChange={form.setField} step={1} required autoFocus />
        <Field label="Title" name="title" value={form.values.title} onChange={form.setField} required />
        <Select label="Observation Type" name="observation_type" value={form.values.observation_type} onChange={form.setField} options={OBS_TYPES} required />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Select label="Status" name="status" value={form.values.status} onChange={form.setField} options={OBS_STATUSES} />
          <Select label="Priority" name="priority" value={form.values.priority} onChange={form.setField} options={OBS_PRIORITIES} />
        </div>
        <TextArea label="Description" name="description" value={form.values.description} onChange={form.setField} rows={3} required />
        <TextArea label="Corrective Action" name="corrective_action" value={form.values.corrective_action} onChange={form.setField} rows={3} />
        <TextArea label="Contributing Behavior" name="contributing_behavior" value={form.values.contributing_behavior} onChange={form.setField} rows={2} />
        <TextArea label="Contributing Condition" name="contributing_condition" value={form.values.contributing_condition} onChange={form.setField} rows={2} />
        <Field label="Location" name="location" value={form.values.location} onChange={form.setField} />
        <Select label="Assigned To" name="assigned_to" value={form.values.assigned_to} onChange={form.setField} options={peopleOptions} />
        <Select label="Assigned Company" name="assigned_company_id" value={form.values.assigned_company_id} onChange={form.setField} options={companyOptions} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <DateField label="Due Date" name="due_date" value={form.values.due_date} onChange={form.setField} />
          <DateField label="Closed Date" name="closed_date" value={form.values.closed_date} onChange={form.setField} />
        </div>
      </FormDrawer>
    </div>
  );
}
