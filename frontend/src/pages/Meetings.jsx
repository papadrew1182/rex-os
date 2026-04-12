import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

const today = new Date();
today.setHours(0, 0, 0, 0);

function isUpcoming(dateStr) {
  if (!dateStr) return false;
  return new Date(dateStr + "T00:00:00") >= today;
}

export default function Meetings() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [timeFilter, setTimeFilter] = useState("all");
  const [selected, setSelected] = useState(null);
  const [actionItems, setActionItems] = useState(null);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null); setActionItems(null);
    Promise.all([
      api(`/meetings?project_id=${selectedId}&limit=200`),
      api(`/meeting-action-items?status=open&limit=500`),
    ])
      .then(([m, a]) => setData({ meetings: m, openActions: a }))
      .catch((e) => setError(e.message));
  }, [selectedId]);

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
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Meetings</h1>
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
            <button className="rex-detail-panel-close" onClick={() => { setSelected(null); setActionItems(null); }}>×</button>
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
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
