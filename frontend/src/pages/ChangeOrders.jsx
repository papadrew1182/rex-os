import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";
import { FormDrawer, useFormState, Field, NumberField, TextArea, Select, WriteButton, cleanPayload } from "../forms";
import { usePermissions } from "../permissions";

const fmt = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

const CE_DEFAULT = {
  title: "",
  event_number: "",
  status: "open",
  change_reason: null,
  event_type: null,
  scope: null,
  estimated_amount: null,
  prime_contract_id: "",
  rfi_id: "",
  description: "",
};

const LINE_DEFAULT = {
  change_event_id: null,
  description: "",
  amount: null,
  cost_code_id: null,
};

export default function ChangeOrders() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Change event drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState("create");
  const [editing, setEditing] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  // Line item drawer state
  const [lineDrawerOpen, setLineDrawerOpen] = useState(false);
  const [lineDrawerMode, setLineDrawerMode] = useState("create");
  const [lineEditing, setLineEditing] = useState(null);
  const [lineSubmitting, setLineSubmitting] = useState(false);
  const [lineSubmitError, setLineSubmitError] = useState(null);

  // Dropdown data
  const [costCodes, setCostCodes] = useState([]);

  const form = useFormState(CE_DEFAULT);
  const lineForm = useFormState(LINE_DEFAULT);
  const { canWrite } = usePermissions();

  // Load list
  const refresh = useCallback(() => {
    if (!selectedId) return;
    api(`/change-events?project_id=${selectedId}&limit=200`).then(setData).catch((e) => setError(e.message));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null); setDetail(null);
    api(`/change-events?project_id=${selectedId}&limit=200`).then(setData).catch((e) => setError(e.message));
  }, [selectedId]);

  // Fetch cost codes when project changes
  useEffect(() => {
    if (!selectedId) return;
    api(`/cost-codes?project_id=${selectedId}&limit=500`).then(c => setCostCodes(Array.isArray(c) ? c : [])).catch(() => {});
  }, [selectedId]);

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.change_events || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q || (r.number || "").toString().toLowerCase().includes(q) || (r.title || "").toLowerCase().includes(q);
      const matchStatus = !statusFilter || r.status === statusFilter;
      return matchSearch && matchStatus;
    });
  }, [items, search, statusFilter]);

  const statuses = useMemo(() => [...new Set(items.map((r) => r.status).filter(Boolean))], [items]);

  const summary = useMemo(() => ({
    total: items.length,
    open: items.filter((r) => r.status === "open").length,
    pending: items.filter((r) => r.status === "pending" || r.status === "in_progress").length,
    totalEstimated: items.reduce((s, r) => s + (r.estimated_amount ?? 0), 0),
    approved: items.filter((r) => r.status === "closed" || r.status === "approved" || r.status === "complete"),
  }), [items]);

  const approvedAmount = summary.approved.reduce((s, r) => s + (r.estimated_amount ?? 0), 0);

  // Refresh detail panel for selected change event
  const refreshDetail = useCallback((id) => {
    if (!id) return;
    setDetailLoading(true);
    api(`/change-events/${id}/detail`)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }, []);

  function handleSelectRow(row) {
    if (selected?.id === row.id) { setSelected(null); setDetail(null); return; }
    setSelected(row);
    setDetail(null);
    refreshDetail(row.id);
  }

  // Change event drawer handlers
  function openCreate() {
    setDrawerMode("create");
    setEditing(null);
    form.setAll({ ...CE_DEFAULT });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  function openEdit(row) {
    setDrawerMode("edit");
    setEditing(row);
    form.setAll({
      title: row.title,
      event_number: row.number ?? row.event_number,
      description: row.description ?? "",
      status: row.status,
      change_reason: row.reason ?? row.change_reason ?? "",
      event_type: row.change_event_type ?? row.event_type ?? "",
      scope: row.scope ?? "",
      estimated_amount: row.estimated_amount ?? 0,
      prime_contract_id: row.prime_contract_id ?? "",
      rfi_id: row.rfi_id ?? "",
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
        payload.project_id = selectedId;
        await api("/change-events/", { method: "POST", body: payload });
      } else {
        await api(`/change-events/${editing.id}`, { method: "PATCH", body: payload });
      }
      setDrawerOpen(false);
      refresh();
    } catch (e) {
      setSubmitError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  // Line item drawer handlers
  function openLineCreate() {
    setLineDrawerMode("create");
    setLineEditing(null);
    lineForm.setAll({
      description: "",
      amount: 0,
      cost_code_id: "",
      sort_order: 0,
    });
    setLineSubmitError(null);
    setLineDrawerOpen(true);
  }

  function openLineEdit(li) {
    setLineDrawerMode("edit");
    setLineEditing(li);
    lineForm.setAll({
      description: li.description ?? "",
      amount: li.amount ?? 0,
      cost_code_id: li.cost_code_id ?? "",
      sort_order: li.sort_order ?? 0,
    });
    setLineSubmitError(null);
    setLineDrawerOpen(true);
  }

  async function onLineSubmit() {
    setLineSubmitting(true);
    setLineSubmitError(null);
    try {
      const payload = cleanPayload(lineForm.values);
      if (lineDrawerMode === "create") {
        payload.change_event_id = selected.id;
        await api("/change-event-line-items/", { method: "POST", body: payload });
      } else {
        await api(`/change-event-line-items/${lineEditing.id}`, { method: "PATCH", body: payload });
      }
      setLineDrawerOpen(false);
      refreshDetail(selected.id);
    } catch (e) {
      setLineSubmitError(e.message);
    } finally {
      setLineSubmitting(false);
    }
  }

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading change events..." />;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <h1 className="rex-h1">Change Orders</h1>
        <WriteButton onClick={openCreate}>+ New Change Event</WriteButton>
      </div>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Events" value={summary.total} />
        <StatCard label="Open" value={summary.open} color={summary.open > 0 ? "amber" : ""} />
        <StatCard label="Pending" value={summary.pending} color={summary.pending > 0 ? "amber" : ""} />
        <StatCard label="Total Estimated" value={fmt(summary.totalEstimated)} color="red" />
        <StatCard label="Approved Amount" value={fmt(approvedAmount)} color="green" />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search event # or title..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 280 }}
        />
        <select className="rex-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: 160 }}>
          <option value="">All Statuses</option>
          {statuses.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <span className="rex-muted">{filtered.length} record{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">🔄</div>No change events found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Event #</th>
                <th>Title</th>
                <th>Status</th>
                <th>Scope</th>
                <th>Reason</th>
                <th>Type</th>
                <th style={{ textAlign: "right" }}>Estimated Amount</th>
                <th>RFI Link</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr key={row.id || i} onClick={() => handleSelectRow(row)}>
                  <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.number || "—"}</span></td>
                  <td>{row.title || "—"}</td>
                  <td><Badge status={row.status} /></td>
                  <td><span className="rex-muted" style={{ fontSize: 12 }}>{row.scope || "—"}</span></td>
                  <td><span className="rex-muted" style={{ fontSize: 12 }}>{row.reason || "—"}</span></td>
                  <td><span className="rex-muted" style={{ fontSize: 12 }}>{row.change_event_type || row.type || "—"}</span></td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.estimated_amount)}</td>
                  <td>{row.rfi_number ? <span className="rex-badge rex-badge-purple">RFI {row.rfi_number}</span> : "—"}</td>
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
              <div className="rex-h3">Event #{selected.number} — {selected.title}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8 }}>
                <Badge status={selected.status} />
                {selected.change_event_type && <span className="rex-badge rex-badge-gray">{selected.change_event_type}</span>}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {canWrite && <button className="rex-btn rex-btn-outline" onClick={() => openEdit(selected)}>Edit</button>}
              <button className="rex-detail-panel-close" onClick={() => { setSelected(null); setDetail(null); }}>×</button>
            </div>
          </div>
          <div className="rex-grid-2" style={{ marginBottom: 14 }}>
            <Card title="Event Details">
              <Row label="Scope" value={selected.scope || "—"} />
              <Row label="Reason" value={selected.reason || "—"} />
              <Row label="Type" value={selected.change_event_type || selected.type || "—"} />
              <Row label="Estimated Amount" value={fmt(selected.estimated_amount)} />
              <Row label="Created" value={fmtDate(selected.created_at)} />
            </Card>
            <Card title="Linked Items">
              {detailLoading ? <span className="rex-muted">Loading...</span> : detail ? (
                <>
                  {detail.pcos?.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <div className="rex-section-label" style={{ marginBottom: 4 }}>PCOs ({detail.pcos.length})</div>
                      {detail.pcos.map((p, j) => (
                        <div key={j} style={{ fontSize: 12, padding: "3px 0", borderBottom: "1px solid var(--rex-border)" }}>
                          <strong>{p.number}</strong> — {p.title} <Badge status={p.status} />
                        </div>
                      ))}
                    </div>
                  )}
                  {detail.ccos?.length > 0 && (
                    <div>
                      <div className="rex-section-label" style={{ marginBottom: 4 }}>CCOs ({detail.ccos.length})</div>
                      {detail.ccos.map((c, j) => (
                        <div key={j} style={{ fontSize: 12, padding: "3px 0", borderBottom: "1px solid var(--rex-border)" }}>
                          <strong>{c.number}</strong> — {c.title} <Badge status={c.status} />
                        </div>
                      ))}
                    </div>
                  )}
                  {(!detail.pcos?.length && !detail.ccos?.length) && <span className="rex-muted">No linked PCOs or CCOs.</span>}
                </>
              ) : <span className="rex-muted">No additional details.</span>}
            </Card>
          </div>
          {selected.description && (
            <div>
              <div className="rex-section-label" style={{ marginBottom: 6 }}>Description</div>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.description}</p>
            </div>
          )}
          <div style={{ marginTop: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
              <div className="rex-section-label">Line Items{detail?.line_items?.length ? ` (${detail.line_items.length})` : ""}</div>
              {canWrite && <WriteButton onClick={openLineCreate} variant="outline">+ Add Line Item</WriteButton>}
            </div>
            {detailLoading ? (
              <span className="rex-muted">Loading...</span>
            ) : detail?.line_items?.length > 0 ? (
              <div className="rex-table-wrap">
                <table className="rex-table">
                  <thead>
                    <tr>
                      <th>Description</th>
                      <th style={{ textAlign: "right" }}>Amount</th>
                      {canWrite && <th style={{ width: 60 }}></th>}
                    </tr>
                  </thead>
                  <tbody>
                    {detail.line_items.map((li, j) => (
                      <tr key={li.id || j}>
                        <td>{li.description || "—"}</td>
                        <td style={{ textAlign: "right" }} className="rex-money">{fmt(li.amount)}</td>
                        {canWrite && (
                          <td>
                            <button
                              className="rex-btn rex-btn-outline"
                              style={{ padding: "2px 8px", fontSize: 11 }}
                              onClick={(e) => { e.stopPropagation(); openLineEdit(li); }}
                            >
                              Edit
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <span className="rex-muted" style={{ fontSize: 13 }}>No line items yet.</span>
            )}
          </div>
        </div>
      )}

      {/* Change Event FormDrawer */}
      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerMode === "create" ? "New Change Event" : `Edit Event — ${form.values.title || ""}`}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
        mode={drawerMode}
      >
        <div className="rex-form-row">
          <Field label="Title" name="title" value={form.values.title} onChange={form.setField} required autoFocus />
          <Field label="Event Number" name="event_number" value={form.values.event_number} onChange={form.setField} />
        </div>
        <div className="rex-form-row">
          <Select label="Status" name="status" value={form.values.status} onChange={form.setField} required options={["open","pending","approved","closed","void"]} />
          <Select label="Change Reason" name="change_reason" value={form.values.change_reason} onChange={form.setField} options={["owner_change","design_change","unforeseen","allowance","contingency"]} />
        </div>
        <div className="rex-form-row">
          <Select label="Event Type" name="event_type" value={form.values.event_type} onChange={form.setField} options={["tbd","allowance","contingency","owner_change","transfer"]} />
          <Select label="Scope" name="scope" value={form.values.scope} onChange={form.setField} options={["in_scope","out_of_scope","tbd"]} />
        </div>
        <NumberField label="Estimated Amount" name="estimated_amount" value={form.values.estimated_amount} onChange={form.setField} />
        <div className="rex-form-row">
          <Field label="Prime Contract ID" name="prime_contract_id" value={form.values.prime_contract_id} onChange={form.setField} placeholder="UUID (optional)" />
          <Field label="RFI ID" name="rfi_id" value={form.values.rfi_id} onChange={form.setField} placeholder="UUID (optional)" />
        </div>
        <TextArea label="Description" name="description" value={form.values.description} onChange={form.setField} rows={3} />
      </FormDrawer>

      {/* Line Item FormDrawer */}
      <FormDrawer
        open={lineDrawerOpen}
        onClose={() => setLineDrawerOpen(false)}
        title={lineDrawerMode === "create" ? "Add Line Item" : "Edit Line Item"}
        onSubmit={onLineSubmit}
        onReset={lineForm.reset}
        dirty={lineForm.dirty}
        submitting={lineSubmitting}
        error={lineSubmitError}
        mode={lineDrawerMode}
        width={440}
      >
        <Field label="Description" name="description" value={lineForm.values.description} onChange={lineForm.setField} required autoFocus />
        <NumberField label="Amount" name="amount" value={lineForm.values.amount} onChange={lineForm.setField} required />
        <Select
          label="Cost Code"
          name="cost_code_id"
          value={lineForm.values.cost_code_id}
          onChange={lineForm.setField}
          options={costCodes.map(c => ({ value: c.id, label: `${c.code} — ${c.description || c.name || ""}` }))}
        />
        <NumberField label="Sort Order" name="sort_order" value={lineForm.values.sort_order} onChange={lineForm.setField} />
      </FormDrawer>
    </div>
  );
}
