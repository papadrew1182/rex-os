import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { StatCard, Badge } from "../ui";
import { LoadState } from "../fetchState";
import { usePermissions } from "../permissions";
import {
  FormDrawer, useFormState, Field, NumberField, DateField, TextArea, Select,
  WriteButton, cleanPayload,
} from "../forms";

const COMPANY_TYPE_OPTIONS = ["gc", "subcontractor", "vendor", "architect", "engineer", "owner", "consultant", "other"];
const STATUS_OPTIONS = ["active", "inactive", "pending_qualification"];

const COMPANY_DEFAULT = {
  name: "",
  trade: "",
  company_type: "subcontractor",
  status: "active",
  phone: "",
  mobile_phone: "",
  email: "",
  website: "",
  address_line1: "",
  city: "",
  state: "",
  zip: "",
  license_number: "",
  insurance_carrier: "",
  insurance_expiry: null,
  bonding_capacity: null,
  notes: "",
};

const fmtMoney = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

export default function Companies() {
  const { isAdminOrVp } = usePermissions();
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const form = useFormState(COMPANY_DEFAULT);

  const load = useCallback(() => {
    setError(null);
    api("/companies/?limit=500")
      .then(setRows)
      .catch((e) => setError(e.message || e));
  }, []);
  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    if (!rows) return [];
    const q = search.toLowerCase();
    return rows.filter((r) => {
      if (typeFilter && r.company_type !== typeFilter) return false;
      if (statusFilter && r.status !== statusFilter) return false;
      if (!q) return true;
      return (
        (r.name || "").toLowerCase().includes(q) ||
        (r.trade || "").toLowerCase().includes(q) ||
        (r.email || "").toLowerCase().includes(q) ||
        (r.city || "").toLowerCase().includes(q)
      );
    });
  }, [rows, search, typeFilter, statusFilter]);

  const summary = useMemo(() => {
    const list = rows || [];
    const active = list.filter((r) => r.status === "active").length;
    const today = new Date();
    const in30 = new Date(); in30.setDate(today.getDate() + 30);
    const expSoon = list.filter((r) => {
      if (!r.insurance_expiry) return false;
      const d = new Date(r.insurance_expiry + "T00:00:00");
      return d <= in30;
    }).length;
    const expired = list.filter((r) => {
      if (!r.insurance_expiry) return false;
      return new Date(r.insurance_expiry + "T00:00:00") < today;
    }).length;
    return { total: list.length, active, expSoon, expired };
  }, [rows]);

  function openCreate() {
    setEditing(null);
    form.setAll({ ...COMPANY_DEFAULT });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  function openEdit(row) {
    setEditing(row);
    form.setAll({
      name: row.name || "",
      trade: row.trade || "",
      company_type: row.company_type || "subcontractor",
      status: row.status || "active",
      phone: row.phone || "",
      mobile_phone: row.mobile_phone || "",
      email: row.email || "",
      website: row.website || "",
      address_line1: row.address_line1 || "",
      city: row.city || "",
      state: row.state || "",
      zip: row.zip || "",
      license_number: row.license_number || "",
      insurance_carrier: row.insurance_carrier || "",
      insurance_expiry: row.insurance_expiry || null,
      bonding_capacity: row.bonding_capacity ?? null,
      notes: row.notes || "",
    });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  async function onSubmit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const payload = cleanPayload(form.values);
      if (editing?.id) {
        await api(`/companies/${editing.id}`, { method: "PATCH", body: payload });
      } else {
        if (!payload.name) throw new Error("Name is required");
        if (!payload.company_type) throw new Error("Company Type is required");
        await api(`/companies/`, { method: "POST", body: payload });
      }
      setDrawerOpen(false);
      load();
    } catch (e) {
      setSubmitError(e.message || String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12, flexWrap: "wrap", gap: 10 }}>
        <h1 className="rex-h1" style={{ margin: 0 }}>Companies</h1>
        {isAdminOrVp && <WriteButton onClick={openCreate}>+ New Company</WriteButton>}
      </div>
      <p className="rex-muted" style={{ marginBottom: 16 }}>Subcontractors, vendors, and other parties that touch project work.</p>

      <LoadState loading={!rows && !error} loadingText="Loading companies..." error={error} onRetry={load} empty={false}>
        <div className="rex-grid-4" style={{ marginBottom: 18 }}>
          <StatCard label="Total" value={summary.total} />
          <StatCard label="Active" value={summary.active} color="green" />
          <StatCard label="Insurance Expiring ≤30d" value={summary.expSoon} color="amber" />
          <StatCard label="Insurance Expired" value={summary.expired} color="red" />
        </div>

        <div className="rex-search-bar">
          <input className="rex-input" placeholder="Search name, trade, email, city…" value={search} onChange={(e) => setSearch(e.target.value)} style={{ maxWidth: 300 }} />
          <select className="rex-input" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} aria-label="Filter by type">
            <option value="">All types</option>
            {COMPANY_TYPE_OPTIONS.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
          </select>
          <select className="rex-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Filter by status">
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
          </select>
          <span className="rex-muted">{filtered.length} companies</span>
        </div>

        {filtered.length === 0 ? (
          <div className="rex-empty"><div className="rex-empty-icon">⚑</div>No companies match.</div>
        ) : (
          <div className="rex-table-wrap">
            <div className="rex-table-scroll">
              <table className="rex-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Trade</th>
                    <th>Status</th>
                    <th>Phone</th>
                    <th>Email</th>
                    <th>City</th>
                    <th>Ins. Expiry</th>
                    <th>Bonding</th>
                    {isAdminOrVp && <th aria-label="Actions"></th>}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((c) => (
                    <tr key={c.id} onClick={() => isAdminOrVp && openEdit(c)}>
                      <td style={{ fontWeight: 600 }}>{c.name}</td>
                      <td>{c.company_type?.replace(/_/g, " ")}</td>
                      <td>{c.trade || "—"}</td>
                      <td><Badge status={c.status} /></td>
                      <td>{c.phone || c.mobile_phone || "—"}</td>
                      <td>{c.email || "—"}</td>
                      <td>{c.city || "—"}</td>
                      <td>{fmtDate(c.insurance_expiry)}</td>
                      <td className="rex-money">{fmtMoney(c.bonding_capacity)}</td>
                      {isAdminOrVp && (
                        <td style={{ textAlign: "right" }}>
                          <button
                            type="button"
                            className="rex-btn rex-btn-outline"
                            style={{ padding: "4px 10px", fontSize: 11 }}
                            onClick={(e) => { e.stopPropagation(); openEdit(c); }}
                            aria-label={`Edit ${c.name}`}
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
          </div>
        )}
      </LoadState>

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editing ? "Edit Company" : "Create Company"}
        subtitle={editing?.name}
        mode={editing ? "edit" : "create"}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
        width={560}
      >
        <Field label="Name" name="name" value={form.values.name} onChange={form.setField} required autoFocus />
        <div className="rex-form-row">
          <Select label="Company Type" name="company_type" value={form.values.company_type} onChange={form.setField} options={COMPANY_TYPE_OPTIONS} required />
          <Select label="Status" name="status" value={form.values.status} onChange={form.setField} options={STATUS_OPTIONS} />
          <Field label="Trade" name="trade" value={form.values.trade} onChange={form.setField} placeholder="e.g. Drywall" />
        </div>
        <div className="rex-form-row">
          <Field label="Phone" name="phone" value={form.values.phone} onChange={form.setField} />
          <Field label="Mobile Phone" name="mobile_phone" value={form.values.mobile_phone} onChange={form.setField} />
        </div>
        <div className="rex-form-row">
          <Field label="Email" name="email" value={form.values.email} onChange={form.setField} type="email" />
          <Field label="Website" name="website" value={form.values.website} onChange={form.setField} placeholder="https://" />
        </div>
        <Field label="Address Line 1" name="address_line1" value={form.values.address_line1} onChange={form.setField} />
        <div className="rex-form-row">
          <Field label="City" name="city" value={form.values.city} onChange={form.setField} />
          <Field label="State" name="state" value={form.values.state} onChange={form.setField} />
          <Field label="Zip" name="zip" value={form.values.zip} onChange={form.setField} />
        </div>
        <div className="rex-form-row">
          <Field label="License Number" name="license_number" value={form.values.license_number} onChange={form.setField} />
          <Field label="Insurance Carrier" name="insurance_carrier" value={form.values.insurance_carrier} onChange={form.setField} />
        </div>
        <div className="rex-form-row">
          <DateField label="Insurance Expiry" name="insurance_expiry" value={form.values.insurance_expiry} onChange={form.setField} />
          <NumberField label="Bonding Capacity" name="bonding_capacity" value={form.values.bonding_capacity} onChange={form.setField} step="1000" placeholder="0" />
        </div>
        <TextArea label="Notes" name="notes" value={form.values.notes} onChange={form.setField} rows={3} />
      </FormDrawer>
    </div>
  );
}
