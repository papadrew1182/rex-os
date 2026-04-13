import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";
import {
  FormDrawer, useFormState,
  Field, NumberField, DateField, TextArea, Select, Checkbox, WriteButton, cleanPayload,
} from "../forms";
import { usePermissions } from "../permissions";
import { AlertCallout } from "../AlertCallout";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

function isOverdue(row) {
  if (row.status === "approved" || row.status === "closed" || row.status === "complete") return false;
  if (!row.due_date) return false;
  return new Date(row.due_date) < new Date();
}

const SUBMITTAL_TYPES = ["shop_drawing", "product_data", "sample", "mock_up", "test_report", "other"];
const SUBMITTAL_STATUSES = ["draft", "pending", "submitted", "approved", "approved_as_noted", "rejected", "closed"];

const SUBMITTAL_DEFAULT = {
  submittal_number: "",
  title: "",
  submittal_type: null,
  status: "draft",
  spec_section: "",
  current_revision: 0,
  location: "",
  is_critical_path: false,
  lead_time_days: null,
  due_date: null,
  submitted_date: null,
  approved_date: null,
  required_on_site: null,
  assigned_to: null,
  ball_in_court: null,
  responsible_contractor: null,
  submittal_manager_id: null,
  submittal_package_id: null,
  cost_code_id: null,
  schedule_activity_id: null,
};

export default function SubmittalManagement() {
  const { selected: project, selectedId } = useProject();
  const { canWrite } = usePermissions();

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [selected, setSelected] = useState(null);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState("create");
  const [editing, setEditing] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  // Lookup data
  const [people, setPeople] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [costCodes, setCostCodes] = useState([]);
  const [submittalPackages, setSubmittalPackages] = useState([]);
  const [scheduleActivities, setScheduleActivities] = useState([]);

  const form = useFormState(SUBMITTAL_DEFAULT);

  // Data fetching
  const refresh = useCallback(() => {
    if (!selectedId) return;
    api(`/submittals?project_id=${selectedId}&limit=200`).then(setData).catch((e) => setError(e.message));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null);
    refresh();
  }, [selectedId, refresh]);

  // Lookups
  useEffect(() => {
    if (!selectedId) return;
    Promise.all([
      api(`/people?limit=500`).catch(() => []),
      api(`/companies?limit=500`).catch(() => []),
      api(`/cost-codes?project_id=${selectedId}&limit=500`).catch(() => []),
      api(`/submittal-packages?project_id=${selectedId}&limit=200`).catch(() => []),
      api(`/schedule-activities?project_id=${selectedId}&limit=500`).catch(() => []),
    ]).then(([p, c, cc, sp, sa]) => {
      setPeople(Array.isArray(p) ? p : []);
      setCompanies(Array.isArray(c) ? c : []);
      setCostCodes(Array.isArray(cc) ? cc : []);
      setSubmittalPackages(Array.isArray(sp) ? sp : []);
      setScheduleActivities(Array.isArray(sa) ? sa : []);
    });
  }, [selectedId]);

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.submittals || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q || (r.number || r.submittal_number || "").toString().toLowerCase().includes(q) || (r.title || "").toLowerCase().includes(q) || (r.spec_section || "").toLowerCase().includes(q);
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

  // Lookup option arrays
  const peopleOptions = useMemo(() => people.map((p) => ({ value: p.id, label: `${p.first_name} ${p.last_name}` })), [people]);
  const companyOptions = useMemo(() => companies.map((c) => ({ value: c.id, label: c.name })), [companies]);
  const costCodeOptions = useMemo(() => costCodes.map((c) => ({ value: c.id, label: `${c.code} — ${c.name}` })), [costCodes]);
  const packageOptions = useMemo(() => submittalPackages.map((p) => ({ value: p.id, label: p.name || p.package_number || p.id })), [submittalPackages]);
  const activityOptions = useMemo(() => scheduleActivities.map((a) => ({ value: a.id, label: a.name || a.activity_id || a.id })), [scheduleActivities]);

  function openCreate() {
    setDrawerMode("create");
    setEditing(null);
    form.setAll({ ...SUBMITTAL_DEFAULT });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  function openEdit(row) {
    setDrawerMode("edit");
    setEditing(row);
    form.setAll({
      submittal_number: row.submittal_number || row.number || "",
      title: row.title || "",
      submittal_type: row.submittal_type || null,
      status: row.status || "draft",
      spec_section: row.spec_section || "",
      current_revision: row.current_revision ?? 0,
      location: row.location || "",
      is_critical_path: row.is_critical_path || false,
      lead_time_days: row.lead_time_days ?? null,
      due_date: row.due_date || null,
      submitted_date: row.submitted_date || null,
      approved_date: row.approved_date || null,
      required_on_site: row.required_on_site || row.required_on_site_date || null,
      assigned_to: row.assigned_to_id || row.assigned_to || null,
      ball_in_court: row.ball_in_court_id || row.ball_in_court || null,
      responsible_contractor: row.responsible_contractor_id || row.responsible_contractor || null,
      submittal_manager_id: row.submittal_manager_id || null,
      submittal_package_id: row.submittal_package_id || null,
      cost_code_id: row.cost_code_id || null,
      schedule_activity_id: row.schedule_activity_id || null,
    });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  async function onSubmit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const payload = cleanPayload(form.values);
      if (drawerMode === "create") {
        await api("/submittals/", { method: "POST", body: { ...payload, project_id: selectedId } });
      } else {
        // eslint-disable-next-line no-unused-vars
        const { submittal_number, ...updateOnly } = payload;
        await api(`/submittals/${editing.id}`, { method: "PATCH", body: updateOnly });
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
  if (!data) return <PageLoader text="Loading submittals..." />;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <h1 className="rex-h1">Submittals</h1>
        <WriteButton onClick={openCreate}>+ New Submittal</WriteButton>
      </div>
      <p className="rex-muted" style={{ marginBottom: 12 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>
      <AlertCallout notificationTypes={["aging_summary_submittal"]} title="Active alerts on this project" />

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
                  <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.number || row.submittal_number || "—"}</span></td>
                  <td>{row.title || "—"}</td>
                  <td><Badge status={row.status} /></td>
                  <td><span className="rex-muted" style={{ fontSize: 12 }}>{row.submittal_type || "—"}</span></td>
                  <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.spec_section || "—"}</span></td>
                  <td>{row.ball_in_court || "—"}</td>
                  <td style={{ color: isOverdue(row) ? "var(--rex-red)" : "inherit" }}>{fmtDate(row.due_date)}</td>
                  <td style={{ textAlign: "right" }}>{row.lead_time_days != null ? `${row.lead_time_days}d` : "—"}</td>
                  <td>{fmtDate(row.required_on_site_date || row.required_on_site)}</td>
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
              <div className="rex-h3">Submittal #{selected.number || selected.submittal_number} — {selected.title}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Badge status={selected.status} />
                {selected.submittal_type && <span className="rex-badge rex-badge-gray">{selected.submittal_type.replace(/_/g, " ")}</span>}
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {canWrite && (
                <button className="rex-btn rex-btn-outline" style={{ marginRight: 8 }} onClick={() => openEdit(selected)}>
                  Edit
                </button>
              )}
              <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>×</button>
            </div>
          </div>
          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Details">
              <Row label="Spec Section" value={selected.spec_section || "—"} />
              <Row label="Type" value={selected.submittal_type || "—"} />
              <Row label="Revision" value={selected.revision != null ? selected.revision : (selected.current_revision ?? "—")} />
              <Row label="Ball in Court" value={selected.ball_in_court || "—"} />
            </Card>
            <Card title="Dates">
              <Row label="Created" value={fmtDate(selected.created_at)} />
              <Row label="Submitted" value={fmtDate(selected.submitted_at || selected.submitted_date)} />
              <Row label="Due Date" value={fmtDate(selected.due_date)} />
              <Row label="Approved Date" value={fmtDate(selected.approved_at || selected.approved_date)} />
            </Card>
            <Card title="Procurement">
              <Row label="Lead Time" value={selected.lead_time_days != null ? `${selected.lead_time_days} days` : "—"} />
              <Row label="Required On Site" value={fmtDate(selected.required_on_site_date || selected.required_on_site)} />
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

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerMode === "create" ? "New Submittal" : `Edit Submittal #${form.values.submittal_number || ""}`}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
        mode={drawerMode}
      >
        <div className="rex-form-row">
          <Field label="Submittal Number" name="submittal_number" value={form.values.submittal_number} onChange={form.setField} required />
          <Select label="Type" name="submittal_type" value={form.values.submittal_type} onChange={form.setField} required options={SUBMITTAL_TYPES} />
          <Select label="Status" name="status" value={form.values.status} onChange={form.setField} required options={SUBMITTAL_STATUSES} />
        </div>
        <Field label="Title" name="title" value={form.values.title} onChange={form.setField} required />
        <div className="rex-form-row">
          <Field label="Spec Section" name="spec_section" value={form.values.spec_section} onChange={form.setField} />
          <Field label="Location" name="location" value={form.values.location} onChange={form.setField} />
          <NumberField label="Current Revision" name="current_revision" value={form.values.current_revision} onChange={form.setField} step={1} />
        </div>
        <div className="rex-form-row">
          <Select label="Assigned To" name="assigned_to" value={form.values.assigned_to} onChange={form.setField} options={peopleOptions} />
          <Select label="Ball in Court" name="ball_in_court" value={form.values.ball_in_court} onChange={form.setField} options={peopleOptions} />
          <Select label="Submittal Manager" name="submittal_manager_id" value={form.values.submittal_manager_id} onChange={form.setField} options={peopleOptions} />
        </div>
        <div className="rex-form-row">
          <Select label="Responsible Contractor" name="responsible_contractor" value={form.values.responsible_contractor} onChange={form.setField} options={companyOptions} />
          <Select label="Cost Code" name="cost_code_id" value={form.values.cost_code_id} onChange={form.setField} options={costCodeOptions} />
        </div>
        <div className="rex-form-row">
          <Select label="Submittal Package" name="submittal_package_id" value={form.values.submittal_package_id} onChange={form.setField} options={packageOptions} />
          <Select label="Schedule Activity" name="schedule_activity_id" value={form.values.schedule_activity_id} onChange={form.setField} options={activityOptions} />
        </div>
        <div className="rex-form-row">
          <DateField label="Due Date" name="due_date" value={form.values.due_date} onChange={form.setField} />
          <DateField label="Submitted Date" name="submitted_date" value={form.values.submitted_date} onChange={form.setField} />
          <DateField label="Approved Date" name="approved_date" value={form.values.approved_date} onChange={form.setField} />
        </div>
        <div className="rex-form-row">
          <NumberField label="Lead Time (days)" name="lead_time_days" value={form.values.lead_time_days} onChange={form.setField} step={1} />
          <DateField label="Required On Site" name="required_on_site" value={form.values.required_on_site} onChange={form.setField} />
        </div>
        <Checkbox label="Critical Path Item" name="is_critical_path" value={form.values.is_critical_path} onChange={form.setField} />
      </FormDrawer>
    </div>
  );
}
