import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";
import { AlertCallout } from "../AlertCallout";
import {
  FormDrawer, useFormState,
  Field, NumberField, DateField, TextArea, Select, Checkbox, WriteButton, cleanPayload,
} from "../forms";
import { usePermissions } from "../permissions";
import { FilePreviewDrawer } from "../preview";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

const WARRANTY_DEFAULT = {
  scope_description: "",
  system_or_product: "",
  manufacturer: "",
  warranty_type: "standard",
  company_id: null,
  duration_months: null,
  start_date: null,
  expiration_date: null,
  cost_code_id: null,
  status: "active",
  is_letter_received: false,
  is_om_received: false,
  notes: "",
};

const WARRANTY_TYPE_OPTIONS = [
  { value: "standard", label: "Standard" },
  { value: "extended", label: "Extended" },
  { value: "manufacturer", label: "Manufacturer" },
  { value: "labor_only", label: "Labor Only" },
  { value: "material_only", label: "Material Only" },
];

const STATUS_OPTIONS = [
  { value: "active", label: "Active" },
  { value: "expiring_soon", label: "Expiring Soon" },
  { value: "expired", label: "Expired" },
  { value: "claimed", label: "Claimed" },
];

function daysToExpiry(d) {
  if (!d) return null;
  return Math.floor((new Date(d + "T00:00:00") - new Date()) / 86400000);
}

function expiryColor(d) {
  const days = daysToExpiry(d);
  if (days == null) return "";
  if (days < 0) return "var(--rex-red)";
  if (days <= 60) return "var(--rex-amber)";
  return "";
}

export default function Warranties() {
  const { selected: project, selectedId } = useProject();
  const { canWrite } = usePermissions();

  const [data, setData] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [costCodes, setCostCodes] = useState([]);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [claims, setClaims] = useState(null);
  const [alerts, setAlerts] = useState(null);
  const [warrantyAttachments, setWarrantyAttachments] = useState([]);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewAttachment, setPreviewAttachment] = useState(null);

  function openPreview(attachment) { setPreviewAttachment(attachment); setPreviewOpen(true); }

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState("create");
  const [editing, setEditing] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  const form = useFormState(WARRANTY_DEFAULT);

  const refresh = useCallback(() => {
    if (!selectedId) return;
    api(`/warranties?project_id=${selectedId}&limit=200`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null); setClaims(null); setAlerts(null);
    refresh();
  }, [selectedId, refresh]);

  useEffect(() => {
    if (!selectedId) return;
    Promise.all([
      api(`/companies?limit=500`).catch(() => []),
      api(`/cost-codes?project_id=${selectedId}&limit=500`).catch(() => []),
    ]).then(([c, cc]) => {
      setCompanies(Array.isArray(c) ? c : []);
      setCostCodes(Array.isArray(cc) ? cc : []);
    });
  }, [selectedId]);

  const companyMap = useMemo(() => {
    const m = {};
    companies.forEach((c) => { m[c.id] = c.name; });
    return m;
  }, [companies]);

  const costCodeMap = useMemo(() => {
    const m = {};
    costCodes.forEach((cc) => { m[cc.id] = `${cc.code} — ${cc.name}`; });
    return m;
  }, [costCodes]);

  const companyOptions = useMemo(() => companies.map((c) => ({ value: c.id, label: c.name })), [companies]);
  const costCodeOptions = useMemo(() => costCodes.map((cc) => ({ value: cc.id, label: `${cc.code} — ${cc.name}` })), [costCodes]);

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.warranties || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q
        || (r.scope_description || "").toLowerCase().includes(q)
        || (r.system_or_product || "").toLowerCase().includes(q)
        || (r.manufacturer || "").toLowerCase().includes(q);
      const matchType = !typeFilter || r.warranty_type === typeFilter;
      const matchStatus = !statusFilter || r.status === statusFilter;
      return matchSearch && matchType && matchStatus;
    });
  }, [items, search, typeFilter, statusFilter]);

  const summary = useMemo(() => ({
    total: items.length,
    active: items.filter((r) => r.status === "active").length,
    expiring_soon: items.filter((r) => r.status === "expiring_soon").length,
    expired: items.filter((r) => r.status === "expired").length,
    claimed: items.filter((r) => r.status === "claimed").length,
  }), [items]);

  function handleRowClick(row) {
    if (selected?.id === row.id) { setSelected(null); setClaims(null); setAlerts(null); setWarrantyAttachments([]); return; }
    setSelected(row);
    setClaims(null);
    setAlerts(null);
    setWarrantyAttachments([]);
    api(`/warranty-claims?warranty_id=${row.id}`).then(setClaims).catch(() => setClaims([]));
    api(`/warranty-alerts?warranty_id=${row.id}`).then(setAlerts).catch(() => setAlerts([]));
    api(`/attachments?source_type=warranty&source_id=${row.id}`).catch(() => []).then((atts) => setWarrantyAttachments(Array.isArray(atts) ? atts : (atts?.items || [])));
  }

  function openCreate() {
    setDrawerMode("create");
    setEditing(null);
    form.setAll({ ...WARRANTY_DEFAULT });
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
        await api("/warranties/", { method: "POST", body: { ...payload, project_id: selectedId } });
      } else {
        // eslint-disable-next-line no-unused-vars
        const { project_id, company_id, ...updateOnly } = payload;
        await api(`/warranties/${editing.id}`, { method: "PATCH", body: updateOnly });
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
  if (!data) return <PageLoader text="Loading warranties..." />;

  const claimList = Array.isArray(claims) ? claims : (claims?.items || []);
  const alertList = Array.isArray(alerts) ? alerts : (alerts?.items || []);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <h1 className="rex-h1">Warranties</h1>
        <WriteButton onClick={openCreate}>+ New Warranty</WriteButton>
      </div>
      <p className="rex-muted" style={{ marginBottom: 12 }}>
        Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong>
      </p>
      <AlertCallout notificationTypes={["warranty_expiry"]} title="Active alerts on this project" />

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Warranties" value={summary.total} />
        <StatCard label="Active" value={summary.active} color="green" />
        <StatCard label="Expiring Soon" value={summary.expiring_soon} color="amber" />
        <StatCard label="Expired" value={summary.expired} color="red" />
        <StatCard label="Claimed" value={summary.claimed} />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search scope, system/product, manufacturer..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 300 }}
        />
        <select className="rex-input" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} style={{ width: 170 }}>
          <option value="">All Types</option>
          {WARRANTY_TYPE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <select className="rex-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: 150 }}>
          <option value="">All Statuses</option>
          {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <span className="rex-muted">{filtered.length} record{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No warranties found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Scope</th>
                <th>System / Product</th>
                <th>Manufacturer</th>
                <th>Type</th>
                <th>Vendor</th>
                <th>Start Date</th>
                <th>Expiration</th>
                <th>Duration</th>
                <th>Status</th>
                <th>Letter</th>
                <th>O&amp;M</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => {
                const color = expiryColor(row.expiration_date);
                return (
                  <tr key={row.id || i} onClick={() => handleRowClick(row)}>
                    <td style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {row.scope_description || "—"}
                    </td>
                    <td>{row.system_or_product || "—"}</td>
                    <td>{row.manufacturer || "—"}</td>
                    <td>
                      {row.warranty_type
                        ? <span className="rex-badge rex-badge-gray">{row.warranty_type.replace(/_/g, " ")}</span>
                        : "—"}
                    </td>
                    <td>{companyMap[row.company_id] || "—"}</td>
                    <td>{fmtDate(row.start_date)}</td>
                    <td style={{ color, fontWeight: color ? 600 : 400 }}>{fmtDate(row.expiration_date)}</td>
                    <td>{row.duration_months != null ? `${row.duration_months}mo` : "—"}</td>
                    <td><Badge status={row.status} /></td>
                    <td style={{ color: row.is_letter_received ? "var(--rex-green)" : "var(--rex-text-muted)" }}>
                      {row.is_letter_received ? "✓" : "—"}
                    </td>
                    <td style={{ color: row.is_om_received ? "var(--rex-green)" : "var(--rex-text-muted)" }}>
                      {row.is_om_received ? "✓" : "—"}
                    </td>
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
              <div className="rex-h3">{selected.scope_description || "Warranty"}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Badge status={selected.status} />
                {selected.warranty_type && (
                  <span className="rex-badge rex-badge-gray">{selected.warranty_type.replace(/_/g, " ")}</span>
                )}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {canWrite && (
                <button className="rex-btn rex-btn-outline" onClick={() => openEdit(selected)}>Edit</button>
              )}
              <button className="rex-detail-panel-close" onClick={() => { setSelected(null); setClaims(null); setAlerts(null); }}>×</button>
            </div>
          </div>

          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Warranty Info">
              <Row label="Scope" value={selected.scope_description || "—"} />
              <Row label="System / Product" value={selected.system_or_product || "—"} />
              <Row label="Manufacturer" value={selected.manufacturer || "—"} />
              <Row label="Type" value={selected.warranty_type?.replace(/_/g, " ") || "—"} />
              <Row label="Vendor" value={companyMap[selected.company_id] || "—"} />
              <Row label="Cost Code" value={costCodeMap[selected.cost_code_id] || "—"} />
            </Card>
            <Card title="Dates">
              <Row label="Start Date" value={fmtDate(selected.start_date)} />
              <Row label="Expiration" value={fmtDate(selected.expiration_date)} />
              <Row label="Duration" value={selected.duration_months != null ? `${selected.duration_months} months` : "—"} />
            </Card>
            <Card title="Documents">
              <Row label="Letter Received" value={selected.is_letter_received ? "Yes" : "No"} />
              <Row label="O&M Received" value={selected.is_om_received ? "Yes" : "No"} />
            </Card>
          </div>

          <Card title={`Claims (${claimList.length})`} style={{ marginBottom: 12 }}>
            {claims === null ? (
              <p className="rex-muted" style={{ fontSize: 12, margin: 0 }}>Loading claims...</p>
            ) : claimList.length === 0 ? (
              <p className="rex-muted" style={{ fontSize: 12, margin: 0 }}>No claims on record.</p>
            ) : (
              <div className="rex-table-wrap" style={{ marginTop: 8 }}>
                <table className="rex-table">
                  <thead>
                    <tr>
                      <th>Claim #</th>
                      <th>Title</th>
                      <th>Status</th>
                      <th>Reported</th>
                    </tr>
                  </thead>
                  <tbody>
                    {claimList.map((cl, i) => (
                      <tr key={cl.id || i}>
                        <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{cl.claim_number || "—"}</span></td>
                        <td>{cl.title || "—"}</td>
                        <td><Badge status={cl.status} /></td>
                        <td>{fmtDate(cl.reported_date)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card title={`Alerts (${alertList.length})`} style={{ marginBottom: 12 }}>
            {alerts === null ? (
              <p className="rex-muted" style={{ fontSize: 12, margin: 0 }}>Loading alerts...</p>
            ) : alertList.length === 0 ? (
              <p className="rex-muted" style={{ fontSize: 12, margin: 0 }}>No alerts.</p>
            ) : (
              <ul style={{ margin: 0, paddingLeft: 16, fontSize: 13 }}>
                {alertList.map((al, i) => (
                  <li key={al.id || i} style={{ marginBottom: 4, color: "var(--rex-text-muted)" }}>
                    {al.message || al.title || al.alert_type || "Alert"}{al.alert_date ? ` — ${fmtDate(al.alert_date)}` : ""}
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {warrantyAttachments.length > 0 && (
            <Card title={`Attachments (${warrantyAttachments.length})`} style={{ marginBottom: 12 }}>
              <div className="rex-table-wrap" style={{ marginTop: 8 }}>
                <table className="rex-table">
                  <thead>
                    <tr>
                      <th>Filename</th>
                      <th style={{ textAlign: "right" }}>Size</th>
                      <th>Type</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {warrantyAttachments.map((att, i) => (
                      <tr key={att.id || i}>
                        <td>{att.filename || "—"}</td>
                        <td style={{ textAlign: "right" }}>
                          {att.file_size != null
                            ? att.file_size >= 1048576
                              ? `${(att.file_size / 1048576).toFixed(1)} MB`
                              : `${(att.file_size / 1024).toFixed(1)} KB`
                            : "—"}
                        </td>
                        <td>{att.content_type || "—"}</td>
                        <td>
                          <button className="rex-btn rex-btn-outline" onClick={(e) => { e.stopPropagation(); openPreview(att); }} style={{ padding: "2px 8px", fontSize: 12 }}>Preview</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {selected.notes && (
            <Card title="Notes">
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.notes}</p>
            </Card>
          )}
        </div>
      )}

      <FilePreviewDrawer open={previewOpen} onClose={() => setPreviewOpen(false)} attachment={previewAttachment} />

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerMode === "create" ? "New Warranty" : "Edit Warranty"}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
        mode={drawerMode}
      >
        <Field label="Scope Description" name="scope_description" value={form.values.scope_description} onChange={form.setField} required />
        <div className="rex-form-row">
          <Field label="System / Product" name="system_or_product" value={form.values.system_or_product} onChange={form.setField} />
          <Field label="Manufacturer" name="manufacturer" value={form.values.manufacturer} onChange={form.setField} />
        </div>
        <div className="rex-form-row">
          <Select label="Warranty Type" name="warranty_type" value={form.values.warranty_type} onChange={form.setField} options={WARRANTY_TYPE_OPTIONS} required />
          <Select label="Vendor" name="company_id" value={form.values.company_id} onChange={form.setField} options={companyOptions} required />
        </div>
        <div className="rex-form-row">
          <NumberField label="Duration (months)" name="duration_months" value={form.values.duration_months} onChange={form.setField} required step={1} />
          <DateField label="Start Date" name="start_date" value={form.values.start_date} onChange={form.setField} required />
        </div>
        <div className="rex-form-row">
          <DateField label="Expiration Date" name="expiration_date" value={form.values.expiration_date} onChange={form.setField} />
          <Select label="Cost Code" name="cost_code_id" value={form.values.cost_code_id} onChange={form.setField} options={costCodeOptions} />
        </div>
        <Select label="Status" name="status" value={form.values.status} onChange={form.setField} options={STATUS_OPTIONS} />
        <div className="rex-form-row">
          <Checkbox label="Letter Received" name="is_letter_received" value={form.values.is_letter_received} onChange={form.setField} />
          <Checkbox label="O&M Received" name="is_om_received" value={form.values.is_om_received} onChange={form.setField} />
        </div>
        <TextArea label="Notes" name="notes" value={form.values.notes} onChange={form.setField} />
      </FormDrawer>
    </div>
  );
}
