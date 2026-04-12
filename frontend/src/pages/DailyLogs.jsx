import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";
const fmtNum = (n) => n == null ? "—" : Number(n).toLocaleString();

export default function DailyLogs() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [manpowerSummary, setManpowerSummary] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [logSummary, setLogSummary] = useState(null);
  const [manpowerEntries, setManpowerEntries] = useState(null);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null); setManpowerSummary(null);
    Promise.all([
      api(`/daily-logs?project_id=${selectedId}&limit=200`),
      api(`/projects/${selectedId}/manpower-summary`),
    ])
      .then(([logs, mp]) => { setData(logs); setManpowerSummary(mp); })
      .catch((e) => setError(e.message));
  }, [selectedId]);

  function handleRowClick(row) {
    if (selected?.id === row.id) { setSelected(null); setLogSummary(null); setManpowerEntries(null); return; }
    setSelected(row);
    setLogSummary(null);
    setManpowerEntries(null);
    api(`/daily-logs/${row.id}/summary`).then(setLogSummary).catch(() => setLogSummary(null));
    api(`/manpower-entries?daily_log_id=${row.id}&limit=100`).then(setManpowerEntries).catch(() => setManpowerEntries([]));
  }

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.daily_logs || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q || (r.log_date || "").toLowerCase().includes(q) || (r.work_summary || "").toLowerCase().includes(q);
      const matchStatus = !statusFilter || r.status === statusFilter;
      return matchSearch && matchStatus;
    });
  }, [items, search, statusFilter]);

  const statuses = useMemo(() => [...new Set(items.map((r) => r.status).filter(Boolean))], [items]);

  const summary = useMemo(() => {
    const weatherDelays = items.filter((r) => r.is_weather_delay === true).length;
    return {
      totalLogs: manpowerSummary?.total_logs ?? items.length,
      totalWorkers: manpowerSummary?.total_workers ?? null,
      totalHours: manpowerSummary?.total_hours ?? null,
      avgWorkers: manpowerSummary?.average_workers_per_log != null
        ? Number(manpowerSummary.average_workers_per_log).toFixed(1)
        : null,
      weatherDelays,
    };
  }, [items, manpowerSummary]);

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading daily logs..." />;

  const mpEntries = Array.isArray(manpowerEntries) ? manpowerEntries : (manpowerEntries?.items || []);

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Daily Logs</h1>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Logs" value={summary.totalLogs} />
        <StatCard label="Total Workers" value={summary.totalWorkers != null ? fmtNum(summary.totalWorkers) : "—"} />
        <StatCard label="Total Hours" value={summary.totalHours != null ? fmtNum(summary.totalHours) : "—"} />
        <StatCard label="Avg Workers/Log" value={summary.avgWorkers ?? "—"} />
        <StatCard label="Weather Delays" value={summary.weatherDelays} color={summary.weatherDelays > 0 ? "amber" : ""} />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search date or work summary..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 260 }}
        />
        <select className="rex-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: 150 }}>
          <option value="">All Statuses</option>
          {statuses.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <span className="rex-muted">{filtered.length} record{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No daily logs found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Log Date</th>
                <th>Status</th>
                <th>Weather</th>
                <th>Temp Hi / Lo</th>
                <th>Delay</th>
                <th>Work Summary</th>
                <th>Approved</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => {
                const tempStr = (row.temp_high_f != null && row.temp_low_f != null)
                  ? `${row.temp_high_f}° / ${row.temp_low_f}°`
                  : "—";
                const shortSummary = row.work_summary
                  ? row.work_summary.length > 50 ? row.work_summary.slice(0, 50) + "…" : row.work_summary
                  : "—";
                return (
                  <tr key={row.id || i} onClick={() => handleRowClick(row)}>
                    <td>{fmtDate(row.log_date)}</td>
                    <td><Badge status={row.status} /></td>
                    <td>{row.weather_summary || "—"}</td>
                    <td>{tempStr}</td>
                    <td>
                      {row.is_weather_delay
                        ? <span className="rex-badge rex-badge-amber">DELAY</span>
                        : <span className="rex-badge rex-badge-gray">—</span>}
                    </td>
                    <td>{shortSummary}</td>
                    <td>
                      {row.approved_by
                        ? <span className="rex-badge rex-badge-green">Approved</span>
                        : "—"}
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
              <div className="rex-h3">Daily Log — {fmtDate(selected.log_date)}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Badge status={selected.status} />
                {selected.is_weather_delay && <span className="rex-badge rex-badge-amber">WEATHER DELAY</span>}
              </div>
            </div>
            <button className="rex-detail-panel-close" onClick={() => { setSelected(null); setLogSummary(null); setManpowerEntries(null); }}>×</button>
          </div>
          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Log Info">
              <Row label="Date" value={fmtDate(selected.log_date)} />
              <Row label="Status" value={<Badge status={selected.status} />} />
              <Row label="Weather" value={selected.weather_summary || "—"} />
              <Row label="Temp Hi / Lo" value={(selected.temp_high_f != null && selected.temp_low_f != null) ? `${selected.temp_high_f}° / ${selected.temp_low_f}°` : "—"} />
              <Row label="Weather Delay" value={selected.is_weather_delay ? "Yes" : "No"} />
            </Card>
            <Card title="Manpower Summary">
              {logSummary ? (
                <>
                  <Row label="Total Workers" value={fmtNum(logSummary.total_workers)} />
                  <Row label="Total Hours" value={fmtNum(logSummary.total_hours)} />
                  <Row label="Unique Companies" value={fmtNum(logSummary.unique_companies)} />
                </>
              ) : (
                <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>Loading…</p>
              )}
            </Card>
            <Card title="Approval">
              <Row label="Approved By" value={selected.approved_by || "—"} />
              <Row label="Approved At" value={selected.approved_at ? new Date(selected.approved_at).toLocaleString() : "—"} />
            </Card>
          </div>
          <Card title="Notes" style={{ marginBottom: 12 }}>
            {selected.work_summary && <p style={{ margin: "0 0 8px", fontSize: 13, color: "var(--rex-text-muted)" }}><strong>Work:</strong> {selected.work_summary}</p>}
            {selected.delay_notes && <p style={{ margin: "0 0 8px", fontSize: 13, color: "var(--rex-text-muted)" }}><strong>Delays:</strong> {selected.delay_notes}</p>}
            {selected.safety_notes && <p style={{ margin: "0 0 8px", fontSize: 13, color: "var(--rex-text-muted)" }}><strong>Safety:</strong> {selected.safety_notes}</p>}
            {selected.visitor_notes && <p style={{ margin: "0 0 8px", fontSize: 13, color: "var(--rex-text-muted)" }}><strong>Visitors:</strong> {selected.visitor_notes}</p>}
            {!selected.work_summary && !selected.delay_notes && !selected.safety_notes && !selected.visitor_notes && (
              <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>No notes recorded.</p>
            )}
          </Card>
          {mpEntries.length > 0 && (
            <Card title="Manpower Entries">
              <div className="rex-table-wrap" style={{ marginTop: 8 }}>
                <table className="rex-table">
                  <thead>
                    <tr>
                      <th>Company ID</th>
                      <th style={{ textAlign: "right" }}>Workers</th>
                      <th style={{ textAlign: "right" }}>Hours</th>
                      <th>Description</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mpEntries.map((e, i) => (
                      <tr key={e.id || i}>
                        <td><span style={{ fontFamily: "monospace", fontSize: 11 }}>{e.company_id || "—"}</span></td>
                        <td style={{ textAlign: "right" }}>{e.worker_count ?? "—"}</td>
                        <td style={{ textAlign: "right" }}>{e.hours_worked ?? "—"}</td>
                        <td>{e.description || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
