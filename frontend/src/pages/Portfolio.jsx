import { useState, useEffect, useMemo, useCallback } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, PageLoader } from "../ui";
import { LoadState } from "../fetchState";
import { usePermissions } from "../permissions";
import {
  FormDrawer, useFormState, Field, NumberField, DateField, TextArea, Select,
  WriteButton, cleanPayload,
} from "../forms";

const TEST_RE = /^(Test |VF-|WS-|H-Orphan|K-Orphan|Orphan-|SCOPE-|SEC-|ROLLBACK-|SprintE-|Aging-|SubAging-)/i;

const PROJECT_STATUS_OPTIONS = ["active", "on_hold", "closed", "archived"];
const PROJECT_TYPE_OPTIONS = ["retail", "multifamily", "commercial", "mixed_use", "industrial", "other"];

const PROJECT_DEFAULT = {
  name: "",
  project_number: "",
  status: "active",
  project_type: null,
  address_line1: "",
  city: "",
  state: "",
  zip: "",
  start_date: null,
  end_date: null,
  contract_value: null,
  square_footage: null,
  description: "",
  latitude: null,
  longitude: null,
};

export default function Portfolio() {
  const { select } = useProject();
  const { isAdminOrVp } = usePermissions();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [hideTest, setHideTest] = useState(true);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState(null); // null = create
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const form = useFormState(PROJECT_DEFAULT);

  const load = useCallback(() => {
    setError(null);
    api("/closeout-readiness/portfolio?limit=500")
      .then(setData)
      .catch((e) => setError(e.message || e));
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    if (!data) return [];
    let list = data.projects;
    if (hideTest) list = list.filter((p) => !TEST_RE.test(p.project_name) && !TEST_RE.test(p.project_number || ""));
    if (statusFilter) list = list.filter((p) => p.readiness_status === statusFilter);
    if (search) { const q = search.toLowerCase(); list = list.filter((p) => p.project_name.toLowerCase().includes(q) || (p.project_number || "").toLowerCase().includes(q)); }
    return list;
  }, [data, search, statusFilter, hideTest]);

  function openCreate() {
    setEditing(null);
    form.setAll({ ...PROJECT_DEFAULT });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  async function openEditFromRow(row) {
    // Portfolio row doesn't carry all editable fields — fetch the full record.
    setEditing({ id: row.project_id, name: row.project_name });
    setSubmitError(null);
    try {
      const full = await api(`/projects/${row.project_id}`);
      form.setAll({
        name: full.name || "",
        project_number: full.project_number || "",
        status: full.status || "active",
        project_type: full.project_type || null,
        address_line1: full.address_line1 || "",
        city: full.city || "",
        state: full.state || "",
        zip: full.zip || "",
        start_date: full.start_date || null,
        end_date: full.end_date || null,
        contract_value: full.contract_value ?? null,
        square_footage: full.square_footage ?? null,
        description: full.description || "",
        latitude: full.latitude ?? null,
        longitude: full.longitude ?? null,
      });
      setDrawerOpen(true);
    } catch (e) {
      setSubmitError(e.message || String(e));
      setDrawerOpen(true);
    }
  }

  async function onSubmit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const payload = cleanPayload(form.values);
      if (editing?.id) {
        await api(`/projects/${editing.id}`, { method: "PATCH", body: payload });
      } else {
        if (!payload.name) throw new Error("Name is required");
        await api(`/projects/`, { method: "POST", body: payload });
      }
      setDrawerOpen(false);
      setEditing(null);
      load();
    } catch (e) {
      setSubmitError(e.message || String(e));
    } finally {
      setSubmitting(false);
    }
  }

  if (!data && !error) return <PageLoader text="Loading portfolio..." />;
  const summary = data?.summary;

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <h1 className="rex-h1" style={{ margin: 0 }}>Portfolio Closeout Readiness</h1>
        {isAdminOrVp && (
          <WriteButton onClick={openCreate}>+ New Project</WriteButton>
        )}
      </div>

      <LoadState loading={false} error={error} onRetry={load} empty={!data}>
        {data && summary && (
          <>
            <div className="rex-grid-5" style={{ marginBottom: 20 }}>
              <StatCard label="Total" value={summary.total_projects} />
              <StatCard label="Pass" value={summary.pass_count} color="green" />
              <StatCard label="Warning" value={summary.warning_count} color="amber" />
              <StatCard label="Fail" value={summary.fail_count} color="red" />
              <StatCard label="Not Started" value={summary.not_started_count} />
            </div>

            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 14, flexWrap: "wrap" }}>
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search projects..." className="rex-input" style={{ width: 220 }} />
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rex-input">
                <option value="">All statuses</option>
                <option value="pass">Pass</option><option value="warning">Warning</option>
                <option value="fail">Fail</option><option value="not_started">Not Started</option>
              </select>
              <label style={{ fontSize: 13, color: "var(--rex-text-muted)", display: "flex", alignItems: "center", gap: 4, cursor: "pointer" }}>
                <input type="checkbox" checked={hideTest} onChange={(e) => setHideTest(e.target.checked)} /> Hide test
              </label>
              <span className="rex-muted" style={{ marginLeft: "auto" }}>{filtered.length} projects</span>
            </div>

            {filtered.length === 0 ? (
              <p className="rex-muted" style={{ textAlign: "center", padding: "2rem 0" }}>No matching projects.</p>
            ) : (
              <div className="rex-table-wrap">
                <div className="rex-table-scroll">
                  <table className="rex-table">
                    <thead><tr><th>Project</th><th>Status</th><th>Checklist</th><th>Milestones</th><th>Holdback</th><th>Issues</th>{isAdminOrVp && <th aria-label="Actions"></th>}</tr></thead>
                    <tbody>
                      {filtered.map((p) => (
                        <tr key={p.project_id}>
                          <td>
                            <Link to={`/project/${p.project_id}`} onClick={() => select(p.project_id)}
                              style={{ fontWeight: 600, color: "var(--rex-text-bold)" }}>
                              {p.project_name}
                            </Link>
                            {p.project_number && <span className="rex-muted" style={{ marginLeft: 6 }}>{p.project_number}</span>}
                          </td>
                          <td><Badge status={p.readiness_status} /></td>
                          <td>{p.best_checklist_percent?.toFixed(0) ?? "---"}%</td>
                          <td>{p.achieved_milestones}/{p.total_milestones}</td>
                          <td><Badge status={p.holdback_gate_status} /></td>
                          <td>{p.open_issue_count || 0}</td>
                          {isAdminOrVp && (
                            <td style={{ textAlign: "right" }}>
                              <button
                                type="button"
                                className="rex-btn rex-btn-outline"
                                style={{ padding: "4px 10px", fontSize: 11 }}
                                onClick={() => openEditFromRow(p)}
                                aria-label={`Edit ${p.project_name}`}
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
          </>
        )}
      </LoadState>

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={editing ? "Edit Project" : "Create Project"}
        subtitle={editing?.name}
        mode={editing ? "edit" : "create"}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
      >
        <Field label="Name" name="name" value={form.values.name} onChange={form.setField} required autoFocus />
        <Field label="Project Number" name="project_number" value={form.values.project_number} onChange={form.setField} />
        <div className="rex-form-row">
          <Select label="Status" name="status" value={form.values.status} onChange={form.setField} options={PROJECT_STATUS_OPTIONS} />
          <Select label="Project Type" name="project_type" value={form.values.project_type} onChange={form.setField} options={PROJECT_TYPE_OPTIONS} placeholder="Unset" />
        </div>
        <Field label="Address Line 1" name="address_line1" value={form.values.address_line1} onChange={form.setField} />
        <div className="rex-form-row">
          <Field label="City" name="city" value={form.values.city} onChange={form.setField} />
          <Field label="State" name="state" value={form.values.state} onChange={form.setField} />
          <Field label="Zip" name="zip" value={form.values.zip} onChange={form.setField} />
        </div>
        <div className="rex-form-row">
          <DateField label="Start Date" name="start_date" value={form.values.start_date} onChange={form.setField} />
          <DateField label="End Date" name="end_date" value={form.values.end_date} onChange={form.setField} />
        </div>
        <div className="rex-form-row">
          <NumberField label="Contract Value" name="contract_value" value={form.values.contract_value} onChange={form.setField} step="0.01" placeholder="0.00" />
          <NumberField label="Square Footage" name="square_footage" value={form.values.square_footage} onChange={form.setField} step="1" />
        </div>
        <div className="rex-form-row">
          <NumberField label="Latitude" name="latitude" value={form.values.latitude} onChange={form.setField} step="0.000001" />
          <NumberField label="Longitude" name="longitude" value={form.values.longitude} onChange={form.setField} step="0.000001" />
        </div>
        <TextArea label="Description" name="description" value={form.values.description} onChange={form.setField} rows={3} />
      </FormDrawer>
    </div>
  );
}
