import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";
import { FormDrawer, useFormState, Field, NumberField, DateField, TextArea, Select, WriteButton, cleanPayload } from "../forms";
import { usePermissions } from "../permissions";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

function resultBadge(result) {
  if (result === "pass") return <span className="rex-badge rex-badge-green">pass</span>;
  if (result === "fail") return <span className="rex-badge rex-badge-red">fail</span>;
  if (result === "n_a") return <span className="rex-badge rex-badge-gray">n/a</span>;
  if (result === "not_inspected") return <span className="rex-badge rex-badge-amber">not inspected</span>;
  return <span className="rex-badge rex-badge-gray">{result || "—"}</span>;
}

const INSP_TYPES = ["municipal", "quality", "safety", "pre_concrete", "framing", "mep_rough", "mep_final", "other"];
const INSP_STATUSES = ["scheduled", "in_progress", "passed", "failed", "partial", "cancelled"];
const ITEM_RESULTS = ["pass", "fail", "n_a", "not_inspected"];

export default function Inspections() {
  const { selected: project, selectedId } = useProject();
  const { canWrite } = usePermissions();

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [inspSummary, setInspSummary] = useState(null);
  const [inspItems, setInspItems] = useState(null);
  const [people, setPeople] = useState([]);
  const [companies, setCompanies] = useState([]);

  // Main drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState("create");
  const [editing, setEditing] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const form = useFormState({});

  // Child (inspection item) drawer state
  const [childDrawerOpen, setChildDrawerOpen] = useState(false);
  const [childMode, setChildMode] = useState("create");
  const [childEditing, setChildEditing] = useState(null);
  const [childSubmitting, setChildSubmitting] = useState(false);
  const [childError, setChildError] = useState(null);
  const childForm = useFormState({});

  const refresh = useCallback(() => {
    if (!selectedId) return;
    api(`/inspections?project_id=${selectedId}&limit=200`)
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

  function refreshItems(inspId) {
    api(`/inspection-items?inspection_id=${inspId}&limit=100`)
      .then(setInspItems)
      .catch(() => setInspItems([]));
  }

  function handleRowClick(row) {
    if (selected?.id === row.id) { setSelected(null); setInspSummary(null); setInspItems(null); return; }
    setSelected(row);
    setInspSummary(null);
    setInspItems(null);
    api(`/inspections/${row.id}/summary`).then(setInspSummary).catch(() => setInspSummary(null));
    api(`/inspection-items?inspection_id=${row.id}&limit=100`).then(setInspItems).catch(() => setInspItems([]));
  }

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.inspections || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q
        || (r.inspection_number || "").toLowerCase().includes(q)
        || (r.title || "").toLowerCase().includes(q)
        || (r.location || "").toLowerCase().includes(q);
      const matchStatus = !statusFilter || r.status === statusFilter;
      const matchType = !typeFilter || r.inspection_type === typeFilter;
      return matchSearch && matchStatus && matchType;
    });
  }, [items, search, statusFilter, typeFilter]);

  const statuses = useMemo(() => [...new Set(items.map((r) => r.status).filter(Boolean))], [items]);
  const types = useMemo(() => [...new Set(items.map((r) => r.inspection_type).filter(Boolean))], [items]);

  const summary = useMemo(() => {
    const openScheduled = items.filter((r) => r.status === "scheduled" || r.status === "in_progress").length;
    const completed = items.filter((r) => r.status === "passed" || r.status === "failed" || r.status === "partial").length;
    const failed = items.filter((r) => r.status === "failed").length;
    const passed = items.filter((r) => r.status === "passed").length;
    const passRate = (passed + failed) > 0 ? Math.round(passed / (passed + failed) * 100) + "%" : "—";
    return { total: items.length, openScheduled, completed, failed, passRate };
  }, [items]);

  function openCreate() {
    setDrawerMode("create");
    setEditing(null);
    form.setAll({ status: "scheduled" });
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
        await api("/inspections/", { method: "POST", body: { ...payload, project_id: selectedId } });
      } else {
        const { project_id, ...updateOnly } = payload;
        await api(`/inspections/${editing.id}`, { method: "PATCH", body: updateOnly });
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

  function openChildCreate(inspId) {
    setChildMode("create");
    setChildEditing(null);
    childForm.setAll({ inspection_id: inspId, result: "not_inspected" });
    setChildError(null);
    setChildDrawerOpen(true);
  }

  function openChildEdit(item) {
    setChildMode("edit");
    setChildEditing(item);
    childForm.setAll({ ...item });
    setChildError(null);
    setChildDrawerOpen(true);
  }

  async function onChildSubmit() {
    setChildSubmitting(true);
    setChildError(null);
    try {
      const payload = cleanPayload(childForm.values);
      if (childMode === "create") {
        await api("/inspection-items/", { method: "POST", body: payload });
      } else {
        const { inspection_id, ...updateOnly } = payload;
        await api(`/inspection-items/${childEditing.id}`, { method: "PATCH", body: updateOnly });
      }
      setChildDrawerOpen(false);
      if (selected) refreshItems(selected.id);
    } catch (e) {
      setChildError(e.message);
    } finally {
      setChildSubmitting(false);
    }
  }

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading inspections..." />;

  const itemsList = Array.isArray(inspItems) ? inspItems : (inspItems?.items || []);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <h1 className="rex-h1">Inspections</h1>
        <WriteButton onClick={openCreate}>+ New Inspection</WriteButton>
      </div>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Inspections" value={summary.total} />
        <StatCard label="Open / Scheduled" value={summary.openScheduled} color={summary.openScheduled > 0 ? "amber" : ""} />
        <StatCard label="Completed" value={summary.completed} color="green" />
        <StatCard label="Failed" value={summary.failed} color={summary.failed > 0 ? "red" : ""} />
        <StatCard label="Pass Rate" value={summary.passRate} color="green" />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search #, title, or location..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 260 }}
        />
        <select className="rex-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: 150 }}>
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
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No inspections found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Insp #</th>
                <th>Title</th>
                <th>Type</th>
                <th>Status</th>
                <th>Scheduled</th>
                <th>Completed</th>
                <th>Inspector</th>
                <th>Location</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr key={row.id || i} onClick={() => handleRowClick(row)}>
                  <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.inspection_number || "—"}</span></td>
                  <td>{row.title || "—"}</td>
                  <td>{row.inspection_type ? <span className="rex-badge rex-badge-gray">{row.inspection_type.replace(/_/g, " ")}</span> : "—"}</td>
                  <td><Badge status={row.status} /></td>
                  <td>{fmtDate(row.scheduled_date)}</td>
                  <td>{fmtDate(row.completed_date)}</td>
                  <td>{row.inspector_name || "—"}</td>
                  <td>{row.location || "—"}</td>
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
              <div className="rex-h3">Inspection #{selected.inspection_number} — {selected.title}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Badge status={selected.status} />
                {selected.inspection_type && <span className="rex-badge rex-badge-gray">{selected.inspection_type.replace(/_/g, " ")}</span>}
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {canWrite && (
                <button className="rex-btn rex-btn-outline" onClick={() => openEdit(selected)}>
                  Edit
                </button>
              )}
              <button className="rex-detail-panel-close" onClick={() => { setSelected(null); setInspSummary(null); setInspItems(null); }}>×</button>
            </div>
          </div>
          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Inspection Info">
              <Row label="Number" value={selected.inspection_number || "—"} />
              <Row label="Title" value={selected.title || "—"} />
              <Row label="Type" value={selected.inspection_type?.replace(/_/g, " ") || "—"} />
              <Row label="Status" value={<Badge status={selected.status} />} />
              <Row label="Scheduled" value={fmtDate(selected.scheduled_date)} />
              <Row label="Completed" value={fmtDate(selected.completed_date)} />
              <Row label="Inspector" value={selected.inspector_name || "—"} />
              <Row label="Location" value={selected.location || "—"} />
            </Card>
            <Card title="Results Summary">
              {inspSummary ? (
                <>
                  <Row label="Pass" value={inspSummary.items_by_result?.pass ?? "—"} />
                  <Row label="Fail" value={inspSummary.items_by_result?.fail ?? "—"} />
                  <Row label="N/A" value={inspSummary.items_by_result?.n_a ?? "—"} />
                  <Row label="Not Inspected" value={inspSummary.items_by_result?.not_inspected ?? "—"} />
                  <Row label="Unresolved Failures" value={
                    inspSummary.has_unresolved_failures
                      ? <span className="rex-badge rex-badge-red">YES</span>
                      : <span className="rex-badge rex-badge-green">NO</span>
                  } />
                </>
              ) : (
                <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>Loading…</p>
              )}
            </Card>
            <Card title="Linked Punch Items">
              {inspSummary ? (
                inspSummary.linked_punch_item_ids?.length > 0 ? (
                  <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, color: "var(--rex-text-muted)" }}>
                    {inspSummary.linked_punch_item_ids.map((id) => (
                      <li key={id}><span style={{ fontFamily: "monospace" }}>{id}</span></li>
                    ))}
                  </ul>
                ) : (
                  <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>None linked.</p>
                )
              ) : (
                <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>Loading…</p>
              )}
            </Card>
          </div>
          {selected.comments && (
            <Card title="Comments" style={{ marginBottom: 12 }}>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.comments}</p>
            </Card>
          )}
          <Card title="Inspection Items">
            {canWrite && (
              <div style={{ marginBottom: 8 }}>
                <WriteButton onClick={() => openChildCreate(selected.id)} variant="outline">+ Add Item</WriteButton>
              </div>
            )}
            {inspItems === null ? (
              <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>Loading…</p>
            ) : itemsList.length === 0 ? (
              <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>No inspection items.</p>
            ) : (
              <div className="rex-table-wrap" style={{ marginTop: 8 }}>
                <table className="rex-table">
                  <thead>
                    <tr>
                      <th>Item #</th>
                      <th>Description</th>
                      <th>Result</th>
                      <th>Comments</th>
                      {canWrite && <th></th>}
                    </tr>
                  </thead>
                  <tbody>
                    {itemsList.map((item, i) => (
                      <tr key={item.id || i}>
                        <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{item.item_number || i + 1}</span></td>
                        <td>{item.description || "—"}</td>
                        <td>{resultBadge(item.result)}</td>
                        <td>{item.comments || "—"}</td>
                        {canWrite && (
                          <td>
                            <button className="rex-btn rex-btn-outline" style={{ padding: "2px 8px", fontSize: 11 }} onClick={() => openChildEdit(item)}>
                              Edit
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Main Inspection Drawer */}
      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerMode === "create" ? "New Inspection" : "Edit Inspection"}
        mode={drawerMode}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
      >
        <Field label="Inspection Number" name="inspection_number" value={form.values.inspection_number} onChange={form.setField} required autoFocus />
        <Field label="Title" name="title" value={form.values.title} onChange={form.setField} required />
        <Select label="Inspection Type" name="inspection_type" value={form.values.inspection_type} onChange={form.setField} options={INSP_TYPES} required />
        <Select label="Status" name="status" value={form.values.status} onChange={form.setField} options={INSP_STATUSES} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <DateField label="Scheduled Date" name="scheduled_date" value={form.values.scheduled_date} onChange={form.setField} required />
          <DateField label="Completed Date" name="completed_date" value={form.values.completed_date} onChange={form.setField} />
        </div>
        <Field label="Inspector Name" name="inspector_name" value={form.values.inspector_name} onChange={form.setField} />
        <Select label="Inspecting Company" name="inspecting_company_id" value={form.values.inspecting_company_id} onChange={form.setField} options={companyOptions} />
        <Select label="Responsible Person" name="responsible_person_id" value={form.values.responsible_person_id} onChange={form.setField} options={peopleOptions} />
        <Field label="Location" name="location" value={form.values.location} onChange={form.setField} />
        <TextArea label="Comments" name="comments" value={form.values.comments} onChange={form.setField} />
      </FormDrawer>

      {/* Child Inspection Item Drawer */}
      <FormDrawer
        open={childDrawerOpen}
        onClose={() => setChildDrawerOpen(false)}
        title={childMode === "create" ? "Add Inspection Item" : "Edit Inspection Item"}
        mode={childMode}
        onSubmit={onChildSubmit}
        onReset={childForm.reset}
        dirty={childForm.dirty}
        submitting={childSubmitting}
        error={childError}
      >
        <NumberField label="Item Number" name="item_number" value={childForm.values.item_number} onChange={childForm.setField} step={1} required />
        <Field label="Description" name="description" value={childForm.values.description} onChange={childForm.setField} required />
        <Select label="Result" name="result" value={childForm.values.result} onChange={childForm.setField} options={ITEM_RESULTS} required />
        <TextArea label="Comments" name="comments" value={childForm.values.comments} onChange={childForm.setField} />
      </FormDrawer>
    </div>
  );
}
