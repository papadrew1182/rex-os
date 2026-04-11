import { useState, useEffect } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, Card, Row, PageLoader, Flash } from "../ui";

export default function ExecutionHealth() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => { if (!selectedId) return; setData(null); setError(null); api(`/projects/${selectedId}/execution-health`).then(setData).catch((e) => setError(e.message)); }, [selectedId]);

  if (!selectedId) return <p className="rex-muted">Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading execution health..." />;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Execution Health</h1>
      <p className="rex-muted" style={{ marginBottom: 12 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
        <Badge status={data.schedule_health_status} />
        <span className="rex-muted">{data.schedule_active_constraints} active constraint{data.schedule_active_constraints !== 1 ? "s" : ""}</span>
      </div>

      <div className="rex-grid-2">
        <Card title="Manpower">
          <Row label="Daily Logs" value={data.manpower.total_logs} />
          <Row label="Total Workers" value={data.manpower.total_worker_count} />
          <Row label="Total Hours" value={data.manpower.total_hours.toLocaleString()} />
          <Row label="Avg Workers/Log" value={data.manpower.average_workers_per_log.toFixed(1)} />
          {data.manpower.total_logs === 0 && <p className="rex-muted" style={{ marginTop: 6 }}>No daily logs recorded.</p>}
        </Card>
        <Card title="Inspections">
          <Row label="Total" value={data.inspections.total} />
          <Row label="Open" value={<span style={{ color: data.inspections.open_count > 0 ? "var(--rex-amber)" : "var(--rex-green)", fontWeight: 700 }}>{data.inspections.open_count}</span>} />
          <Row label="Failed Items" value={<span style={{ color: data.inspections.failed_item_count > 0 ? "var(--rex-red)" : "var(--rex-green)", fontWeight: 700 }}>{data.inspections.failed_item_count}</span>} />
        </Card>
        <Card title="Punch Items">
          <Row label="Total" value={data.punch.total} />
          <Row label="Open" value={<span style={{ color: data.punch.open_count > 0 ? "var(--rex-red)" : "var(--rex-green)", fontWeight: 700 }}>{data.punch.open_count}</span>} />
          {data.punch.total > 0 && <Row label="Closure Rate" value={`${(((data.punch.total - data.punch.open_count) / data.punch.total) * 100).toFixed(0)}%`} />}
        </Card>
        <Card title="Tasks by Status">
          {Object.keys(data.tasks_by_status).length === 0 ? <p className="rex-muted">No tasks.</p> : (
            <>
              {Object.entries(data.tasks_by_status).map(([s, c]) => <Row key={s} label={s.replace(/_/g, " ")} value={c} />)}
              <TaskBar tasks={data.tasks_by_status} />
            </>
          )}
        </Card>
        {data.schedule_active_constraints > 0 && (
          <Card title="Schedule Constraints">
            {Object.entries(data.schedule_constraints_by_severity).map(([s, c]) => (
              <Row key={s} label={s} value={<span style={{ color: s === "critical" ? "var(--rex-red)" : s === "high" ? "var(--rex-amber)" : "var(--rex-text)", fontWeight: 700 }}>{c}</span>} />
            ))}
          </Card>
        )}
      </div>
    </div>
  );
}

function TaskBar({ tasks }) {
  const total = Object.values(tasks).reduce((a, b) => a + b, 0);
  if (!total) return null;
  const colors = { complete: "var(--rex-green)", in_progress: "var(--rex-accent)", open: "var(--rex-amber)", draft: "#94A3B8", closed: "var(--rex-green)" };
  return (
    <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", marginTop: 8 }}>
      {Object.entries(tasks).map(([s, c]) => <div key={s} style={{ width: `${(c / total) * 100}%`, background: colors[s] || "#ccc" }} title={`${s}: ${c}`} />)}
    </div>
  );
}
