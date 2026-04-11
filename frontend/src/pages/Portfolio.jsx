import { useState, useEffect, useMemo } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, PageLoader, Flash } from "../ui";

const TEST_RE = /^(Test |VF-|WS-|H-Orphan|K-Orphan|Orphan-|SCOPE-|SEC-|ROLLBACK-|SprintE-|Aging-|SubAging-)/i;

export default function Portfolio() {
  const { select } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [hideTest, setHideTest] = useState(true);

  useEffect(() => { api("/closeout-readiness/portfolio?limit=500").then(setData).catch((e) => setError(e.message)); }, []);

  const filtered = useMemo(() => {
    if (!data) return [];
    let list = data.projects;
    if (hideTest) list = list.filter((p) => !TEST_RE.test(p.project_name) && !TEST_RE.test(p.project_number || ""));
    if (statusFilter) list = list.filter((p) => p.readiness_status === statusFilter);
    if (search) { const q = search.toLowerCase(); list = list.filter((p) => p.project_name.toLowerCase().includes(q) || (p.project_number || "").toLowerCase().includes(q)); }
    return list;
  }, [data, search, statusFilter, hideTest]);

  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading portfolio..." />;
  const { summary } = data;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 16 }}>Portfolio Closeout Readiness</h1>

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
          <table className="rex-table">
            <thead><tr><th>Project</th><th>Status</th><th>Checklist</th><th>Milestones</th><th>Holdback</th><th>Issues</th></tr></thead>
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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
