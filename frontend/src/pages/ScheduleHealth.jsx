import { useState, useEffect } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

export default function ScheduleHealth() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { if (!selectedId) return; setData(null); setError(null); api(`/projects/${selectedId}/schedule-health`).then(setData).catch((e) => setError(e.message)); }, [selectedId]);

  if (!selectedId) return <p className="rex-muted">Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading schedule health..." />;

  const v = data.project_average_variance_days;
  const vc = v > 5 ? "red" : v > 0 ? "amber" : "green";

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Schedule Health</h1>
      <p className="rex-muted" style={{ marginBottom: 12 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>
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
