import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";
import { FormDrawer, useFormState, Field, NumberField, TextArea, Select, WriteButton, cleanPayload } from "../forms";
import { usePermissions } from "../permissions";

const OM_DEFAULT = { status: "pending", required_count: 1, received_count: 0 };

export default function OmManuals() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState("create");
  const [editing, setEditing] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const form = useFormState(OM_DEFAULT);
  const { canWrite } = usePermissions();

  const refresh = useCallback(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null);
    api(`/om-manuals/?project_id=${selectedId}&limit=500`).then(setData).catch(e => setError(e.message));
  }, [selectedId]);

  useEffect(() => { refresh(); }, [refresh]);

  useEffect(() => {
    api(`/companies?limit=500`).catch(() => []).then(c => setCompanies(Array.isArray(c) ? c : []));
  }, []);

  const companyMap = useMemo(() => {
    const m = {};
    companies.forEach(c => { m[c.id] = c.name; });
    return m;
  }, [companies]);

  const companyOptions = useMemo(() => companies.map(c => ({ value: c.id, label: c.name })), [companies]);

  const items = useMemo(() => Array.isArray(data) ? data : [], [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter(r => {
      if (q && !(r.spec_section || "").toLowerCase().includes(q) && !(r.spec_title || "").toLowerCase().includes(q)) return false;
      if (statusFilter && r.status !== statusFilter) return false;
      return true;
    });
  }, [items, search, statusFilter]);

  const summary = useMemo(() => {
    return {
      total: items.length,
      pending: items.filter(r => r.status === "pending").length,
      partial: items.filter(r => r.status === "partial").length,
      received: items.filter(r => r.status === "received").length,
      approved: items.filter(r => r.status === "approved").length,
    };
  }, [items]);

  function openCreate() {
    setDrawerMode("create");
    setEditing(null);
    form.setAll({ ...OM_DEFAULT });
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
        await api("/om-manuals/", { method: "POST", body: { ...payload, project_id: selectedId } });
      } else {
        // eslint-disable-next-line no-unused-vars
        const { project_id, ...updateOnly } = payload;
        await api(`/om-manuals/${editing.id}`, { method: "PATCH", body: updateOnly });
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
  if (!data) return <PageLoader text="Loading O&M manuals..." />;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <h1 className="rex-h1">O&amp;M Manuals</h1>
        <WriteButton onClick={openCreate}>+ New Manual</WriteButton>
      </div>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 20 }}>
        <StatCard label="Total" value={summary.total} />
        <StatCard label="Pending" value={summary.pending} color={summary.pending > 0 ? "amber" : ""} />
        <StatCard label="Partial" value={summary.partial} color={summary.partial > 0 ? "amber" : ""} />
        <StatCard label="Received" value={summary.received} color="green" />
        <StatCard label="Approved" value={summary.approved} color="green" />
      </div>

      <div className="rex-search-bar">
        <input className="rex-input" placeholder="Search section or title..." value={search} onChange={e => setSearch(e.target.value)} style={{ maxWidth: 280 }} />
        <select className="rex-input" value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ width: 150 }}>
          <option value="">All Statuses</option>
          <option value="pending">Pending</option>
          <option value="partial">Partial</option>
          <option value="received">Received</option>
          <option value="approved">Approved</option>
          <option value="n_a">N/A</option>
        </select>
        <span className="rex-muted">{filtered.length} record{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">&#9675;</div>No O&amp;M manuals found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Spec Section</th>
                <th>Title</th>
                <th>Vendor</th>
                <th style={{ textAlign: "right" }}>Required</th>
                <th style={{ textAlign: "right" }}>Received</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr key={row.id || i} onClick={() => setSelected(selected?.id === row.id ? null : row)}>
                  <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.spec_section}</span></td>
                  <td>{row.spec_title || "—"}</td>
                  <td>{companyMap[row.vendor_company_id] || "—"}</td>
                  <td style={{ textAlign: "right" }}>{row.required_count}</td>
                  <td style={{ textAlign: "right", color: row.received_count >= row.required_count ? "var(--rex-green)" : "inherit" }}>{row.received_count}</td>
                  <td><Badge status={row.status} /></td>
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
              <div className="rex-h3">{selected.spec_section} — {selected.spec_title || "O&M Manual"}</div>
              <div style={{ marginTop: 4 }}><Badge status={selected.status} /></div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {canWrite && <button className="rex-btn rex-btn-outline" onClick={() => openEdit(selected)}>Edit</button>}
              <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>&#215;</button>
            </div>
          </div>
          <div className="rex-grid-3">
            <Card title="Spec">
              <Row label="Section" value={selected.spec_section} />
              <Row label="Title" value={selected.spec_title || "—"} />
            </Card>
            <Card title="Counts">
              <Row label="Required" value={selected.required_count} />
              <Row label="Received" value={selected.received_count} />
              <Row label="Status" value={selected.status} />
            </Card>
            <Card title="Vendor">
              <Row label="Company" value={companyMap[selected.vendor_company_id] || "—"} />
            </Card>
          </div>
          {selected.notes && (
            <Card title="Notes" style={{ marginTop: 12 }}>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.notes}</p>
            </Card>
          )}
        </div>
      )}

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerMode === "create" ? "New O&M Manual" : `Edit ${form.values.spec_section || ""}`}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
        mode={drawerMode}
      >
        <Field label="Spec Section" name="spec_section" value={form.values.spec_section} onChange={form.setField} required />
        <Field label="Spec Title" name="spec_title" value={form.values.spec_title} onChange={form.setField} />
        <div className="rex-form-row">
          <NumberField label="Required Count" name="required_count" value={form.values.required_count} onChange={form.setField} step={1} />
          <NumberField label="Received Count" name="received_count" value={form.values.received_count} onChange={form.setField} step={1} />
        </div>
        <Select label="Status" name="status" value={form.values.status} onChange={form.setField} options={["pending", "partial", "received", "approved", "n_a"]} required />
        <Select label="Vendor" name="vendor_company_id" value={form.values.vendor_company_id} onChange={form.setField} options={companyOptions} />
        <TextArea label="Notes" name="notes" value={form.values.notes} onChange={form.setField} />
      </FormDrawer>
    </div>
  );
}
