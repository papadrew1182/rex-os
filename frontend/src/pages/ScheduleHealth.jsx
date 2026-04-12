import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

// ── A) Health View (existing summary) ────────────────────────────────────────

function HealthView({ data, project }) {
  const v = data.project_average_variance_days;
  const vc = v > 5 ? "red" : v > 0 ? "amber" : "green";

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        <Badge status={data.health_status} />
        <span className="rex-muted">{data.schedule_count} schedule{data.schedule_count !== 1 ? "s" : ""} · {data.total_activities} activities</span>
      </div>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Activities" value={data.total_activities} />
        <StatCard label="Critical" value={data.critical_count} color={data.critical_count > 0 ? "red" : ""} />
        <StatCard label="Completed" value={data.completed_count} color="green" />
        <StatCard label="Avg Variance" value={`${v >= 0 ? "+" : ""}${v.toFixed(1)}d`} color={vc} />
        <StatCard label="Constraints" value={data.active_constraint_count} color={data.active_constraint_count > 0 ? "amber" : ""} />
      </div>

      {data.active_constraint_count > 0 && (
        <Card title="Constraints by Severity" style={{ marginBottom: 20 }}>
          {Object.entries(data.constraints_by_severity).map(([s, c]) => <Row key={s} label={s} value={c} />)}
        </Card>
      )}

      {data.schedules?.length > 0 && (
        <div>
          <h3 className="rex-h3" style={{ marginBottom: 10 }}>Schedule Drift Details</h3>
          {data.schedules.map((s) => (
            <div key={s.schedule_id} className="rex-card" style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <div><strong>{s.schedule_name}</strong> <span className="rex-muted" style={{ marginLeft: 6 }}>{s.schedule_type}</span></div>
                <Badge status={s.status} />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, fontSize: 13 }}>
                <div><div style={{ fontWeight: 700 }}>{s.total_activities}</div><div className="rex-muted" style={{ fontSize: 11 }}>Activities</div></div>
                <div><div style={{ fontWeight: 700 }}>{s.critical_count}</div><div className="rex-muted" style={{ fontSize: 11 }}>Critical</div></div>
                <div><div style={{ fontWeight: 700, color: `var(--rex-${s.average_variance_days > 5 ? "red" : s.average_variance_days > 0 ? "amber" : "green"})` }}>{s.average_variance_days >= 0 ? "+" : ""}{s.average_variance_days.toFixed(1)}d</div><div className="rex-muted" style={{ fontSize: 11 }}>Avg Variance</div></div>
                <div><div style={{ fontWeight: 700 }}>{s.active_constraint_count}</div><div className="rex-muted" style={{ fontSize: 11 }}>Constraints</div></div>
              </div>
              {s.worst_variance_activity && (
                <div className="rex-alert rex-alert-red" style={{ marginTop: 8 }}>
                  <strong>Worst drift:</strong> {s.worst_variance_activity.name} <span style={{ fontWeight: 800 }}>+{s.worst_variance_activity.variance_days}d</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {data.schedules?.length === 0 && <p className="rex-muted" style={{ marginTop: 12 }}>No schedules for this project.</p>}
    </div>
  );
}

// ── B) Activities View ────────────────────────────────────────────────────────

function ActivitiesView({ project, selectedId }) {
  const [activities, setActivities] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [wbsFilter, setWbsFilter] = useState("");
  const [selected, setSelected] = useState(null);

  const refresh = useCallback(async () => {
    if (!selectedId) return;
    setActivities(null); setError(null); setSelected(null);
    try {
      const schedules = await api(`/schedules?project_id=${selectedId}&limit=50`);
      const lists = await Promise.all((schedules || []).map(s =>
        api(`/schedule-activities?schedule_id=${s.id}&limit=500`).catch(() => [])
      ));
      const all = lists.flat();
      setActivities(all);
    } catch (e) {
      setError(e.message);
    }
  }, [selectedId]);

  useEffect(() => { refresh(); }, [refresh]);

  const filtered = useMemo(() => {
    if (!activities) return [];
    const q = search.toLowerCase();
    return activities.filter(a => {
      if (q && !(a.name || "").toLowerCase().includes(q) && !(a.activity_number || "").toLowerCase().includes(q) && !(a.wbs_code || "").toLowerCase().includes(q)) return false;
      if (wbsFilter && !(a.wbs_code || "").startsWith(wbsFilter)) return false;
      if (statusFilter === "critical" && !a.is_critical) return false;
      if (statusFilter === "complete" && a.percent_complete < 100) return false;
      if (statusFilter === "atrisk" && (a.variance_days == null || a.variance_days <= 0)) return false;
      return true;
    });
  }, [activities, search, statusFilter, wbsFilter]);

  const wbsRoots = useMemo(() => {
    if (!activities) return [];
    const roots = new Set();
    activities.forEach(a => {
      if (a.wbs_code) {
        const root = a.wbs_code.split(".")[0];
        if (root) roots.add(root);
      }
    });
    return [...roots].sort();
  }, [activities]);

  if (!activities && !error) return <PageLoader text="Loading activities..." />;
  if (error) return <Flash type="error" message={error} />;

  return (
    <div>
      <div className="rex-search-bar">
        <input className="rex-input" placeholder="Search name, number, or WBS..." value={search} onChange={e => setSearch(e.target.value)} style={{ maxWidth: 280 }} />
        <select className="rex-input" value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ width: 150 }}>
          <option value="all">All Activities</option>
          <option value="critical">Critical Only</option>
          <option value="atrisk">At Risk (positive variance)</option>
          <option value="complete">Completed</option>
        </select>
        <select className="rex-input" value={wbsFilter} onChange={e => setWbsFilter(e.target.value)} style={{ width: 150 }}>
          <option value="">All WBS</option>
          {wbsRoots.map(r => <option key={r} value={r}>WBS {r}</option>)}
        </select>
        <span className="rex-muted">{filtered.length} activit{filtered.length !== 1 ? "ies" : "y"}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No activities found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>WBS</th>
                <th>Activity #</th>
                <th>Name</th>
                <th>Planned Start</th>
                <th>Planned End</th>
                <th>Actual Start</th>
                <th>Actual End</th>
                <th>Baseline End</th>
                <th style={{ textAlign: "right" }}>% Complete</th>
                <th style={{ textAlign: "right" }}>Variance</th>
                <th style={{ textAlign: "right" }}>Float</th>
                <th>Critical</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(a => {
                const variance = a.variance_days;
                const vColor = variance == null ? "" : variance > 5 ? "var(--rex-red)" : variance > 0 ? "var(--rex-amber)" : "var(--rex-green)";
                return (
                  <tr key={a.id} onClick={() => setSelected(selected?.id === a.id ? null : a)}>
                    <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{a.wbs_code || "—"}</span></td>
                    <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{a.activity_number || "—"}</span></td>
                    <td>{a.name}</td>
                    <td>{fmtDate(a.start_date)}</td>
                    <td>{fmtDate(a.end_date)}</td>
                    <td>{fmtDate(a.actual_start_date)}</td>
                    <td>{fmtDate(a.actual_finish_date)}</td>
                    <td>{fmtDate(a.baseline_end)}</td>
                    <td style={{ textAlign: "right" }}>{a.percent_complete != null ? `${Math.round(a.percent_complete)}%` : "—"}</td>
                    <td style={{ textAlign: "right", color: vColor, fontWeight: variance > 0 ? 700 : 400 }}>{variance != null ? (variance > 0 ? `+${variance}d` : `${variance}d`) : "—"}</td>
                    <td style={{ textAlign: "right" }}>{a.float_days ?? "—"}</td>
                    <td>{a.is_critical ? <span className="rex-badge rex-badge-red">CRITICAL</span> : <span className="rex-badge rex-badge-gray">—</span>}</td>
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
              <div className="rex-h3">{selected.activity_number ? `${selected.activity_number} — ` : ""}{selected.name}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8 }}>
                {selected.is_critical && <span className="rex-badge rex-badge-red">CRITICAL</span>}
                <span className="rex-badge rex-badge-purple">{selected.activity_type}</span>
                {selected.wbs_code && <span className="rex-badge rex-badge-gray">WBS {selected.wbs_code}</span>}
              </div>
            </div>
            <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>×</button>
          </div>
          <div className="rex-grid-3">
            <Card title="Planned">
              <Row label="Start" value={fmtDate(selected.start_date)} />
              <Row label="Finish" value={fmtDate(selected.end_date)} />
              <Row label="Duration" value={selected.duration_days != null ? `${selected.duration_days}d` : "—"} />
            </Card>
            <Card title="Actual">
              <Row label="Start" value={fmtDate(selected.actual_start_date)} />
              <Row label="Finish" value={fmtDate(selected.actual_finish_date)} />
              <Row label="% Complete" value={selected.percent_complete != null ? `${Math.round(selected.percent_complete)}%` : "—"} />
            </Card>
            <Card title="Baseline & Drift">
              <Row label="Baseline Start" value={fmtDate(selected.baseline_start)} />
              <Row label="Baseline End" value={fmtDate(selected.baseline_end)} />
              <Row label="Variance" value={selected.variance_days != null ? `${selected.variance_days}d` : "—"} />
              <Row label="Float" value={selected.float_days != null ? `${selected.float_days}d` : "—"} />
            </Card>
          </div>
          {selected.notes && (
            <Card title="Notes" style={{ marginTop: 12 }}>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.notes}</p>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

// ── C) Lookahead View ─────────────────────────────────────────────────────────

function LookaheadView({ project, selectedId }) {
  const [activities, setActivities] = useState(null);
  const [constraints, setConstraints] = useState({});
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!selectedId) return;
    setActivities(null); setError(null); setConstraints({});
    (async () => {
      try {
        const schedules = await api(`/schedules?project_id=${selectedId}&limit=50`);
        const lists = await Promise.all((schedules || []).map(s => api(`/schedule-activities?schedule_id=${s.id}&limit=500`).catch(() => [])));
        const all = lists.flat();
        // Filter to next 4 weeks
        const today = new Date();
        const horizon = new Date(today.getTime() + 28 * 86400000);
        const inWindow = all.filter(a => {
          const start = a.start_date ? new Date(a.start_date + "T00:00:00") : null;
          return start && start >= today && start <= horizon;
        });
        setActivities(inWindow);
        // Fetch constraints for these activities (best-effort)
        const cMap = {};
        await Promise.all(inWindow.slice(0, 100).map(async a => {
          try {
            const cs = await api(`/schedule-constraints?activity_id=${a.id}&limit=20`);
            cMap[a.id] = (cs || []).filter(c => c.status === "active");
          } catch {}
        }));
        setConstraints(cMap);
      } catch (e) {
        setError(e.message);
      }
    })();
  }, [selectedId]);

  function weekKey(dateStr) {
    const d = new Date(dateStr + "T00:00:00");
    const day = d.getDay();
    const monday = new Date(d.getTime() - ((day + 6) % 7) * 86400000);
    return monday.toISOString().slice(0, 10);
  }

  const grouped = useMemo(() => {
    if (!activities) return {};
    const g = {};
    activities.forEach(a => {
      const k = weekKey(a.start_date);
      if (!g[k]) g[k] = [];
      g[k].push(a);
    });
    return g;
  }, [activities]);

  function constraintBadge(actId, sourceType) {
    const cs = (constraints[actId] || []).filter(c => c.source_type === sourceType);
    if (cs.length === 0) return <span className="rex-badge rex-badge-green">CLEAR</span>;
    const worst = cs.reduce((w, c) => (c.severity === "red" ? "red" : (w === "red" ? "red" : c.severity === "yellow" ? "yellow" : w)), "yellow");
    return <span className={`rex-badge ${worst === "red" ? "rex-badge-red" : "rex-badge-amber"}`}>{cs.length}</span>;
  }

  if (!activities && !error) return <PageLoader text="Loading lookahead..." />;
  if (error) return <Flash type="error" message={error} />;

  const weeks = Object.keys(grouped).sort();

  return (
    <div>
      <p className="rex-muted" style={{ marginBottom: 16 }}>Activities starting in the next 4 weeks. Constraint lanes show active blocks per source type.</p>
      {weeks.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No activities scheduled in the next 4 weeks.</div>
      ) : (
        weeks.map(wk => (
          <div key={wk} style={{ marginBottom: 24 }}>
            <h3 className="rex-h3" style={{ marginBottom: 8 }}>Week of {fmtDate(wk)}</h3>
            <div className="rex-table-wrap">
              <table className="rex-table">
                <thead>
                  <tr>
                    <th>Activity</th>
                    <th>WBS</th>
                    <th>Start</th>
                    <th>End</th>
                    <th>RFI</th>
                    <th>Submittal</th>
                    <th>Commitment</th>
                    <th>Insurance</th>
                    <th>Critical</th>
                  </tr>
                </thead>
                <tbody>
                  {grouped[wk].map(a => (
                    <tr key={a.id}>
                      <td>{a.activity_number ? `${a.activity_number} — ` : ""}{a.name}</td>
                      <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{a.wbs_code || "—"}</span></td>
                      <td>{fmtDate(a.start_date)}</td>
                      <td>{fmtDate(a.end_date)}</td>
                      <td>{constraintBadge(a.id, "rfi")}</td>
                      <td>{constraintBadge(a.id, "submittal")}</td>
                      <td>{constraintBadge(a.id, "commitment")}</td>
                      <td>{constraintBadge(a.id, "insurance")}</td>
                      <td>{a.is_critical ? <span className="rex-badge rex-badge-red">CP</span> : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

// ── D) Critical Path View ─────────────────────────────────────────────────────

function CriticalView({ project, selectedId }) {
  const [activities, setActivities] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!selectedId) return;
    setActivities(null); setError(null);
    (async () => {
      try {
        const schedules = await api(`/schedules?project_id=${selectedId}&limit=50`);
        const lists = await Promise.all((schedules || []).map(s => api(`/schedule-activities?schedule_id=${s.id}&limit=500`).catch(() => [])));
        const all = lists.flat();
        // Critical OR near-critical (float < 5 days)
        const filtered = all.filter(a => a.is_critical || (a.float_days != null && a.float_days < 5));
        // Sort: critical first, then by float asc, then by variance desc
        filtered.sort((a, b) => {
          if (a.is_critical !== b.is_critical) return b.is_critical - a.is_critical;
          if (a.float_days !== b.float_days) return (a.float_days || 0) - (b.float_days || 0);
          return (b.variance_days || 0) - (a.variance_days || 0);
        });
        setActivities(filtered);
      } catch (e) {
        setError(e.message);
      }
    })();
  }, [selectedId]);

  if (!activities && !error) return <PageLoader text="Loading critical path..." />;
  if (error) return <Flash type="error" message={error} />;

  const driftCount = activities.filter(a => a.variance_days != null && a.variance_days > 0).length;

  return (
    <div>
      <div className="rex-grid-4" style={{ marginBottom: 20 }}>
        <StatCard label="Critical Activities" value={activities.filter(a => a.is_critical).length} color="red" />
        <StatCard label="Near-Critical (Float < 5d)" value={activities.filter(a => !a.is_critical && a.float_days != null && a.float_days < 5).length} color="amber" />
        <StatCard label="Drifting Critical" value={driftCount} color={driftCount > 0 ? "red" : ""} />
        <StatCard label="Total Tracked" value={activities.length} />
      </div>

      {activities.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No critical or near-critical activities found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Activity</th>
                <th>WBS</th>
                <th>Planned Finish</th>
                <th>Actual Finish</th>
                <th style={{ textAlign: "right" }}>% Complete</th>
                <th style={{ textAlign: "right" }}>Variance</th>
                <th style={{ textAlign: "right" }}>Float</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {activities.map(a => {
                const variance = a.variance_days;
                const vColor = variance == null ? "" : variance > 5 ? "var(--rex-red)" : variance > 0 ? "var(--rex-amber)" : "var(--rex-green)";
                return (
                  <tr key={a.id} onClick={() => setSelected(selected?.id === a.id ? null : a)}>
                    <td>{a.activity_number ? `${a.activity_number} — ` : ""}{a.name}</td>
                    <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{a.wbs_code || "—"}</span></td>
                    <td>{fmtDate(a.end_date)}</td>
                    <td>{fmtDate(a.actual_finish_date)}</td>
                    <td style={{ textAlign: "right" }}>{a.percent_complete != null ? `${Math.round(a.percent_complete)}%` : "—"}</td>
                    <td style={{ textAlign: "right", color: vColor, fontWeight: variance > 0 ? 700 : 400 }}>{variance != null ? (variance > 0 ? `+${variance}d` : `${variance}d`) : "—"}</td>
                    <td style={{ textAlign: "right" }}>{a.float_days ?? "—"}</td>
                    <td>{a.is_critical ? <span className="rex-badge rex-badge-red">CRITICAL</span> : <span className="rex-badge rex-badge-amber">NEAR</span>}</td>
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
              <div className="rex-h3">{selected.activity_number ? `${selected.activity_number} — ` : ""}{selected.name}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8 }}>
                {selected.is_critical
                  ? <span className="rex-badge rex-badge-red">CRITICAL</span>
                  : <span className="rex-badge rex-badge-amber">NEAR-CRITICAL</span>}
                {selected.wbs_code && <span className="rex-badge rex-badge-gray">WBS {selected.wbs_code}</span>}
              </div>
            </div>
            <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>×</button>
          </div>
          <div className="rex-grid-3">
            <Card title="Planned">
              <Row label="Start" value={fmtDate(selected.start_date)} />
              <Row label="Finish" value={fmtDate(selected.end_date)} />
              <Row label="Duration" value={selected.duration_days != null ? `${selected.duration_days}d` : "—"} />
            </Card>
            <Card title="Actual">
              <Row label="Start" value={fmtDate(selected.actual_start_date)} />
              <Row label="Finish" value={fmtDate(selected.actual_finish_date)} />
              <Row label="% Complete" value={selected.percent_complete != null ? `${Math.round(selected.percent_complete)}%` : "—"} />
            </Card>
            <Card title="Baseline & Drift">
              <Row label="Baseline Start" value={fmtDate(selected.baseline_start)} />
              <Row label="Baseline End" value={fmtDate(selected.baseline_end)} />
              <Row label="Variance" value={selected.variance_days != null ? `${selected.variance_days}d` : "—"} />
              <Row label="Float" value={selected.float_days != null ? `${selected.float_days}d` : "—"} />
            </Card>
          </div>
          {selected.notes && (
            <Card title="Notes" style={{ marginTop: 12 }}>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.notes}</p>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

// ── Default export: tabbed container ─────────────────────────────────────────

export default function ScheduleHealth() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("health");

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null);
    api(`/projects/${selectedId}/schedule-health`).then(setData).catch((e) => setError(e.message));
  }, [selectedId]);

  if (!selectedId) return <p className="rex-muted">Select a project.</p>;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Schedule Health</h1>
      <p className="rex-muted" style={{ marginBottom: 12 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-tab-bar">
        <button className={`rex-tab${activeTab === "health" ? " active" : ""}`} onClick={() => setActiveTab("health")}>Health</button>
        <button className={`rex-tab${activeTab === "activities" ? " active" : ""}`} onClick={() => setActiveTab("activities")}>Activities</button>
        <button className={`rex-tab${activeTab === "lookahead" ? " active" : ""}`} onClick={() => setActiveTab("lookahead")}>Lookahead</button>
        <button className={`rex-tab${activeTab === "critical" ? " active" : ""}`} onClick={() => setActiveTab("critical")}>Critical Path</button>
      </div>

      {activeTab === "health" && (
        error ? <Flash type="error" message={error} /> :
        !data ? <PageLoader text="Loading schedule health..." /> :
        <HealthView data={data} project={project} />
      )}
      {activeTab === "activities" && <ActivitiesView project={project} selectedId={selectedId} />}
      {activeTab === "lookahead" && <LookaheadView project={project} selectedId={selectedId} />}
      {activeTab === "critical" && <CriticalView project={project} selectedId={selectedId} />}
    </div>
  );
}
