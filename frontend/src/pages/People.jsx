import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { StatCard, Badge, Card, Row } from "../ui";
import { LoadState } from "../fetchState";
import { usePermissions } from "../permissions";
import {
  FormDrawer, useFormState, Field, TextArea, Select, Checkbox,
  WriteButton, cleanPayload,
} from "../forms";

const ROLE_OPTIONS = ["vp", "general_super", "lead_super", "asst_super", "pm", "apm", "accountant", "owner", "architect", "engineer", "subcontractor", "vendor", "inspector", "other"];
const ACCESS_OPTIONS = [
  { value: "read_only", label: "Read only" },
  { value: "field_only", label: "Field only" },
  { value: "field_write", label: "Field write" },
  { value: "full_write", label: "Full write" },
  { value: "admin", label: "Admin" },
];

const PERSON_DEFAULT = {
  first_name: "",
  last_name: "",
  email: "",
  phone: "",
  title: "",
  role_type: "other",
  company_id: null,
  is_active: true,
  notes: "",
};

const MEMBER_DEFAULT = {
  access_level: null,
  role_template_id: null,
  is_primary: false,
  is_active: true,
};

const MEMBER_CREATE_DEFAULT = {
  project_id: null,
  access_level: "read_only",
  role_template_id: null,
  is_primary: false,
  is_active: true,
};

export default function People() {
  const { isAdminOrVp } = usePermissions();

  const [people, setPeople] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState("active");

  const [selected, setSelected] = useState(null);
  const [memberships, setMemberships] = useState(null);
  const [projects, setProjects] = useState([]);

  // Edit drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState("person"); // "person" | "member" | "member-create"
  const [editing, setEditing] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const personForm = useFormState(PERSON_DEFAULT);
  const memberForm = useFormState(MEMBER_DEFAULT);
  const memberCreateForm = useFormState(MEMBER_CREATE_DEFAULT);

  const load = useCallback(() => {
    setError(null);
    Promise.all([
      api("/people/?limit=500"),
      api("/companies/?limit=500"),
      api("/projects/?limit=500"),
    ])
      .then(([p, c, pr]) => { setPeople(p); setCompanies(c); setProjects(pr); })
      .catch((e) => setError(e.message || e));
  }, []);
  useEffect(() => { load(); }, [load]);

  const companyMap = useMemo(() => {
    const m = {};
    (companies || []).forEach((c) => { m[c.id] = c.name; });
    return m;
  }, [companies]);

  const projectMap = useMemo(() => {
    const m = {};
    (projects || []).forEach((p) => { m[p.id] = p.name + (p.project_number ? ` (${p.project_number})` : ""); });
    return m;
  }, [projects]);

  const companyOptions = useMemo(() => (companies || []).map((c) => ({ value: c.id, label: c.name })), [companies]);

  const filtered = useMemo(() => {
    if (!people) return [];
    const q = search.toLowerCase();
    return people.filter((p) => {
      if (roleFilter && p.role_type !== roleFilter) return false;
      if (activeFilter === "active" && !p.is_active) return false;
      if (activeFilter === "inactive" && p.is_active) return false;
      if (!q) return true;
      const name = `${p.first_name || ""} ${p.last_name || ""}`.toLowerCase();
      return name.includes(q) || (p.email || "").toLowerCase().includes(q);
    });
  }, [people, search, roleFilter, activeFilter]);

  const summary = useMemo(() => {
    const list = people || [];
    return {
      total: list.length,
      active: list.filter((p) => p.is_active).length,
      internal: list.filter((p) => ["vp", "general_super", "lead_super", "asst_super", "pm", "apm", "accountant"].includes(p.role_type)).length,
      external: list.filter((p) => !["vp", "general_super", "lead_super", "asst_super", "pm", "apm", "accountant"].includes(p.role_type)).length,
    };
  }, [people]);

  async function selectPerson(row) {
    setSelected(row);
    setMemberships(null);
    try {
      const m = await api(`/project-members/?person_id=${row.id}&limit=100`);
      setMemberships(m);
    } catch (e) {
      setMemberships([]);
      setError(e.message || String(e));
    }
  }

  function openCreatePerson() {
    setDrawerMode("person");
    setEditing(null);
    personForm.setAll({ ...PERSON_DEFAULT });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  function openEditPerson(row) {
    setDrawerMode("person");
    setEditing(row);
    personForm.setAll({
      first_name: row.first_name || "",
      last_name: row.last_name || "",
      email: row.email || "",
      phone: row.phone || "",
      title: row.title || "",
      role_type: row.role_type || "other",
      company_id: row.company_id || null,
      is_active: row.is_active ?? true,
      notes: row.notes || "",
    });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  function openEditMember(member) {
    setDrawerMode("member");
    setEditing(member);
    memberForm.setAll({
      access_level: member.access_level || null,
      role_template_id: member.role_template_id || null,
      is_primary: !!member.is_primary,
      is_active: !!member.is_active,
    });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  function openCreateMember() {
    setDrawerMode("member-create");
    setEditing(null);
    memberCreateForm.setAll({ ...MEMBER_CREATE_DEFAULT });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  async function onCreateMember() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const v = memberCreateForm.values;
      if (!selected?.id) throw new Error("No person selected");
      if (!v.project_id) throw new Error("Please choose a project");
      const payload = {
        project_id: v.project_id,
        person_id: selected.id,
        access_level: v.access_level || null,
        is_primary: !!v.is_primary,
        is_active: !!v.is_active,
      };
      // role_template_id is optional — omit if unset to avoid sending null and
      // letting the backend apply its default.
      if (v.role_template_id) payload.role_template_id = v.role_template_id;
      await api("/project-members/", { method: "POST", body: payload });
      setDrawerOpen(false);
      await selectPerson(selected);
    } catch (e) {
      const msg = e?.message || String(e);
      // Surface the distinctive 409 so the operator knows what's going on.
      if (/409|already|duplicate/i.test(msg)) {
        setSubmitError("This person is already a member of that project.");
      } else {
        setSubmitError(msg);
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function onSubmitPerson() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const payload = cleanPayload(personForm.values, ["is_active"]);
      // is_active is a boolean; cleanPayload drops null/"" so we must re-assert it.
      payload.is_active = personForm.values.is_active;
      if (editing?.id) {
        await api(`/people/${editing.id}`, { method: "PATCH", body: payload });
      } else {
        if (!payload.first_name || !payload.last_name) throw new Error("First and last name are required");
        if (!payload.role_type) throw new Error("Role is required");
        await api(`/people/`, { method: "POST", body: payload });
      }
      setDrawerOpen(false);
      load();
    } catch (e) {
      setSubmitError(e.message || String(e));
    } finally {
      setSubmitting(false);
    }
  }

  async function onSubmitMember() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const payload = cleanPayload(memberForm.values, ["is_primary", "is_active"]);
      payload.is_primary = memberForm.values.is_primary;
      payload.is_active = memberForm.values.is_active;
      await api(`/project-members/${editing.id}`, { method: "PATCH", body: payload });
      setDrawerOpen(false);
      if (selected) await selectPerson(selected);
    } catch (e) {
      setSubmitError(e.message || String(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12, flexWrap: "wrap", gap: 10 }}>
        <h1 className="rex-h1" style={{ margin: 0 }}>People &amp; Project Members</h1>
        {isAdminOrVp && <WriteButton onClick={openCreatePerson}>+ New Person</WriteButton>}
      </div>
      <p className="rex-muted" style={{ marginBottom: 16 }}>Users, subs, and stakeholders. Click a row to see project memberships.</p>

      <LoadState loading={!people && !error} loadingText="Loading people..." error={error} onRetry={load} empty={false}>
        <div className="rex-grid-4" style={{ marginBottom: 18 }}>
          <StatCard label="Total" value={summary.total} />
          <StatCard label="Active" value={summary.active} color="green" />
          <StatCard label="Internal" value={summary.internal} />
          <StatCard label="External" value={summary.external} />
        </div>

        <div className="rex-search-bar">
          <input className="rex-input" placeholder="Search name or email…" value={search} onChange={(e) => setSearch(e.target.value)} style={{ maxWidth: 280 }} />
          <select className="rex-input" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} aria-label="Filter by role">
            <option value="">All roles</option>
            {ROLE_OPTIONS.map((r) => <option key={r} value={r}>{r.replace(/_/g, " ")}</option>)}
          </select>
          <select className="rex-input" value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)} aria-label="Filter by active status">
            <option value="active">Active only</option>
            <option value="inactive">Inactive only</option>
            <option value="">All</option>
          </select>
          <span className="rex-muted">{filtered.length} people</span>
        </div>

        {filtered.length === 0 ? (
          <div className="rex-empty"><div className="rex-empty-icon">◎</div>No people match.</div>
        ) : (
          <div className="rex-table-wrap">
            <div className="rex-table-scroll">
              <table className="rex-table">
                <thead>
                  <tr>
                    <th>Name</th><th>Role</th><th>Title</th><th>Company</th><th>Email</th><th>Phone</th><th>Status</th>
                    {isAdminOrVp && <th aria-label="Actions"></th>}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((p) => (
                    <tr
                      key={p.id}
                      onClick={() => selectPerson(p)}
                      style={{ background: selected?.id === p.id ? "var(--rex-accent-light)" : undefined }}
                    >
                      <td style={{ fontWeight: 600 }}>{p.first_name} {p.last_name}</td>
                      <td>{p.role_type?.replace(/_/g, " ")}</td>
                      <td>{p.title || "—"}</td>
                      <td>{companyMap[p.company_id] || "—"}</td>
                      <td>{p.email || "—"}</td>
                      <td>{p.phone || "—"}</td>
                      <td><Badge status={p.is_active ? "active" : "draft"} label={p.is_active ? "active" : "inactive"} /></td>
                      {isAdminOrVp && (
                        <td style={{ textAlign: "right" }}>
                          <button
                            type="button"
                            className="rex-btn rex-btn-outline"
                            style={{ padding: "4px 10px", fontSize: 11 }}
                            onClick={(e) => { e.stopPropagation(); openEditPerson(p); }}
                            aria-label={`Edit ${p.first_name} ${p.last_name}`}
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

        {selected && (
          <div className="rex-detail-panel">
            <div className="rex-detail-panel-header">
              <div>
                <div className="rex-h3">{selected.first_name} {selected.last_name}</div>
                <div className="rex-muted" style={{ fontSize: 12, marginTop: 2 }}>
                  {selected.role_type?.replace(/_/g, " ")} · {companyMap[selected.company_id] || "no company"}
                </div>
              </div>
              <button className="rex-detail-panel-close" aria-label="Close details" onClick={() => setSelected(null)}>×</button>
            </div>

            <div className="rex-grid-2" style={{ marginBottom: 14 }}>
              <Card title="Contact">
                <Row label="Email" value={selected.email || "—"} />
                <Row label="Phone" value={selected.phone || "—"} />
                <Row label="Title" value={selected.title || "—"} />
              </Card>
              <Card title="Status">
                <Row label="Active" value={selected.is_active ? "Yes" : "No"} />
                <Row label="Company" value={companyMap[selected.company_id] || "—"} />
                <Row label="Role" value={selected.role_type?.replace(/_/g, " ")} />
              </Card>
            </div>

            <Card
              title="Project Memberships"
              action={isAdminOrVp && (
                <button
                  type="button"
                  className="rex-btn rex-btn-outline"
                  style={{ padding: "4px 10px", fontSize: 11 }}
                  onClick={openCreateMember}
                  aria-label={`Add project membership for ${selected.first_name} ${selected.last_name}`}
                >
                  + Add
                </button>
              )}
            >
              {memberships == null ? (
                <p className="rex-muted" style={{ fontSize: 12 }}>Loading…</p>
              ) : memberships.length === 0 ? (
                <p className="rex-muted" style={{ fontSize: 12 }}>No project access assignments.</p>
              ) : (
                <div className="rex-table-scroll">
                  <table className="rex-table" style={{ fontSize: 12 }}>
                    <thead><tr><th>Project</th><th>Access</th><th>Primary</th><th>Active</th>{isAdminOrVp && <th aria-label="Actions"></th>}</tr></thead>
                    <tbody>
                      {memberships.map((m) => (
                        <tr key={m.id}>
                          <td>{projectMap[m.project_id] || m.project_id}</td>
                          <td>{m.access_level || "—"}</td>
                          <td>{m.is_primary ? "Yes" : "—"}</td>
                          <td>{m.is_active ? "Yes" : "No"}</td>
                          {isAdminOrVp && (
                            <td style={{ textAlign: "right" }}>
                              <button
                                type="button"
                                className="rex-btn rex-btn-outline"
                                style={{ padding: "3px 8px", fontSize: 10 }}
                                onClick={() => openEditMember(m)}
                                aria-label={`Edit access for ${projectMap[m.project_id] || "project"}`}
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
              )}
            </Card>
          </div>
        )}
      </LoadState>

      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={
          drawerMode === "person"
            ? (editing ? "Edit Person" : "Create Person")
            : drawerMode === "member-create"
              ? "Add Project Membership"
              : "Edit Project Membership"
        }
        subtitle={
          drawerMode === "person"
            ? (editing ? `${editing.first_name} ${editing.last_name}` : undefined)
            : drawerMode === "member-create"
              ? (selected ? `${selected.first_name} ${selected.last_name}` : undefined)
              : (editing ? projectMap[editing.project_id] : undefined)
        }
        mode={drawerMode === "member-create" ? "create" : editing ? "edit" : "create"}
        onSubmit={
          drawerMode === "person"
            ? onSubmitPerson
            : drawerMode === "member-create"
              ? onCreateMember
              : onSubmitMember
        }
        onReset={
          drawerMode === "person"
            ? personForm.reset
            : drawerMode === "member-create"
              ? memberCreateForm.reset
              : memberForm.reset
        }
        dirty={
          drawerMode === "person"
            ? personForm.dirty
            : drawerMode === "member-create"
              ? memberCreateForm.dirty
              : memberForm.dirty
        }
        submitting={submitting}
        error={submitError}
      >
        {drawerMode === "person" ? (
          <>
            <div className="rex-form-row">
              <Field label="First Name" name="first_name" value={personForm.values.first_name} onChange={personForm.setField} required autoFocus />
              <Field label="Last Name" name="last_name" value={personForm.values.last_name} onChange={personForm.setField} required />
            </div>
            <div className="rex-form-row">
              <Field label="Email" name="email" value={personForm.values.email} onChange={personForm.setField} type="email" />
              <Field label="Phone" name="phone" value={personForm.values.phone} onChange={personForm.setField} />
            </div>
            <div className="rex-form-row">
              <Field label="Title" name="title" value={personForm.values.title} onChange={personForm.setField} />
              <Select label="Role" name="role_type" value={personForm.values.role_type} onChange={personForm.setField} options={ROLE_OPTIONS} required />
            </div>
            <Select label="Company" name="company_id" value={personForm.values.company_id} onChange={personForm.setField} options={companyOptions} placeholder="No company" />
            <Checkbox label="Active" name="is_active" value={personForm.values.is_active} onChange={personForm.setField} />
            <TextArea label="Notes" name="notes" value={personForm.values.notes} onChange={personForm.setField} rows={3} />
          </>
        ) : drawerMode === "member-create" ? (
          <>
            <Select
              label="Project"
              name="project_id"
              value={memberCreateForm.values.project_id}
              onChange={memberCreateForm.setField}
              options={(projects || []).map((p) => ({ value: p.id, label: projectMap[p.id] || p.name }))}
              placeholder="Select a project…"
              required
            />
            <Select
              label="Access Level"
              name="access_level"
              value={memberCreateForm.values.access_level}
              onChange={memberCreateForm.setField}
              options={ACCESS_OPTIONS}
            />
            <Checkbox
              label="Primary contact for this project"
              name="is_primary"
              value={memberCreateForm.values.is_primary}
              onChange={memberCreateForm.setField}
            />
            <Checkbox
              label="Active"
              name="is_active"
              value={memberCreateForm.values.is_active}
              onChange={memberCreateForm.setField}
            />
          </>
        ) : (
          <>
            <Select label="Access Level" name="access_level" value={memberForm.values.access_level} onChange={memberForm.setField} options={ACCESS_OPTIONS} required />
            <Checkbox label="Primary contact for this project" name="is_primary" value={memberForm.values.is_primary} onChange={memberForm.setField} />
            <Checkbox label="Active" name="is_active" value={memberForm.values.is_active} onChange={memberForm.setField} />
          </>
        )}
      </FormDrawer>
    </div>
  );
}
