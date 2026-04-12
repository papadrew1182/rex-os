import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";
import { FormDrawer, useFormState, Field, NumberField, DateField, TextArea, Select, WriteButton, cleanPayload } from "../forms";
import { usePermissions } from "../permissions";
import { FilePreviewDrawer } from "../preview";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";
const fmt = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });

const CERT_DEFAULT = { policy_type: "gl", status: "current" };

export default function InsuranceCertificates() {
  const [certs, setCerts] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState("create");
  const [editing, setEditing] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const form = useFormState(CERT_DEFAULT);
  const { canWrite } = usePermissions();
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewAttachment, setPreviewAttachment] = useState(null);

  async function openCertAttachment() {
    if (!selected?.attachment_id) return;
    try {
      const att = await api(`/attachments/${selected.attachment_id}`);
      setPreviewAttachment(att);
      setPreviewOpen(true);
    } catch (e) {
      alert("Could not load certificate file: " + e.message);
    }
  }

  const refresh = useCallback(() => {
    Promise.all([
      api(`/insurance-certificates?limit=500`).catch(() => []),
      api(`/insurance-certificates/summary`).catch(() => null),
    ]).then(([list, sum]) => {
      setCerts(Array.isArray(list) ? list : []);
      setSummary(sum);
    }).catch(e => setError(e.message));
  }, []);

  useEffect(() => {
    api(`/companies?limit=500`).catch(() => []).then(c => setCompanies(Array.isArray(c) ? c : []));
    refresh();
  }, [refresh]);

  const companyMap = useMemo(() => {
    const m = {};
    companies.forEach(c => { m[c.id] = c.name; });
    return m;
  }, [companies]);

  const companyOptions = useMemo(() => companies.map(c => ({ value: c.id, label: c.name })), [companies]);

  const filtered = useMemo(() => {
    if (!certs) return [];
    const q = search.toLowerCase();
    return certs.filter(c => {
      if (q && !(companyMap[c.company_id] || "").toLowerCase().includes(q) && !(c.carrier || "").toLowerCase().includes(q) && !(c.policy_number || "").toLowerCase().includes(q)) return false;
      if (typeFilter && c.policy_type !== typeFilter) return false;
      if (statusFilter && c.status !== statusFilter) return false;
      return true;
    });
  }, [certs, search, typeFilter, statusFilter, companyMap]);

  function daysToExpiry(d) {
    if (!d) return null;
    return Math.floor((new Date(d + "T00:00:00") - new Date()) / 86400000);
  }

  function expiryColor(d) {
    const days = daysToExpiry(d);
    if (days == null) return "";
    if (days < 0) return "var(--rex-red)";
    if (days <= 30) return "var(--rex-red)";
    if (days <= 90) return "var(--rex-amber)";
    return "";
  }

  function openCreate() {
    setDrawerMode("create");
    setEditing(null);
    form.setAll({ ...CERT_DEFAULT });
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
        await api("/insurance-certificates/", { method: "POST", body: payload });
      } else {
        // eslint-disable-next-line no-unused-vars
        const { company_id, policy_type, ...updateOnly } = payload;
        await api(`/insurance-certificates/${editing.id}`, { method: "PATCH", body: updateOnly });
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

  async function refreshAll() {
    if (!window.confirm("Recompute statuses for all certificates based on expiry dates?")) return;
    try {
      await api("/insurance-certificates/refresh-status", { method: "POST", body: {} });
      refresh();
    } catch (e) {
      setError(e.message);
    }
  }

  if (error) return <Flash type="error" message={error} />;
  if (certs === null) return <PageLoader text="Loading insurance certificates..." />;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <h1 className="rex-h1">Insurance Certificates</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="rex-btn rex-btn-outline" onClick={refreshAll}>Refresh Statuses</button>
          <WriteButton onClick={openCreate}>+ New Certificate</WriteButton>
        </div>
      </div>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Vendor insurance compliance tracking. Status auto-computes from expiry date when refreshed.</p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Certificates" value={summary?.total ?? certs.length} />
        <StatCard label="Current" value={summary?.current ?? 0} color="green" />
        <StatCard label="Expiring (≤60d)" value={summary?.expiring_soon ?? 0} color="amber" />
        <StatCard label="Expired" value={summary?.expired ?? 0} color="red" />
        <StatCard label="Missing" value={summary?.missing ?? 0} color="amber" />
      </div>

      <div className="rex-search-bar">
        <input className="rex-input" placeholder="Search vendor, carrier, policy #..." value={search} onChange={e => setSearch(e.target.value)} style={{ maxWidth: 280 }} />
        <select className="rex-input" value={typeFilter} onChange={e => setTypeFilter(e.target.value)} style={{ width: 170 }}>
          <option value="">All Types</option>
          <option value="gl">General Liability</option>
          <option value="wc">Workers Comp</option>
          <option value="auto">Auto</option>
          <option value="umbrella">Umbrella</option>
          <option value="other">Other</option>
        </select>
        <select className="rex-input" value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ width: 150 }}>
          <option value="">All Statuses</option>
          <option value="current">Current</option>
          <option value="expiring_soon">Expiring Soon</option>
          <option value="expired">Expired</option>
          <option value="missing">Missing</option>
        </select>
        <span className="rex-muted">{filtered.length} record{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No certificates found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Vendor</th>
                <th>Type</th>
                <th>Carrier</th>
                <th>Policy #</th>
                <th>Effective</th>
                <th>Expiry</th>
                <th style={{ textAlign: "right" }}>Limit</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(c => (
                <tr key={c.id} onClick={() => setSelected(selected?.id === c.id ? null : c)}>
                  <td>{companyMap[c.company_id] || "—"}</td>
                  <td><span className="rex-badge rex-badge-gray">{c.policy_type.toUpperCase()}</span></td>
                  <td>{c.carrier || "—"}</td>
                  <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{c.policy_number || "—"}</span></td>
                  <td>{fmtDate(c.effective_date)}</td>
                  <td style={{ color: expiryColor(c.expiry_date), fontWeight: expiryColor(c.expiry_date) ? 600 : 400 }}>{fmtDate(c.expiry_date)}</td>
                  <td style={{ textAlign: "right" }}>{fmt(c.limit_amount)}</td>
                  <td><Badge status={c.status} /></td>
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
              <div className="rex-h3">{companyMap[selected.company_id] || "Vendor"} — {selected.policy_type.toUpperCase()}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8 }}>
                <Badge status={selected.status} />
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {canWrite && <button className="rex-btn rex-btn-outline" onClick={() => openEdit(selected)}>Edit</button>}
              <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>×</button>
            </div>
          </div>
          <div className="rex-grid-3">
            <Card title="Policy">
              <Row label="Type" value={selected.policy_type.toUpperCase()} />
              <Row label="Carrier" value={selected.carrier || "—"} />
              <Row label="Number" value={selected.policy_number || "—"} />
            </Card>
            <Card title="Coverage">
              <Row label="Effective" value={fmtDate(selected.effective_date)} />
              <Row label="Expiry" value={fmtDate(selected.expiry_date)} />
              <Row label="Limit" value={fmt(selected.limit_amount)} />
            </Card>
            <Card title="Compliance">
              <Row label="Status" value={selected.status} />
              <Row label="Days to Expiry" value={daysToExpiry(selected.expiry_date) ?? "—"} />
            </Card>
          </div>
          {selected.attachment_id && (
            <Card title="Certificate File" style={{ marginTop: 12 }}>
              <button className="rex-btn rex-btn-outline" onClick={openCertAttachment} style={{ fontSize: 12 }}>
                Preview Certificate
              </button>
            </Card>
          )}
          {selected.notes && (
            <Card title="Notes" style={{ marginTop: 12 }}>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.notes}</p>
            </Card>
          )}
        </div>
      )}

      <FilePreviewDrawer open={previewOpen} onClose={() => setPreviewOpen(false)} attachment={previewAttachment} />

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerMode === "create" ? "New Insurance Certificate" : "Edit Certificate"}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
        mode={drawerMode}
      >
        <Select label="Vendor" name="company_id" value={form.values.company_id} onChange={form.setField} options={companyOptions} required />
        <div className="rex-form-row">
          <Select label="Policy Type" name="policy_type" value={form.values.policy_type} onChange={form.setField} options={[{ value: "gl", label: "General Liability" }, { value: "wc", label: "Workers Comp" }, { value: "auto", label: "Auto" }, { value: "umbrella", label: "Umbrella" }, { value: "other", label: "Other" }]} required />
          <Select label="Status" name="status" value={form.values.status} onChange={form.setField} options={["current", "expiring_soon", "expired", "missing"]} />
        </div>
        <div className="rex-form-row">
          <Field label="Carrier" name="carrier" value={form.values.carrier} onChange={form.setField} />
          <Field label="Policy Number" name="policy_number" value={form.values.policy_number} onChange={form.setField} />
        </div>
        <div className="rex-form-row">
          <DateField label="Effective Date" name="effective_date" value={form.values.effective_date} onChange={form.setField} />
          <DateField label="Expiry Date" name="expiry_date" value={form.values.expiry_date} onChange={form.setField} />
        </div>
        <NumberField label="Limit Amount" name="limit_amount" value={form.values.limit_amount} onChange={form.setField} />
        <TextArea label="Notes" name="notes" value={form.values.notes} onChange={form.setField} />
      </FormDrawer>
    </div>
  );
}
