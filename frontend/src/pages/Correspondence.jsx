import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";
import {
  FormDrawer, useFormState, Field, DateField, TextArea, Select,
  WriteButton, cleanPayload,
} from "../forms";
import { usePermissions } from "../permissions";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

const CORR_DEFAULT = {
  correspondence_number: "",
  subject: "",
  correspondence_type: null,
  status: "draft",
  from_person_id: null,
  to_person_id: null,
  sent_date: null,
  received_date: null,
  body: "",
};

const CORR_TYPES = [
  { value: "letter", label: "Letter" },
  { value: "email", label: "Email" },
  { value: "memo", label: "Memo" },
  { value: "notice", label: "Notice" },
  { value: "transmittal", label: "Transmittal" },
];

const STATUSES = [
  { value: "draft", label: "Draft" },
  { value: "sent", label: "Sent" },
  { value: "received", label: "Received" },
  { value: "closed", label: "Closed" },
];

export default function Correspondence() {
  const { selected: project, selectedId } = useProject();
  const { canWrite } = usePermissions();

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [attachments, setAttachments] = useState(null);

  // People for from/to selects
  const [people, setPeople] = useState([]);
  useEffect(() => {
    api(`/people?limit=500`).catch(() => []).then((p) => setPeople(Array.isArray(p) ? p : []));
  }, []);
  const peopleOptions = useMemo(
    () => people.map((p) => ({ value: p.id, label: `${p.first_name} ${p.last_name}` })),
    [people],
  );

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState("create");
  const [editing, setEditing] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const form = useFormState(CORR_DEFAULT);

  const refresh = useCallback(() => {
    if (!selectedId) return;
    api(`/correspondence?project_id=${selectedId}&limit=200`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null); setAttachments(null);
    refresh();
  }, [selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleRowClick(row) {
    if (selected?.id === row.id) { setSelected(null); setAttachments(null); return; }
    setSelected(row);
    setAttachments(null);
    api(`/attachments?source_type=correspondence&source_id=${row.id}`)
      .then(setAttachments)
      .catch(() => setAttachments([]));
  }

  function openCreate() {
    setDrawerMode("create");
    setEditing(null);
    form.setAll({ ...CORR_DEFAULT });
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
        await api("/correspondence/", { method: "POST", body: { ...payload, project_id: selectedId } });
      } else {
        const { project_id, ...updateOnly } = payload;
        await api(`/correspondence/${editing.id}`, { method: "PATCH", body: updateOnly });
      }
      setDrawerOpen(false);
      refresh();
    } catch (e) {
      setSubmitError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.correspondence || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q
        || (r.subject || "").toLowerCase().includes(q)
        || (r.correspondence_number || "").toLowerCase().includes(q);
      const matchType = !typeFilter || r.correspondence_type === typeFilter;
      const matchStatus = !statusFilter || r.status === statusFilter;
      return matchSearch && matchType && matchStatus;
    });
  }, [items, search, typeFilter, statusFilter]);

  const types = useMemo(() => [...new Set(items.map((r) => r.correspondence_type).filter(Boolean))].sort(), [items]);
  const statuses = useMemo(() => [...new Set(items.map((r) => r.status).filter(Boolean))].sort(), [items]);

  const summary = useMemo(() => {
    const sent = items.filter((r) => r.status === "sent").length;
    const received = items.filter((r) => r.status === "received").length;
    const drafts = items.filter((r) => r.status === "draft").length;
    const closed = items.filter((r) => r.status === "closed").length;
    return { total: items.length, sent, received, drafts, closed };
  }, [items]);

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading correspondence..." />;

  const attList = Array.isArray(attachments) ? attachments : (attachments?.items || []);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <h1 className="rex-h1">Correspondence Log</h1>
        <WriteButton onClick={openCreate}>+ New</WriteButton>
      </div>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Correspondence" value={summary.total} />
        <StatCard label="Sent" value={summary.sent} color="green" />
        <StatCard label="Received" value={summary.received} />
        <StatCard label="Drafts" value={summary.drafts} color={summary.drafts > 0 ? "amber" : ""} />
        <StatCard label="Closed" value={summary.closed} />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search subject or number..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 260 }}
        />
        <select className="rex-input" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} style={{ width: 160 }}>
          <option value="">All Types</option>
          {types.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
        </select>
        <select className="rex-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: 150 }}>
          <option value="">All Statuses</option>
          {statuses.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <span className="rex-muted">{filtered.length} record{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">✉</div>No correspondence found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Number</th>
                <th>Subject</th>
                <th>Type</th>
                <th>Status</th>
                <th>From</th>
                <th>To</th>
                <th>Sent</th>
                <th>Received</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr key={row.id || i} onClick={() => handleRowClick(row)}>
                  <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.correspondence_number || "—"}</span></td>
                  <td>{row.subject || "—"}</td>
                  <td>
                    {row.correspondence_type
                      ? <span className="rex-badge rex-badge-gray">{row.correspondence_type.replace(/_/g, " ")}</span>
                      : "—"}
                  </td>
                  <td><Badge status={row.status} /></td>
                  <td>
                    {row.from_person_id
                      ? <span style={{ fontFamily: "monospace", fontSize: 11 }}>{row.from_person_id.slice(0, 8)}…</span>
                      : "—"}
                  </td>
                  <td>
                    {row.to_person_id
                      ? <span style={{ fontFamily: "monospace", fontSize: 11 }}>{row.to_person_id.slice(0, 8)}…</span>
                      : "—"}
                  </td>
                  <td>{fmtDate(row.sent_date)}</td>
                  <td>{fmtDate(row.received_date)}</td>
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
              <div className="rex-h3">#{selected.correspondence_number} — {selected.subject}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Badge status={selected.status} />
                {selected.correspondence_type && (
                  <span className="rex-badge rex-badge-gray">{selected.correspondence_type.replace(/_/g, " ")}</span>
                )}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {canWrite && (
                <button className="rex-btn rex-btn-outline" style={{ marginRight: 8 }} onClick={() => openEdit(selected)}>
                  Edit
                </button>
              )}
              <button className="rex-detail-panel-close" onClick={() => { setSelected(null); setAttachments(null); }}>×</button>
            </div>
          </div>

          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Correspondence Info">
              <Row label="Number" value={selected.correspondence_number || "—"} />
              <Row label="Subject" value={selected.subject || "—"} />
              <Row label="Type" value={selected.correspondence_type?.replace(/_/g, " ") || "—"} />
              <Row label="Status" value={<Badge status={selected.status} />} />
            </Card>
            <Card title="Parties">
              <Row label="From" value={selected.from_person_id || "—"} />
              <Row label="To" value={selected.to_person_id || "—"} />
              <Row label="Created By" value={selected.created_by || "—"} />
            </Card>
            <Card title="Dates">
              <Row label="Sent Date" value={fmtDate(selected.sent_date)} />
              <Row label="Received Date" value={fmtDate(selected.received_date)} />
              <Row label="Created" value={selected.created_at ? new Date(selected.created_at).toLocaleDateString() : "—"} />
            </Card>
          </div>

          {selected.body && (
            <Card title="Body" style={{ marginBottom: 12 }}>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)", whiteSpace: "pre-wrap" }}>{selected.body}</p>
            </Card>
          )}

          <Card title="Attachments">
            {attachments === null ? (
              <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>Loading attachments…</p>
            ) : attList.length === 0 ? (
              <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>No attachments.</p>
            ) : (
              <div className="rex-table-wrap" style={{ marginTop: 8 }}>
                <table className="rex-table">
                  <thead>
                    <tr>
                      <th>Filename</th>
                      <th style={{ textAlign: "right" }}>File Size</th>
                      <th>Content Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {attList.map((att, i) => (
                      <tr key={att.id || i}>
                        <td>{att.filename || att.file_name || "—"}</td>
                        <td style={{ textAlign: "right" }}>
                          {att.file_size != null
                            ? att.file_size >= 1048576
                              ? `${(att.file_size / 1048576).toFixed(1)} MB`
                              : `${(att.file_size / 1024).toFixed(1)} KB`
                            : "—"}
                        </td>
                        <td>{att.content_type || att.mime_type || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Correspondence create/edit drawer */}
      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerMode === "create" ? "New Correspondence" : "Edit Correspondence"}
        subtitle={drawerMode === "edit" ? editing?.correspondence_number : undefined}
        mode={drawerMode}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
      >
        <Field label="Correspondence Number" name="correspondence_number" value={form.values.correspondence_number} onChange={form.setField} required autoFocus />
        <Field label="Subject" name="subject" value={form.values.subject} onChange={form.setField} required />
        <Select
          label="Type"
          name="correspondence_type"
          value={form.values.correspondence_type}
          onChange={form.setField}
          options={CORR_TYPES}
          required
        />
        <Select
          label="Status"
          name="status"
          value={form.values.status}
          onChange={form.setField}
          options={STATUSES}
        />
        <Select
          label="From Person"
          name="from_person_id"
          value={form.values.from_person_id}
          onChange={form.setField}
          options={peopleOptions}
          placeholder="Select person…"
        />
        <Select
          label="To Person"
          name="to_person_id"
          value={form.values.to_person_id}
          onChange={form.setField}
          options={peopleOptions}
          placeholder="Select person…"
        />
        <DateField label="Sent Date" name="sent_date" value={form.values.sent_date} onChange={form.setField} />
        <DateField label="Received Date" name="received_date" value={form.values.received_date} onChange={form.setField} />
        <TextArea label="Body" name="body" value={form.values.body} onChange={form.setField} rows={5} />
      </FormDrawer>
    </div>
  );
}
