import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";
import { FormDrawer, useFormState, Field, NumberField, DateField, TimeField, TextArea, Select, WriteButton, cleanPayload } from "../forms";
import { usePermissions } from "../permissions";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

const today = new Date();
today.setHours(0, 0, 0, 0);

function isUpcoming(dateStr) {
  if (!dateStr) return false;
  return new Date(dateStr + "T00:00:00") >= today;
}

const ACTION_STATUSES = ["open", "complete", "void"];

const MEETING_DEFAULT = {
  title: "",
  meeting_type: "",
  meeting_date: null,
  start_time: null,
  end_time: null,
  location: "",
  agenda: "",
  minutes: "",
  packet_url: "",
};

const ACTION_ITEM_DEFAULT = {
  meeting_id: null,
  item_number: null,
  description: "",
  assigned_to: null,
  due_date: null,
  status: "open",
};

export default function Meetings() {
  const { selected: project, selectedId } = useProject();
  const { canWrite } = usePermissions();

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [timeFilter, setTimeFilter] = useState("all");
  const [selected, setSelected] = useState(null);
  const [actionItems, setActionItems] = useState(null);
  const [people, setPeople] = useState([]);

  // Main drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState("create");
  const [editing, setEditing] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const form = useFormState(MEETING_DEFAULT);

  // Child (action item) drawer state
  const [childDrawerOpen, setChildDrawerOpen] = useState(false);
  const [childMode, setChildMode] = useState("create");
  const [childEditing, setChildEditing] = useState(null);
  const [childSubmitting, setChildSubmitting] = useState(false);
  const [childError, setChildError] = useState(null);
  const childForm = useFormState(ACTION_ITEM_DEFAULT);

  const refresh = useCallback(() => {
    if (!selectedId) return;
    Promise.all([
      api(`/meetings?project_id=${selectedId}&limit=200`),
      api(`/meeting-action-items?status=open&limit=500`),
    ])
      .then(([m, a]) => setData({ meetings: m, openActions: a }))
      .catch((e) => setError(e.message));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null); setActionItems(null);
    refresh();
  }, [selectedId, refresh]);

  useEffect(() => {
    if (!selectedId) return;
    api(`/people?limit=500`).catch(() => []).then((p) => setPeople(Array.isArray(p) ? p : []));
  }, [selectedId]);

  const peopleOptions = useMemo(() => people.map((p) => ({ value: p.id, label: `${p.first_name} ${p.last_name}` })), [people]);

  function refreshActionItems(meetingId) {
    api(`/meeting-action-items?meeting_id=${meetingId}&limit=100`)
      .then(setActionItems)
      .catch(() => setActionItems([]));
  }

  function handleRowClick(row) {
    if (selected?.id === row.id) { setSelected(null); setActionItems(null); return; }
    setSelected(row);
    setActionItems(null);
    api(`/meeting-action-items?meeting_id=${row.id}&limit=100`)
      .then(setActionItems)
      .catch(() => setActionItems([]));
  }

  const meetings = useMemo(() => {
    if (!data) return [];
    return Array.isArray(data.meetings) ? data.meetings : (data.meetings?.items || data.meetings?.meetings || []);
  }, [data]);

  const openActionsCount = useMemo(() => {
    if (!data?.openActions) return 0;
    const list = Array.isArray(data.openActions) ? data.openActions : (data.openActions?.items || []);
    return list.length;
  }, [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return meetings.filter((r) => {
      const matchSearch = !q
        || (r.title || "").toLowerCase().includes(q)
        || (r.location || "").toLowerCase().includes(q);
      const matchType = !typeFilter || r.meeting_type === typeFilter;
      const matchTime = timeFilter === "all"
        || (timeFilter === "upcoming" && isUpcoming(r.meeting_date))
        || (timeFilter === "past" && !isUpcoming(r.meeting_date));
      return matchSearch && matchType && matchTime;
    });
  }, [meetings, search, typeFilter, timeFilter]);

  const types = useMemo(() => [...new Set(meetings.map((r) => r.meeting_type).filter(Boolean))].sort(), [meetings]);

  const summary = useMemo(() => {
    const upcoming = meetings.filter((r) => isUpcoming(r.meeting_date)).length;
    const past = meetings.filter((r) => !isUpcoming(r.meeting_date)).length;
    const withPackets = meetings.filter((r) => r.packet_url).length;
    return { total: meetings.length, upcoming, past, withPackets };
  }, [meetings]);

  function openCreate() {
    setDrawerMode("create");
    setEditing(null);
    form.setAll({ ...MEETING_DEFAULT });
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
        await api("/meetings/", { method: "POST", body: { ...payload, project_id: selectedId } });
      } else {
        const { project_id, ...updateOnly } = payload;
        await api(`/meetings/${editing.id}`, { method: "PATCH", body: updateOnly });
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

  function openChildCreate(meetingId) {
    setChildMode("create");
    setChildEditing(null);
    childForm.setAll({ meeting_id: meetingId, status: "open" });
    setChildError(null);
    setChildDrawerOpen(true);
  }

  function openChildEdit(item) {
    setChildMode("edit");
    setChildEditing(item);
    childForm.setAll({ ...item });
    setChildError(null);
    setChildDrawerOpen(true);
  }

  async function onChildSubmit() {
    setChildSubmitting(true);
    setChildError(null);
    try {
      const payload = cleanPayload(childForm.values);
      if (childMode === "create") {
        await api("/meeting-action-items/", { method: "POST", body: payload });
      } else {
        const { meeting_id, ...updateOnly } = payload;
        await api(`/meeting-action-items/${childEditing.id}`, { method: "PATCH", body: updateOnly });
      }
      setChildDrawerOpen(false);
      if (selected) refreshActionItems(selected.id);
    } catch (e) {
      setChildError(e.message);
    } finally {
      setChildSubmitting(false);
    }
  }

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading meetings..." />;

  const aiList = Array.isArray(actionItems) ? actionItems : (actionItems?.items || []);

  function fmtTime(t) {
    if (!t) return "";
    return t.slice(0, 5);
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <h1 className="rex-h1">Meetings</h1>
        <WriteButton onClick={openCreate}>+ New Meeting</WriteButton>
      </div>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Meetings" value={summary.total} />
        <StatCard label="Upcoming" value={summary.upcoming} color={summary.upcoming > 0 ? "green" : ""} />
        <StatCard label="Past" value={summary.past} />
        <StatCard label="Open Action Items" value={openActionsCount} color={openActionsCount > 0 ? "amber" : ""} />
        <StatCard label="With Packets" value={summary.withPackets} />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search title or location..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 260 }}
        />
        <select className="rex-input" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} style={{ width: 160 }}>
          <option value="">All Types</option>
          {types.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
        </select>
        <select className="rex-input" value={timeFilter} onChange={(e) => setTimeFilter(e.target.value)} style={{ width: 140 }}>
          <option value="all">All Meetings</option>
          <option value="upcoming">Upcoming</option>
          <option value="past">Past</option>
        </select>
        <span className="rex-muted">{filtered.length} record{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No meetings found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Title</th>
                <th>Type</th>
                <th>Time</th>
                <th>Location</th>
                <th>Status</th>
                <th>Packet</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => {
                const upcoming = isUpcoming(row.meeting_date);
                const timeStr = [fmtTime(row.start_time), fmtTime(row.end_time)].filter(Boolean).join(" — ") || "—";
                return (
                  <tr key={row.id || i} onClick={() => handleRowClick(row)}>
                    <td>{fmtDate(row.meeting_date)}</td>
                    <td>{row.title || "—"}</td>
                    <td>
                      {row.meeting_type
                        ? <span className="rex-badge rex-badge-gray">{row.meeting_type.replace(/_/g, " ")}</span>
                        : "—"}
                    </td>
                    <td style={{ fontFamily: "monospace", fontSize: 12 }}>{timeStr}</td>
                    <td>{row.location || "—"}</td>
                    <td>
                      {upcoming
                        ? <span className="rex-badge rex-badge-green">UPCOMING</span>
                        : <span className="rex-badge rex-badge-gray">PAST</span>}
                    </td>
                    <td>
                      {row.packet_url
                        ? <span className="rex-badge rex-badge-green">FILE</span>
                        : <span className="rex-badge rex-badge-gray">—</span>}
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
              <div className="rex-h3">{selected.title}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                {isUpcoming(selected.meeting_date)
                  ? <span className="rex-badge rex-badge-green">UPCOMING</span>
                  : <span className="rex-badge rex-badge-gray">PAST</span>}
                {selected.meeting_type && (
                  <span className="rex-badge rex-badge-gray">{selected.meeting_type.replace(/_/g, " ")}</span>
                )}
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {canWrite && (
                <button className="rex-btn rex-btn-outline" onClick={() => openEdit(selected)}>
                  Edit
                </button>
              )}
              <button className="rex-detail-panel-close" onClick={() => { setSelected(null); setActionItems(null); }}>×</button>
            </div>
          </div>

          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Meeting Info">
              <Row label="Title" value={selected.title || "—"} />
              <Row label="Type" value={selected.meeting_type?.replace(/_/g, " ") || "—"} />
              <Row label="Date" value={fmtDate(selected.meeting_date)} />
              <Row label="Time" value={[fmtTime(selected.start_time), fmtTime(selected.end_time)].filter(Boolean).join(" — ") || "—"} />
              <Row label="Location" value={selected.location || "—"} />
            </Card>
            <Card title="Resources">
              <Row
                label="Packet"
                value={selected.packet_url
                  ? <a href={selected.packet_url} target="_blank" rel="noreferrer" style={{ color: "var(--rex-accent)", fontSize: 12 }}>View Packet</a>
                  : "—"}
              />
              <Row label="Created By" value={selected.created_by || "—"} />
              <Row label="Created" value={selected.created_at ? new Date(selected.created_at).toLocaleDateString() : "—"} />
            </Card>
            <Card title="Attendees">
              {selected.attendees ? (
                Array.isArray(selected.attendees)
                  ? selected.attendees.length > 0
                    ? <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, color: "var(--rex-text-muted)" }}>
                        {selected.attendees.map((a, i) => <li key={i}>{typeof a === "string" ? a : JSON.stringify(a)}</li>)}
                      </ul>
                    : <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>No attendees listed.</p>
                  : <pre style={{ margin: 0, fontSize: 11, color: "var(--rex-text-muted)", whiteSpace: "pre-wrap" }}>{JSON.stringify(selected.attendees, null, 2)}</pre>
              ) : (
                <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>No attendees listed.</p>
              )}
            </Card>
          </div>

          {selected.agenda && (
            <Card title="Agenda" style={{ marginBottom: 12 }}>
              <pre style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)", whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{selected.agenda}</pre>
            </Card>
          )}

          {selected.minutes && (
            <Card title="Minutes" style={{ marginBottom: 12 }}>
              <pre style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)", whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{selected.minutes}</pre>
            </Card>
          )}

          <Card title="Action Items">
            {canWrite && (
              <div style={{ marginBottom: 8 }}>
                <WriteButton onClick={() => openChildCreate(selected.id)} variant="outline">+ Add Action Item</WriteButton>
              </div>
            )}
            {actionItems === null ? (
              <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>Loading action items…</p>
            ) : aiList.length === 0 ? (
              <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>No action items.</p>
            ) : (
              <div className="rex-table-wrap" style={{ marginTop: 8 }}>
                <table className="rex-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Description</th>
                      <th>Assigned To</th>
                      <th>Due Date</th>
                      <th>Status</th>
                      <th>Linked Task</th>
                      {canWrite && <th></th>}
                    </tr>
                  </thead>
                  <tbody>
                    {aiList.map((ai, i) => (
                      <tr key={ai.id || i}>
                        <td style={{ fontFamily: "monospace", fontSize: 12 }}>{ai.item_number ?? i + 1}</td>
                        <td>{ai.description || "—"}</td>
                        <td>
                          {ai.assigned_to
                            ? <span style={{ fontFamily: "monospace", fontSize: 11 }}>{ai.assigned_to.slice(0, 8)}…</span>
                            : "—"}
                        </td>
                        <td>{fmtDate(ai.due_date)}</td>
                        <td><Badge status={ai.status} /></td>
                        <td>
                          {ai.task_id
                            ? <span style={{ fontFamily: "monospace", fontSize: 11 }}>{ai.task_id.slice(0, 8)}…</span>
                            : "—"}
                        </td>
                        {canWrite && (
                          <td>
                            <button className="rex-btn rex-btn-outline" style={{ padding: "2px 8px", fontSize: 11 }} onClick={() => openChildEdit(ai)}>
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

      {/* Main Meeting Drawer */}
      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerMode === "create" ? "New Meeting" : "Edit Meeting"}
        mode={drawerMode}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
      >
        <Field label="Title" name="title" value={form.values.title} onChange={form.setField} required autoFocus />
        <Field label="Meeting Type" name="meeting_type" value={form.values.meeting_type} onChange={form.setField} required placeholder="e.g. OAC, Safety, Kickoff" />
        <DateField label="Meeting Date" name="meeting_date" value={form.values.meeting_date} onChange={form.setField} required />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <TimeField label="Start Time" name="start_time" value={form.values.start_time} onChange={form.setField} />
          <TimeField label="End Time" name="end_time" value={form.values.end_time} onChange={form.setField} />
        </div>
        <Field label="Location" name="location" value={form.values.location} onChange={form.setField} />
        <TextArea label="Agenda" name="agenda" value={form.values.agenda} onChange={form.setField} rows={4} />
        <TextArea label="Minutes" name="minutes" value={form.values.minutes} onChange={form.setField} rows={4} />
        <Field label="Packet URL" name="packet_url" value={form.values.packet_url} onChange={form.setField} placeholder="https://..." />
      </FormDrawer>

      {/* Child Action Item Drawer */}
      <FormDrawer
        open={childDrawerOpen}
        onClose={() => setChildDrawerOpen(false)}
        title={childMode === "create" ? "Add Action Item" : "Edit Action Item"}
        mode={childMode}
        onSubmit={onChildSubmit}
        onReset={childForm.reset}
        dirty={childForm.dirty}
        submitting={childSubmitting}
        error={childError}
      >
        <NumberField label="Item Number" name="item_number" value={childForm.values.item_number} onChange={childForm.setField} step={1} required />
        <TextArea label="Description" name="description" value={childForm.values.description} onChange={childForm.setField} rows={2} required />
        <Select label="Assigned To" name="assigned_to" value={childForm.values.assigned_to} onChange={childForm.setField} options={peopleOptions} />
        <DateField label="Due Date" name="due_date" value={childForm.values.due_date} onChange={childForm.setField} />
        <Select label="Status" name="status" value={childForm.values.status} onChange={childForm.setField} options={ACTION_STATUSES} />
      </FormDrawer>
    </div>
  );
}
