import { useState, useEffect, useCallback } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../api";
import { StatCard, PageLoader, Flash, Spinner } from "../ui";
import { usePermissions } from "../permissions";

const fmtDate = (d) => d ? new Date(d).toLocaleString() : "—";
const fmtDuration = (ms) => ms == null ? "—" : ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(2)}s`;

function statusBadge(status) {
  if (!status) return null;
  const cls = {
    succeeded: "rex-badge-green",
    running: "rex-badge-purple",
    failed: "rex-badge-red",
    skipped: "rex-badge-gray",
  }[status] || "rex-badge-gray";
  return <span className={`rex-badge ${cls}`}>{status}</span>;
}

export default function AdminJobs() {
  const { isAdminOrVp } = usePermissions();
  const [jobs, setJobs] = useState(null);
  const [error, setError] = useState(null);
  const [running, setRunning] = useState({}); // job_key → bool
  const [history, setHistory] = useState({}); // job_key → list
  const [expanded, setExpanded] = useState(null);
  const [flash, setFlash] = useState(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const list = await api("/admin/jobs");
      setJobs(Array.isArray(list) ? list : []);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => { if (isAdminOrVp) refresh(); }, [isAdminOrVp, refresh]);

  if (!isAdminOrVp) return <Navigate to="/" replace />;

  async function handleRun(jobKey) {
    setRunning((prev) => ({ ...prev, [jobKey]: true }));
    setFlash(null);
    try {
      const r = await api(`/admin/jobs/${jobKey}/run`, { method: "POST", body: {} });
      if (r.triggered) {
        setFlash({ type: "success", message: `${jobKey} ran successfully.` });
      } else {
        setFlash({ type: "error", message: `${jobKey} skipped: ${r.skipped_reason || "unknown"}` });
      }
      await refresh();
      // Refresh history if expanded
      if (expanded === jobKey) await loadHistory(jobKey);
    } catch (e) {
      setFlash({ type: "error", message: e.message });
    } finally {
      setRunning((prev) => ({ ...prev, [jobKey]: false }));
    }
  }

  async function loadHistory(jobKey) {
    try {
      const runs = await api(`/admin/job-runs?job_key=${jobKey}&limit=20`);
      setHistory((prev) => ({ ...prev, [jobKey]: Array.isArray(runs) ? runs : [] }));
    } catch {
      setHistory((prev) => ({ ...prev, [jobKey]: [] }));
    }
  }

  async function toggleExpand(jobKey) {
    if (expanded === jobKey) {
      setExpanded(null);
    } else {
      setExpanded(jobKey);
      if (!history[jobKey]) await loadHistory(jobKey);
    }
  }

  if (error) return <Flash type="error" message={error} />;
  if (jobs === null) return <PageLoader text="Loading jobs..." />;

  const succeeded = jobs.filter((j) => j.last_run?.status === "succeeded").length;
  const failed = jobs.filter((j) => j.last_run?.status === "failed").length;
  const running_now = jobs.filter((j) => j.is_running).length;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Operations · Background Jobs</h1>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Admin/VP only · scheduled background jobs and run history.</p>

      <div className="rex-grid-4" style={{ marginBottom: 20 }}>
        <StatCard label="Total Jobs" value={jobs.length} />
        <StatCard label="Healthy" value={succeeded} color="green" />
        <StatCard label="Failed (last run)" value={failed} color={failed > 0 ? "red" : ""} />
        <StatCard label="Running" value={running_now} color={running_now > 0 ? "amber" : ""} />
      </div>

      {flash && <Flash type={flash.type} message={flash.message} onDismiss={() => setFlash(null)} />}

      <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 16 }}>
        {jobs.map((job) => {
          const isExpanded = expanded === job.job_key;
          const isRunning = running[job.job_key] || job.is_running;
          return (
            <div key={job.job_key} className="rex-card">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
                    <span className="rex-h4" style={{ margin: 0 }}>{job.name}</span>
                    {job.last_run && statusBadge(job.last_run.status)}
                    {job.enabled
                      ? <span className="rex-badge rex-badge-green" style={{ fontSize: 10 }}>ENABLED</span>
                      : <span className="rex-badge rex-badge-gray" style={{ fontSize: 10 }}>DISABLED</span>
                    }
                  </div>
                  <div className="rex-muted" style={{ fontSize: 12 }}>{job.description}</div>
                  <div className="rex-muted" style={{ fontSize: 11, marginTop: 4, fontFamily: "monospace" }}>
                    key: <strong>{job.job_key}</strong> · schedule: {job.schedule || "manual only"}
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginTop: 10, fontSize: 12 }}>
                    <div>
                      <div className="rex-muted" style={{ fontSize: 11, textTransform: "uppercase", fontWeight: 700 }}>Last run</div>
                      <div>{fmtDate(job.last_run?.finished_at || job.last_run?.started_at)}</div>
                      {job.last_run?.duration_ms != null && <div className="rex-muted" style={{ fontSize: 11 }}>{fmtDuration(job.last_run.duration_ms)}</div>}
                    </div>
                    <div>
                      <div className="rex-muted" style={{ fontSize: 11, textTransform: "uppercase", fontWeight: 700 }}>Last success</div>
                      <div>{fmtDate(job.last_success?.finished_at)}</div>
                    </div>
                    <div>
                      <div className="rex-muted" style={{ fontSize: 11, textTransform: "uppercase", fontWeight: 700 }}>Last failure</div>
                      <div style={{ color: job.last_failure ? "var(--rex-red)" : "inherit" }}>{fmtDate(job.last_failure?.finished_at)}</div>
                    </div>
                  </div>
                  {job.last_run?.summary && (
                    <div style={{ marginTop: 8, padding: "6px 10px", background: "var(--rex-bg-stripe)", borderRadius: 4, fontSize: 12, fontFamily: "monospace", color: "var(--rex-text-muted)" }}>
                      {job.last_run.summary}
                    </div>
                  )}
                  {job.last_failure?.error_excerpt && (
                    <div style={{ marginTop: 8, padding: "6px 10px", background: "var(--rex-red-bg)", borderLeft: "3px solid var(--rex-red)", borderRadius: 4, fontSize: 11, fontFamily: "monospace", color: "var(--rex-red)", maxHeight: 120, overflowY: "auto" }}>
                      {job.last_failure.error_excerpt.split("\n").slice(0, 4).join("\n")}
                    </div>
                  )}
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <button
                    className="rex-btn rex-btn-primary"
                    onClick={() => handleRun(job.job_key)}
                    disabled={isRunning}
                    style={{ minWidth: 100 }}
                  >
                    {isRunning ? <Spinner size={12} /> : "Run now"}
                  </button>
                  <button
                    className="rex-btn rex-btn-outline"
                    onClick={() => toggleExpand(job.job_key)}
                    style={{ minWidth: 100, fontSize: 12 }}
                  >
                    {isExpanded ? "Hide history" : "History"}
                  </button>
                </div>
              </div>

              {isExpanded && (
                <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--rex-border)" }}>
                  <div className="rex-h4" style={{ marginBottom: 8 }}>Recent runs</div>
                  {history[job.job_key] === undefined ? (
                    <Spinner size={16} />
                  ) : history[job.job_key].length === 0 ? (
                    <p className="rex-muted" style={{ fontSize: 12 }}>No run history yet.</p>
                  ) : (
                    <div className="rex-table-wrap">
                      <table className="rex-table">
                        <thead>
                          <tr>
                            <th>Status</th>
                            <th>Started</th>
                            <th>Duration</th>
                            <th>Trigger</th>
                            <th>Summary</th>
                          </tr>
                        </thead>
                        <tbody>
                          {history[job.job_key].map((run) => (
                            <tr key={run.id}>
                              <td>{statusBadge(run.status)}</td>
                              <td style={{ fontSize: 11 }}>{fmtDate(run.started_at)}</td>
                              <td style={{ fontSize: 11 }}>{fmtDuration(run.duration_ms)}</td>
                              <td style={{ fontSize: 11 }}><span className="rex-badge rex-badge-gray" style={{ fontSize: 9 }}>{run.triggered_by}</span></td>
                              <td style={{ fontSize: 11, maxWidth: 360, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={run.summary || run.error_excerpt}>
                                {run.summary || run.error_excerpt || "—"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
