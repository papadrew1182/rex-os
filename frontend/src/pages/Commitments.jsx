import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";
import { FormDrawer, useFormState, Field, NumberField, DateField, TextArea, Select, WriteButton, cleanPayload } from "../forms";
import { usePermissions } from "../permissions";

const fmt = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

export default function Commitments() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Commitment drawer state
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
  const [companies, setCompanies] = useState([]);
  const [costCodes, setCostCodes] = useState([]);

  const form = useFormState({});
  const lineForm = useFormState({});
  const { canWrite } = usePermissions();

  const refresh = useCallback(() => {
    if (!selectedId) return;
    api(`/commitments?project_id=${selectedId}&limit=200`).then(setData).catch((e) => setError(e.message));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null); setDetail(null);
    api(`/commitments?project_id=${selectedId}&limit=200`).then(setData).catch((e) => setError(e.message));
  }, [selectedId]);

  // Fetch companies once (global, not project-scoped)
  useEffect(() => {
    api(`/companies?limit=500`).then(c => setCompanies(Array.isArray(c) ? c : [])).catch(() => {});
  }, []);

  // Fetch cost codes when project changes
  useEffect(() => {
    if (!selectedId) return;
    api(`/cost-codes?project_id=${selectedId}&limit=500`).then(c => setCostCodes(Array.isArray(c) ? c : [])).catch(() => {});
  }, [selectedId]);

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.commitments || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q || (r.number || "").toLowerCase().includes(q) || (r.title || "").toLowerCase().includes(q) || (r.vendor_name || "").toLowerCase().includes(q);
      const matchStatus = !statusFilter || r.status === statusFilter;
      const matchType = !typeFilter || r.commitment_type === typeFilter;
      return matchSearch && matchStatus && matchType;
    });
  }, [items, search, statusFilter, typeFilter]);

  const statuses = useMemo(() => [...new Set(items.map((r) => r.status).filter(Boolean))], [items]);
  const types = useMemo(() => [...new Set(items.map((r) => r.commitment_type).filter(Boolean))], [items]);

  const summary = useMemo(() => ({
    total: items.length,
    originalValue: items.reduce((s, r) => s + (r.original_value ?? 0), 0),
    revisedValue: items.reduce((s, r) => s + (r.revised_value ?? 0), 0),
    invoiced: items.reduce((s, r) => s + (r.invoiced_amount ?? 0), 0),
    remaining: items.reduce((s, r) => s + ((r.revised_value ?? 0) - (r.invoiced_amount ?? 0)), 0),
  }), [items]);

  // Refresh detail panel for selected commitment
  const refreshDetail = useCallback((id) => {
    if (!id) return;
    setDetailLoading(true);
    api(`/commitments/${id}/summary`)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }, []);

  // Also refresh line items in detail — detail may embed them or we fetch separately
  const refreshLineItems = useCallback((id) => {
    if (!id) return;
    api(`/commitment-line-items?commitment_id=${id}&limit=200`)
      .then(r => {
        const items = Array.isArray(r) ? r : (r?.items || []);
        setDetail(prev => prev ? { ...prev, line_items: items } : { line_items: items });
      })
      .catch(() => {});
  }, []);

  function handleSelectRow(row) {
    if (selected?.id === row.id) { setSelected(null); setDetail(null); return; }
    setSelected(row);
    setDetail(null);
    setDetailLoading(true);
    api(`/commitments/${row.id}/summary`)
      .then(d => {
        setDetail(d);
        // Also fetch line items
        api(`/commitment-line-items?commitment_id=${row.id}&limit=200`)
          .then(r => {
            const lis = Array.isArray(r) ? r : (r?.items || []);
            setDetail(prev => prev ? { ...prev, line_items: lis } : { line_items: lis });
          })
          .catch(() => {});
      })
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }

  // Commitment drawer handlers
  function openCreate() {
    setDrawerMode("create");
    setEditing(null);
    form.setAll({
      commitment_number: "",
      title: "",
      contract_type: "subcontract",
      status: "draft",
      vendor_id: "",
      original_value: 0,
      retention_rate: 10,
      estimated_completion_date: null,
      executed_date: null,
      scope_of_work: "",
      notes: "",
    });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  function openEdit(row) {
    setDrawerMode("edit");
    setEditing(row);
    form.setAll({
      commitment_number: row.number ?? row.commitment_number ?? "",
      title: row.title ?? "",
      contract_type: row.commitment_type ?? row.contract_type ?? "subcontract",
      status: row.status ?? "draft",
      vendor_id: row.vendor_id ?? "",
      original_value: row.original_value ?? 0,
      retention_rate: row.retention_rate ?? 10,
      estimated_completion_date: row.estimated_completion_date ?? row.completion_date ?? null,
      executed_date: row.executed_date ?? null,
      scope_of_work: row.scope_of_work ?? "",
      notes: row.notes ?? "",
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
        await api("/commitments/", { method: "POST", body: payload });
      } else {
        await api(`/commitments/${editing.id}`, { method: "PATCH", body: payload });
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
      quantity: 1,
      unit: "",
      unit_cost: 0,
      amount: 0,
      cost_code_id: "",
    });
    setLineSubmitError(null);
    setLineDrawerOpen(true);
  }

  function openLineEdit(li) {
    setLineDrawerMode("edit");
    setLineEditing(li);
    lineForm.setAll({
      description: li.description ?? "",
      quantity: li.quantity ?? 1,
      unit: li.unit ?? "",
      unit_cost: li.unit_cost ?? 0,
      amount: li.amount ?? 0,
      cost_code_id: li.cost_code_id ?? "",
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
        payload.commitment_id = selected.id;
        await api("/commitment-line-items/", { method: "POST", body: payload });
      } else {
        await api(`/commitment-line-items/${lineEditing.id}`, { method: "PATCH", body: payload });
      }
      setLineDrawerOpen(false);
      refreshLineItems(selected.id);
    } catch (e) {
      setLineSubmitError(e.message);
    } finally {
      setLineSubmitting(false);
    }
  }

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading commitments..." />;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <h1 className="rex-h1">Commitments</h1>
        <WriteButton onClick={openCreate}>+ New Commitment</WriteButton>
      </div>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Commitments" value={summary.total} />
        <StatCard label="Original Value" value={fmt(summary.originalValue)} />
        <StatCard label="Revised Value" value={fmt(summary.revisedValue)} color="amber" />
        <StatCard label="Invoiced" value={fmt(summary.invoiced)} color="red" />
        <StatCard label="Remaining" value={fmt(summary.remaining)} color="green" />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search number, title, vendor..."
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
        <div className="rex-empty"><div className="rex-empty-icon">📑</div>No commitments found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Number</th>
                <th>Title</th>
                <th>Vendor</th>
                <th>Type</th>
                <th>Status</th>
                <th style={{ textAlign: "right" }}>Original</th>
                <th style={{ textAlign: "right" }}>Approved COs</th>
                <th style={{ textAlign: "right" }}>Revised</th>
                <th style={{ textAlign: "right" }}>Invoiced</th>
                <th style={{ textAlign: "right" }}>Remaining</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr key={row.id || i} onClick={() => handleSelectRow(row)}>
                  <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.number || "—"}</span></td>
                  <td>{row.title || "—"}</td>
                  <td>{row.vendor_name || "—"}</td>
                  <td><span className="rex-muted" style={{ fontSize: 12 }}>{row.commitment_type || "—"}</span></td>
                  <td><Badge status={row.status} /></td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.original_value)}</td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.approved_co_amount)}</td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.revised_value)}</td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.invoiced_amount)}</td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt((row.revised_value ?? 0) - (row.invoiced_amount ?? 0))}</td>
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
              <div className="rex-h3">{selected.number} — {selected.title}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8 }}>
                <Badge status={selected.status} />
                {selected.commitment_type && <span className="rex-badge rex-badge-gray">{selected.commitment_type.replace(/_/g, " ")}</span>}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {canWrite && <button className="rex-btn rex-btn-outline" onClick={() => openEdit(selected)}>Edit</button>}
              <button className="rex-detail-panel-close" onClick={() => { setSelected(null); setDetail(null); }}>×</button>
            </div>
          </div>
          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Details">
              <Row label="Vendor" value={selected.vendor_name || "—"} />
              <Row label="Type" value={selected.commitment_type || "—"} />
              <Row label="Executed Date" value={fmtDate(selected.executed_date)} />
              <Row label="Completion Date" value={fmtDate(selected.completion_date)} />
            </Card>
            <Card title="Financials">
              <Row label="Original Value" value={fmt(selected.original_value)} />
              <Row label="Approved COs" value={fmt(selected.approved_co_amount)} />
              <Row label="Revised Value" value={fmt(selected.revised_value)} />
              <Row label="Invoiced" value={fmt(selected.invoiced_amount)} />
            </Card>
            <Card title="Activity">
              {detailLoading ? <span className="rex-muted">Loading...</span> : detail ? (
                <>
                  <Row label="PCO Count" value={detail.pco_count ?? "—"} />
                  <Row label="CCO Count" value={detail.cco_count ?? "—"} />
                  <Row label="Pay Apps" value={detail.pay_app_count ?? "—"} />
                </>
              ) : <span className="rex-muted">No activity data.</span>}
            </Card>
          </div>
          {selected.scope_of_work && (
            <div style={{ marginBottom: 12 }}>
              <div className="rex-section-label" style={{ marginBottom: 6 }}>Scope of Work</div>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.scope_of_work}</p>
            </div>
          )}
          {selected.notes && (
            <div style={{ marginBottom: 14 }}>
              <div className="rex-section-label" style={{ marginBottom: 6 }}>Notes</div>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.notes}</p>
            </div>
          )}
          <div>
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
                      <th style={{ textAlign: "right" }}>Qty</th>
                      <th>Unit</th>
                      <th style={{ textAlign: "right" }}>Unit Cost</th>
                      <th style={{ textAlign: "right" }}>Amount</th>
                      {canWrite && <th style={{ width: 60 }}></th>}
                    </tr>
                  </thead>
                  <tbody>
                    {detail.line_items.map((li, j) => (
                      <tr key={li.id || j}>
                        <td>{li.description || "—"}</td>
                        <td style={{ textAlign: "right" }}>{li.quantity ?? "—"}</td>
                        <td>{li.unit || "—"}</td>
                        <td style={{ textAlign: "right" }} className="rex-money">{fmt(li.unit_cost)}</td>
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

      {/* Commitment FormDrawer */}
      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerMode === "create" ? "New Commitment" : `Edit — ${form.values.title || ""}`}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
        mode={drawerMode}
        width={560}
      >
        <div className="rex-form-row">
          <Field label="Commitment Number" name="commitment_number" value={form.values.commitment_number} onChange={form.setField} required />
          <Field label="Title" name="title" value={form.values.title} onChange={form.setField} required />
        </div>
        <div className="rex-form-row">
          <Select label="Contract Type" name="contract_type" value={form.values.contract_type} onChange={form.setField} required options={["subcontract","purchase_order","service_agreement"]} />
          <Select label="Status" name="status" value={form.values.status} onChange={form.setField} required options={["draft","out_for_bid","approved","executed","closed","void"]} />
        </div>
        <Select
          label="Vendor"
          name="vendor_id"
          value={form.values.vendor_id}
          onChange={form.setField}
          required
          options={companies.map(c => ({ value: c.id, label: c.name }))}
        />
        <div className="rex-form-row">
          <NumberField label="Original Value" name="original_value" value={form.values.original_value} onChange={form.setField} />
          <NumberField label="Retention Rate (%)" name="retention_rate" value={form.values.retention_rate} onChange={form.setField} />
        </div>
        <div className="rex-form-row">
          <DateField label="Executed Date" name="executed_date" value={form.values.executed_date} onChange={form.setField} />
          <DateField label="Est. Completion Date" name="estimated_completion_date" value={form.values.estimated_completion_date} onChange={form.setField} />
        </div>
        <TextArea label="Scope of Work" name="scope_of_work" value={form.values.scope_of_work} onChange={form.setField} rows={3} />
        <TextArea label="Notes" name="notes" value={form.values.notes} onChange={form.setField} rows={2} />
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
        <Select
          label="Cost Code"
          name="cost_code_id"
          value={lineForm.values.cost_code_id}
          onChange={lineForm.setField}
          options={costCodes.map(c => ({ value: c.id, label: `${c.code} — ${c.description || c.name || ""}` }))}
        />
        <div className="rex-form-row">
          <NumberField label="Quantity" name="quantity" value={lineForm.values.quantity} onChange={lineForm.setField} />
          <Field label="Unit" name="unit" value={lineForm.values.unit} onChange={lineForm.setField} placeholder="e.g. LS, EA, SF" />
        </div>
        <div className="rex-form-row">
          <NumberField label="Unit Cost" name="unit_cost" value={lineForm.values.unit_cost} onChange={lineForm.setField} />
          <NumberField label="Amount" name="amount" value={lineForm.values.amount} onChange={lineForm.setField} required />
        </div>
      </FormDrawer>
    </div>
  );
}
