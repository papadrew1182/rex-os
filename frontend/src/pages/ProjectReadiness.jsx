import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, Card, Row, ProgressBar, PageLoader, Flash } from "../ui";

export default function ProjectReadiness() {
  const { projectId } = useParams();
  const { select } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { select(projectId); setData(null); api(`/projects/${projectId}/closeout-readiness`).then(setData).catch((e) => setError(e.message)); }, [projectId, select]);

  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading project readiness..." />;

  return (
    <div>
      <Link to="/" style={{ color: "var(--rex-accent)", fontSize: 13, fontWeight: 600 }}>&larr; Portfolio</Link>
      <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "12px 0 6px" }}>
        <h1 className="rex-h1">{data.project_name}</h1>
        <Badge status={data.overall_status} />
      </div>
      <p className="rex-muted" style={{ marginBottom: 16 }}>{data.summary_message}</p>

      <div style={{ display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        {[["Schedule Health", "/schedule"], ["Execution", "/execution"], ["Checklists", "/checklists"], ["Milestones", "/milestones"], ["Attachments", "/attachments"]].map(([l, to]) => (
          <Link key={to} to={to} className="rex-btn rex-btn-outline" style={{ fontSize: 12 }}>{l}</Link>
        ))}
      </div>

      <div className="rex-grid-2">
        <Card title="Checklist">
          <Row label="Checklists" value={data.checklist_summary.checklist_count} />
          <Row label="Items" value={`${data.checklist_summary.completed_items} / ${data.checklist_summary.total_items}`} />
          <Row label="Best %" value={`${data.checklist_summary.best_percent_complete.toFixed(1)}%`} />
          <ProgressBar pct={data.checklist_summary.best_percent_complete} />
        </Card>
        <Card title="Milestones">
          <Row label="Total" value={data.milestone_summary.total_milestones} />
          <Row label="Achieved" value={data.milestone_summary.achieved_count} />
          <Row label="Evidence Complete" value={data.milestone_summary.evidence_complete_count} />
          <Row label="Certified" value={data.milestone_summary.certified_count} />
        </Card>
        <Card title="Holdback Release">
          <Row label="Status" value={<Badge status={data.holdback_release.gate_status} />} />
          {data.holdback_release.gate_summary && <p className="rex-muted" style={{ marginTop: 6 }}>{data.holdback_release.gate_summary}</p>}
        </Card>
        <Card title="Warranties">
          <Row label="Claimed" value={data.warranty_summary.claimed_count} />
          <Row label="Expiring Soon" value={data.warranty_summary.expiring_soon_count} />
        </Card>
      </div>

      {data.open_issues.length > 0 && (
        <div style={{ marginTop: 20 }}>
          <h3 className="rex-h3" style={{ marginBottom: 10 }}>Open Issues ({data.open_issues.length})</h3>
          {data.open_issues.map((issue, i) => (
            <div key={i} className={`rex-alert ${issue.severity === "high" ? "rex-alert-red" : "rex-alert-amber"}`}>
              <strong style={{ textTransform: "capitalize" }}>{issue.severity}:</strong> {issue.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
