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
const fmt = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function daysOpen(createdAt) {
  if (!createdAt) return null;
  return Math.max(0, Math.floor((Date.now() - new Date(createdAt).getTime()) / 86400000));
}

const PUNCH_DEFAULT = {
  punch_number: "",
  title: "",
  description: "",
  status: "draft",
  priority: "medium",
  punch_type: "",
  location: "",
  cost_impact: null,
  schedule_impact: null,
  is_critical_path: false,
  assigned_to: null,
  assigned_company_id: null,
  punch_manager_id: null,
  final_approver_id: null,
  due_date: null,
  closed_date: null,
  closed_by: null,
  drawing_id: null,
  cost_code_id: null,
};

export default function PunchList() {
  const { selected: project, selectedId } = useProject();
  const { canWrite } = usePermissions();

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
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
  const [drawings, setDrawings] = useState([]);
  const [costCodes, setCostCodes] = useState([]);

  const form = useFormState(PUNCH_DEFAULT);

  // Data fetching
  const refresh = useCallback(() => {
    if (!selectedId) return;
    api(`/punch-items?project_id=${selectedId}&limit=200`).then(setData).catch((e) => setError(e.message));
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
      api(`/drawings?project_id=${selectedId}&limit=500`).catch(() => []),
      api(`/cost-codes?project_id=${selectedId}&limit=500`).catch(() => []),
    ]).then(([p, c, d, cc]) => {
      setPeople(Array.isArray(p) ? p : []);
      setCompanies(Array.isArray(c) ? c : []);
      setDrawings(Array.isArray(d) ? d : []);
      setCostCodes(Array.isArray(cc) ? cc : []);
    });
  }, [selectedId]);

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.punch_items || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q || (r.number || r.punch_number || "").toString().toLowerCase().includes(q) || (r.title || r.description || "").toLowerCase().includes(q) || (r.location || "").toLowerCase().includes(q);
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

  // Lookup option arrays
  const peopleOptions = useMemo(() => people.map((p) => ({ value: p.id, label: `${p.first_name} ${p.last_name}` })), [people]);
  const companyOptions = useMemo(() => companies.map((c) => ({ value: c.id, label: c.name })), [companies]);
  const drawingOptions = useMemo(() => drawings.map((d) => ({ value: d.id, label: `${d.drawing_number} — ${d.title}` })), [drawings]);
  const costCodeOptions = useMemo(() => costCodes.map((c) => ({ value: c.id, label: `${c.code} — ${c.name}` })), [costCodes]);

  function priorityColor(p) {
    if (p === "critical") return "rex-badge-red";
    if (p === "high") return "rex-badge-amber";
    if (p === "medium" || p === "normal") return "rex-badge-purple";
    return "rex-badge-gray";
  }

  function openCreate() {
    setDrawerMode("create");
    setEditing(null);
    form.setAll({ ...PUNCH_DEFAULT });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  function openEdit(row) {
    setDrawerMode("edit");
    setEditing(row);
    form.setAll({
      punch_number: row.punch_number || row.number || "",
      title: row.title || "",
      description: row.description || "",
      status: row.status || "draft",
      priority: row.priority || "medium",
      punch_type: row.punch_type || "",
      location: row.location || "",
      cost_impact: row.cost_impact || null,
      schedule_impact: row.schedule_impact || null,
      is_critical_path: row.is_critical_path || false,
      assigned_to: row.assigned_to_id || row.assigned_to || null,
      assigned_company_id: row.assigned_company_id || null,
      punch_manager_id: row.punch_manager_id || null,
      final_approver_id: row.final_approver_id || null,
      due_date: row.due_date || null,
      closed_date: row.closed_date || null,
      closed_by: row.closed_by_id || row.closed_by || null,
      drawing_id: row.drawing_id || null,
      cost_code_id: row.cost_code_id || null,
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
        await api("/punch-items/", { method: "POST", body: { ...payload, project_id: selectedId } });
      } else {
        // eslint-disable-next-line no-unused-vars
        const { punch_number, ...updateOnly } = payload;
        await api(`/punch-items/${editing.id}`, { method: "PATCH", body: updateOnly });
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
  if (!data) return <PageLoader text="Loading punch list..." />;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <h1 className="rex-h1">Punch List</h1>
        <WriteButton onClick={openCreate}>+ New Punch Item</WriteButton>
      </div>
      <p className="rex-muted" style={{ marginBottom: 12 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>
      <AlertCallout notificationTypes={["aging_summary_punch"]} title="Active alerts on this project" />

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
                    <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.number || row.punch_number || "—"}</span></td>
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
              <div className="rex-h3">Punch #{selected.number || selected.punch_number} — {selected.title || selected.description}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Badge status={selected.status} />
                {selected.priority && <span className={`rex-badge ${priorityColor(selected.priority)}`}>{selected.priority}</span>}
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

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerMode === "create" ? "New Punch Item" : `Edit Punch #${form.values.punch_number || ""}`}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
        mode={drawerMode}
      >
        <div className="rex-form-row">
          <NumberField label="Punch Number" name="punch_number" value={form.values.punch_number} onChange={form.setField} required step={1} />
          <Select label="Status" name="status" value={form.values.status} onChange={form.setField} required options={["draft", "open", "work_required", "ready_for_review", "ready_to_close", "closed"]} />
          <Select label="Priority" name="priority" value={form.values.priority} onChange={form.setField} options={["low", "medium", "high"]} />
        </div>
        <Field label="Title" name="title" value={form.values.title} onChange={form.setField} required />
        <TextArea label="Description" name="description" value={form.values.description} onChange={form.setField} rows={3} />
        <div className="rex-form-row">
          <Field label="Punch Type" name="punch_type" value={form.values.punch_type} onChange={form.setField} />
          <Field label="Location" name="location" value={form.values.location} onChange={form.setField} />
        </div>
        <div className="rex-form-row">
          <Select label="Assigned To" name="assigned_to" value={form.values.assigned_to} onChange={form.setField} options={peopleOptions} />
          <Select label="Assigned Company" name="assigned_company_id" value={form.values.assigned_company_id} onChange={form.setField} options={companyOptions} />
          <Select label="Punch Manager" name="punch_manager_id" value={form.values.punch_manager_id} onChange={form.setField} options={peopleOptions} />
        </div>
        <div className="rex-form-row">
          <Select label="Cost Impact" name="cost_impact" value={form.values.cost_impact} onChange={form.setField} options={["yes", "no", "tbd"]} />
          <Select label="Schedule Impact" name="schedule_impact" value={form.values.schedule_impact} onChange={form.setField} options={["yes", "no", "tbd"]} />
        </div>
        <div className="rex-form-row">
          <Select label="Drawing" name="drawing_id" value={form.values.drawing_id} onChange={form.setField} options={drawingOptions} />
          <Select label="Cost Code" name="cost_code_id" value={form.values.cost_code_id} onChange={form.setField} options={costCodeOptions} />
        </div>
        <DateField label="Due Date" name="due_date" value={form.values.due_date} onChange={form.setField} />
        <Checkbox label="Critical Path Item" name="is_critical_path" value={form.values.is_critical_path} onChange={form.setField} />

        <div className="rex-h4" style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid var(--rex-border)" }}>Closure</div>
        <div className="rex-form-row">
          <DateField label="Closed Date" name="closed_date" value={form.values.closed_date} onChange={form.setField} />
          <Select label="Closed By" name="closed_by" value={form.values.closed_by} onChange={form.setField} options={peopleOptions} />
          <Select label="Final Approver" name="final_approver_id" value={form.values.final_approver_id} onChange={form.setField} options={peopleOptions} />
        </div>
      </FormDrawer>
    </div>
  );
}
