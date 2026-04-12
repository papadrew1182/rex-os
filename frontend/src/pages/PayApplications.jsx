import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";
import { FormDrawer, useFormState, Field, NumberField, DateField, Select, WriteButton, cleanPayload } from "../forms";
import { usePermissions } from "../permissions";

const fmt = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

export default function PayApplications() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState(null);

  // Drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState("create");
  const [editing, setEditing] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [commitments, setCommitments] = useState([]);
  const [billingPeriods, setBillingPeriods] = useState([]);

  const form = useFormState({});
  const { canWrite } = usePermissions();

  const refresh = useCallback(() => {
    if (!selectedId) return;
    api(`/projects/${selectedId}/pay-app-summary`).then(setData).catch((e) => setError(e.message));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null);
    api(`/projects/${selectedId}/pay-app-summary`).then(setData).catch((e) => setError(e.message));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    Promise.all([
      api(`/commitments?project_id=${selectedId}&limit=200`),
      api(`/billing-periods?project_id=${selectedId}&limit=100`),
    ]).then(([c, b]) => {
      setCommitments(Array.isArray(c) ? c : []);
      setBillingPeriods(Array.isArray(b) ? b : []);
    }).catch(() => {});
  }, [selectedId]);

  const filtered = useMemo(() => {
    if (!data?.pay_apps) return [];
    const q = search.toLowerCase();
    return data.pay_apps.filter((r) => {
      const matchSearch = !q || (r.number || "").toString().toLowerCase().includes(q) || (r.vendor_name || "").toLowerCase().includes(q);
      const matchStatus = !statusFilter || r.status === statusFilter;
      return matchSearch && matchStatus;
    });
  }, [data, search, statusFilter]);

  const statuses = useMemo(() => {
    if (!data?.pay_apps) return [];
    return [...new Set(data.pay_apps.map((r) => r.status).filter(Boolean))];
  }, [data]);

  function openCreate() {
    setDrawerMode("create");
    setEditing(null);
    form.setAll({
      pay_app_number: "",
      status: "draft",
      period_start: null,
      period_end: null,
      this_period_amount: 0,
      total_completed: 0,
      retention_held: 0,
      retention_released: 0,
      net_payment_due: 0,
      commitment_id: "",
      billing_period_id: "",
    });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  function openEdit(row) {
    setDrawerMode("edit");
    setEditing(row);
    form.setAll({
      pay_app_number: row.pay_app_number ?? row.number,
      status: row.status,
      period_start: row.period_start,
      period_end: row.period_end,
      this_period_amount: row.this_period_amount,
      total_completed: row.total_completed_amount ?? row.total_completed,
      retention_held: row.retention_amount ?? row.retention_held,
      retention_released: row.retention_released,
      net_payment_due: row.net_due ?? row.net_payment_due,
      commitment_id: row.commitment_id,
      billing_period_id: row.billing_period_id,
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
        await api("/payment-applications/", { method: "POST", body: payload });
      } else {
        const { commitment_id, billing_period_id, pay_app_number, ...updateOnly } = payload;
        await api(`/payment-applications/${editing.id}`, { method: "PATCH", body: updateOnly });
      }
      setDrawerOpen(false);
      refresh();
    } catch (e) {
      setSubmitError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading pay applications..." />;

  const summary = data.summary || {};

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <h1 className="rex-h1">Pay Applications</h1>
        <WriteButton onClick={openCreate}>+ New Pay App</WriteButton>
      </div>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Pay Apps" value={summary.total_count ?? (data.pay_apps?.length || 0)} />
        <StatCard label="This Period" value={fmt(summary.this_period_amount)} color="amber" />
        <StatCard label="Total Completed" value={fmt(summary.total_completed)} color="green" />
        <StatCard label="Retention Held" value={fmt(summary.retention_held)} color="red" />
        <StatCard label="Net Due" value={fmt(summary.net_due)} />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search pay app # or vendor..."
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
        <div className="rex-empty"><div className="rex-empty-icon">📄</div>No pay applications found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Pay App #</th>
                <th>Vendor</th>
                <th>Status</th>
                <th>Period</th>
                <th style={{ textAlign: "right" }}>This Period</th>
                <th style={{ textAlign: "right" }}>Total Completed</th>
                <th style={{ textAlign: "right" }}>Retention</th>
                <th style={{ textAlign: "right" }}>Net Due</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr key={row.id || i} onClick={() => setSelected(selected?.id === row.id ? null : row)}>
                  <td><strong>{row.number || "—"}</strong></td>
                  <td>{row.vendor_name || "—"}</td>
                  <td><Badge status={row.status} /></td>
                  <td>{fmtDate(row.period_start)}{row.period_end ? ` – ${fmtDate(row.period_end)}` : ""}</td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.this_period_amount)}</td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.total_completed_amount)}</td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.retention_amount)}</td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.net_due)}</td>
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
              <div className="rex-h3">Pay App #{selected.number} — {selected.vendor_name}</div>
              <div style={{ marginTop: 4 }}><Badge status={selected.status} /></div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {canWrite && <button className="rex-btn rex-btn-outline" onClick={() => openEdit(selected)}>Edit</button>}
              <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>×</button>
            </div>
          </div>
          <div className="rex-grid-2">
            <Card title="Payment Details">
              <Row label="Period Start" value={fmtDate(selected.period_start)} />
              <Row label="Period End" value={fmtDate(selected.period_end)} />
              <Row label="Invoice Date" value={fmtDate(selected.invoice_date)} />
              <Row label="Due Date" value={fmtDate(selected.due_date)} />
            </Card>
            <Card title="Amounts">
              <Row label="This Period" value={fmt(selected.this_period_amount)} />
              <Row label="Total Completed" value={fmt(selected.total_completed_amount)} />
              <Row label="Retention" value={fmt(selected.retention_amount)} />
              <Row label="Net Due" value={fmt(selected.net_due)} />
            </Card>
          </div>
          {(selected.lien_waiver_status || selected.lien_waiver_received != null) && (
            <Card title="Lien Waiver" style={{ marginTop: 12 }}>
              <Row label="Status" value={<Badge status={selected.lien_waiver_status} />} />
              <Row label="Received" value={selected.lien_waiver_received ? "Yes" : "No"} />
              {selected.lien_waiver_date && <Row label="Date" value={fmtDate(selected.lien_waiver_date)} />}
            </Card>
          )}
          {selected.description && (
            <div style={{ marginTop: 12 }}>
              <div className="rex-section-label" style={{ marginBottom: 6 }}>Description</div>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.description}</p>
            </div>
          )}
        </div>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerMode === "create" ? "New Pay Application" : `Edit Pay App #${form.values.pay_app_number || ""}`}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
        mode={drawerMode}
      >
        <div className="rex-form-row">
          <Field label="Pay App Number" name="pay_app_number" value={form.values.pay_app_number} onChange={form.setField} required />
          <Select label="Status" name="status" value={form.values.status} onChange={form.setField} required options={["draft","submitted","under_review","approved","paid","rejected"]} />
        </div>
        {drawerMode === "create" && (
          <div className="rex-form-row">
            <Select label="Commitment" name="commitment_id" value={form.values.commitment_id} onChange={form.setField} required options={commitments.map(c => ({ value: c.id, label: `${c.commitment_number || c.number} — ${c.title}` }))} />
            <Select label="Billing Period" name="billing_period_id" value={form.values.billing_period_id} onChange={form.setField} required options={billingPeriods.map(b => ({ value: b.id, label: `Period ${b.period_number} (${b.start_date} → ${b.end_date})` }))} />
          </div>
        )}
        <div className="rex-form-row">
          <DateField label="Period Start" name="period_start" value={form.values.period_start} onChange={form.setField} required />
          <DateField label="Period End" name="period_end" value={form.values.period_end} onChange={form.setField} required />
        </div>
        <div className="rex-form-row">
          <NumberField label="This Period Amount" name="this_period_amount" value={form.values.this_period_amount} onChange={form.setField} />
          <NumberField label="Total Completed" name="total_completed" value={form.values.total_completed} onChange={form.setField} />
        </div>
        <div className="rex-form-row">
          <NumberField label="Retention Held" name="retention_held" value={form.values.retention_held} onChange={form.setField} />
          <NumberField label="Retention Released" name="retention_released" value={form.values.retention_released} onChange={form.setField} />
        </div>
        <NumberField label="Net Payment Due" name="net_payment_due" value={form.values.net_payment_due} onChange={form.setField} />
      </FormDrawer>
    </div>
  );
}
