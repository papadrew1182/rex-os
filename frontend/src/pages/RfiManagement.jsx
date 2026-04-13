import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";
import {
  FormDrawer, useFormState,
  Field, DateField, TextArea, Select, WriteButton, cleanPayload,
} from "../forms";
import { usePermissions } from "../permissions";
import { AlertCallout } from "../AlertCallout";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";
const fmt = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

function daysOpen(createdAt) {
  if (!createdAt) return null;
  const ms = Date.now() - new Date(createdAt).getTime();
  return Math.max(0, Math.floor(ms / 86400000));
}

const RFI_DEFAULT = {
  rfi_number: "",
  subject: "",
  question: "",
  answer: "",
  status: "draft",
  priority: "medium",
  cost_impact: null,
  schedule_impact: null,
  assigned_to: null,
  ball_in_court: null,
  rfi_manager: null,
  due_date: null,
  answered_date: null,
  drawing_id: null,
  cost_code_id: null,
  spec_section: "",
  location: "",
};

export default function RfiManagement() {
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
  const [drawings, setDrawings] = useState([]);
  const [costCodes, setCostCodes] = useState([]);

  const form = useFormState(RFI_DEFAULT);

  // Data fetching
  const refresh = useCallback(() => {
    if (!selectedId) return;
    api(`/rfis?project_id=${selectedId}&limit=200`).then(setData).catch((e) => setError(e.message));
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
      api(`/drawings?project_id=${selectedId}&limit=500`).catch(() => []),
      api(`/cost-codes?project_id=${selectedId}&limit=500`).catch(() => []),
    ]).then(([p, d, cc]) => {
      setPeople(Array.isArray(p) ? p : []);
      setDrawings(Array.isArray(d) ? d : []);
      setCostCodes(Array.isArray(cc) ? cc : []);
    });
  }, [selectedId]);

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.rfis || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q || (r.number || r.rfi_number || "").toString().toLowerCase().includes(q) || (r.subject || r.title || "").toLowerCase().includes(q);
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

  // Lookup option arrays
  const peopleOptions = useMemo(() => people.map((p) => ({ value: p.id, label: `${p.first_name} ${p.last_name}` })), [people]);
  const drawingOptions = useMemo(() => drawings.map((d) => ({ value: d.id, label: `${d.drawing_number} — ${d.title}` })), [drawings]);
  const costCodeOptions = useMemo(() => costCodes.map((c) => ({ value: c.id, label: `${c.code} — ${c.name}` })), [costCodes]);

  function priorityColor(p) {
    if (p === "critical" || p === "high") return "rex-badge-red";
    if (p === "medium" || p === "normal") return "rex-badge-amber";
    return "rex-badge-gray";
  }

  function openCreate() {
    setDrawerMode("create");
    setEditing(null);
    form.setAll({ ...RFI_DEFAULT });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  function openEdit(row) {
    setDrawerMode("edit");
    setEditing(row);
    form.setAll({
      rfi_number: row.rfi_number || row.number || "",
      subject: row.subject || row.title || "",
      question: row.question || "",
      answer: row.answer || "",
      status: row.status || "draft",
      priority: row.priority || "medium",
      cost_impact: row.cost_impact || null,
      schedule_impact: row.schedule_impact || null,
      assigned_to: row.assigned_to_id || row.assigned_to || null,
      ball_in_court: row.ball_in_court_id || row.ball_in_court || null,
      rfi_manager: row.rfi_manager_id || row.rfi_manager || null,
      due_date: row.due_date || null,
      answered_date: row.answered_date || null,
      drawing_id: row.drawing_id || null,
      cost_code_id: row.cost_code_id || null,
      spec_section: row.spec_section || "",
      location: row.location || "",
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
        await api("/rfis/", { method: "POST", body: { ...payload, project_id: selectedId } });
      } else {
        // eslint-disable-next-line no-unused-vars
        const { rfi_number, ...updateOnly } = payload;
        await api(`/rfis/${editing.id}`, { method: "PATCH", body: updateOnly });
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
  if (!data) return <PageLoader text="Loading RFIs..." />;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <h1 className="rex-h1">RFI Management</h1>
        <WriteButton onClick={openCreate}>+ New RFI</WriteButton>
      </div>
      <p className="rex-muted" style={{ marginBottom: 12 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>
      <AlertCallout notificationTypes={["aging_summary_rfi"]} title="Active alerts on this project" />

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
                    <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.number || row.rfi_number || "—"}</span></td>
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
              <div className="rex-h3">RFI #{selected.number || selected.rfi_number} — {selected.subject || selected.title}</div>
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

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerMode === "create" ? "New RFI" : `Edit RFI #${form.values.rfi_number || ""}`}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
        mode={drawerMode}
      >
        <div className="rex-form-row">
          <Field label="RFI Number" name="rfi_number" value={form.values.rfi_number} onChange={form.setField} required />
          <Select label="Status" name="status" value={form.values.status} onChange={form.setField} required options={["draft", "open", "answered", "closed", "void"]} />
          <Select label="Priority" name="priority" value={form.values.priority} onChange={form.setField} options={["low", "medium", "high"]} />
        </div>
        <Field label="Subject" name="subject" value={form.values.subject} onChange={form.setField} required />
        <TextArea label="Question" name="question" value={form.values.question} onChange={form.setField} rows={4} />
        <TextArea label="Answer" name="answer" value={form.values.answer} onChange={form.setField} rows={3} />
        <div className="rex-form-row">
          <Select label="Assigned To" name="assigned_to" value={form.values.assigned_to} onChange={form.setField} options={peopleOptions} />
          <Select label="Ball in Court" name="ball_in_court" value={form.values.ball_in_court} onChange={form.setField} options={peopleOptions} />
          <Select label="RFI Manager" name="rfi_manager" value={form.values.rfi_manager} onChange={form.setField} options={peopleOptions} />
        </div>
        <div className="rex-form-row">
          <DateField label="Due Date" name="due_date" value={form.values.due_date} onChange={form.setField} />
          <DateField label="Answered Date" name="answered_date" value={form.values.answered_date} onChange={form.setField} />
        </div>
        <div className="rex-form-row">
          <Select label="Cost Impact" name="cost_impact" value={form.values.cost_impact} onChange={form.setField} options={["yes", "no", "tbd"]} />
          <Select label="Schedule Impact" name="schedule_impact" value={form.values.schedule_impact} onChange={form.setField} options={["yes", "no", "tbd"]} />
        </div>
        <div className="rex-form-row">
          <Select label="Drawing" name="drawing_id" value={form.values.drawing_id} onChange={form.setField} options={drawingOptions} />
          <Select label="Cost Code" name="cost_code_id" value={form.values.cost_code_id} onChange={form.setField} options={costCodeOptions} />
        </div>
        <div className="rex-form-row">
          <Field label="Spec Section" name="spec_section" value={form.values.spec_section} onChange={form.setField} />
          <Field label="Location" name="location" value={form.values.location} onChange={form.setField} />
        </div>
      </FormDrawer>
    </div>
  );
}
