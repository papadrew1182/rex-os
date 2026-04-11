import { useState, useEffect, useCallback } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { useProject } from "../project";
import { Badge, Card, PageLoader, Flash, Spinner } from "../ui";

export default function Milestones() {
  const { user } = useAuth();
  const { selected: project, selectedId } = useProject();
  const isAdmin = user?.is_admin || user?.global_role === "vp";
  const personId = user?.person_id;
  const [milestones, setMilestones] = useState([]);
  const [sel, setSel] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [gates, setGates] = useState(null);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [busy, setBusy] = useState(false);
  const [pageLoad, setPageLoad] = useState(true);

  const flash = (m) => { setSuccess(m); setTimeout(() => setSuccess(null), 3000); };

  const pick = async (m) => {
    setSel(m); setEvidence(null); setGates(null); setError(null);
    try { setEvidence(await api(`/completion-milestones/${m.id}/evidence-checklist`)); } catch (e) { setEvidence({ error: e.message }); }
  };

  const load = useCallback(() => {
    if (!selectedId) return;
    setPageLoad(true);
    api(`/completion-milestones/?project_id=${selectedId}&limit=50`)
      .then((list) => { setMilestones(list); if (list.length) pick(list.find((m) => m.status === "pending") || list[0]); })
      .catch((e) => setError(e.message)).finally(() => setPageLoad(false));
  }, [selectedId]);

  useEffect(() => { setSel(null); setEvidence(null); setGates(null); load(); }, [selectedId]);

  const refresh = async () => {
    const ms = await api(`/completion-milestones/?project_id=${selectedId}&limit=50`);
    setMilestones(ms);
    if (sel) { const f = ms.find((m) => m.id === sel.id); if (f) setSel(f); }
  };

  const evalEvidence = async () => { setBusy(true); setError(null); try { await api(`/completion-milestones/${sel.id}/evaluate-evidence`, { method: "POST", body: { all_items_complete: true, notes: "All confirmed" } }); await refresh(); setEvidence(await api(`/completion-milestones/${sel.id}/evidence-checklist`)); flash("Evidence complete"); } catch (e) { setError(e.message); } finally { setBusy(false); } };
  const certify = async () => { setBusy(true); setError(null); try { await api(`/completion-milestones/${sel.id}/certify`, { method: "POST", body: { certified_by: personId, actual_date: new Date().toISOString().slice(0, 10), notes: "Certified via UI" } }); await refresh(); flash("Milestone certified"); } catch (e) { setError(e.message); } finally { setBusy(false); } };
  const evalGates = async () => { setBusy(true); setError(null); try { setGates(await api(`/completion-milestones/${sel.id}/evaluate-gates`, { method: "POST" })); } catch (e) { setError(e.message); } finally { setBusy(false); } };

  if (!selectedId) return <p className="rex-muted">Select a project.</p>;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Completion Milestones</h1>
      <p className="rex-muted" style={{ marginBottom: 16 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>
      <Flash type="error" message={error} onDismiss={() => setError(null)} />
      <Flash message={success} />

      {pageLoad ? <PageLoader text="Loading milestones..." /> : (
        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 14 }}>
          {/* List */}
          <div className="rex-card" style={{ padding: 0, maxHeight: 600, overflowY: "auto" }}>
            {milestones.length === 0 ? <p className="rex-muted" style={{ padding: 16 }}>No milestones.</p> : milestones.map((m) => (
              <div key={m.id} onClick={() => pick(m)} style={{
                padding: "10px 16px", cursor: "pointer", borderBottom: "1px solid var(--rex-border)",
                background: sel?.id === m.id ? "var(--rex-accent-light)" : "transparent",
              }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{m.milestone_name}</div>
                <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 3 }}>
                  <span className="rex-muted" style={{ fontSize: 12 }}>{m.milestone_type?.replace(/_/g, " ")}</span>
                  <Badge status={m.status} />
                  {m.is_evidence_complete && <Badge status="pass" label="evidence" />}
                </div>
              </div>
            ))}
          </div>

          {/* Detail */}
          <div>
            {sel ? (
              <>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
                  <h2 className="rex-h2">{sel.milestone_name}</h2>
                  <Badge status={sel.status} />
                  {sel.is_evidence_complete && <Badge status="pass" label="evidence" />}
                </div>

                <Card title="Evidence Checklist">
                  {evidence?.error ? <p style={{ color: "var(--rex-red)", fontSize: 13 }}>Failed: {evidence.error}</p>
                    : !evidence ? <Spinner size={20} />
                    : evidence.checklist?.length === 0 ? <p className="rex-muted">No evidence items defined.</p>
                    : <>
                        {evidence.checklist.map((ev, i) => (
                          <div key={i} style={{ padding: "4px 0", fontSize: 14, display: "flex", gap: 8 }}>
                            <span>{ev.is_complete ? "\u2705" : "\u2B1C"}</span>
                            <span>{ev.item}{ev.source && <span className="rex-muted" style={{ marginLeft: 6 }}>({ev.source})</span>}</span>
                          </div>
                        ))}
                        {sel.is_evidence_complete
                          ? <p style={{ color: "var(--rex-green)", marginTop: 8, fontWeight: 600, fontSize: 13 }}>All evidence confirmed.</p>
                          : <button onClick={evalEvidence} disabled={busy} className="rex-btn rex-btn-primary" style={{ marginTop: 10 }}>{busy ? <><Spinner size={14} /> Saving...</> : "Mark All Evidence Complete"}</button>
                        }
                      </>}
                </Card>

                <Card title="Certification">
                  {sel.status === "achieved"
                    ? <p style={{ color: "var(--rex-green)", fontWeight: 600 }}>Milestone is certified.</p>
                    : isAdmin ? <button onClick={certify} disabled={busy} className="rex-btn rex-btn-primary">{busy ? <><Spinner size={14} /> Certifying...</> : "Certify Milestone"}</button>
                    : <p className="rex-muted">Only admins can certify.</p>}
                </Card>

                <Card title="Gate Evaluation">
                  {isAdmin ? <button onClick={evalGates} disabled={busy} className="rex-btn rex-btn-primary">{busy ? <><Spinner size={14} /> Evaluating...</> : "Evaluate Gates"}</button>
                    : <p className="rex-muted">Only admins can evaluate gates.</p>}
                  {gates && (
                    <div style={{ marginTop: 12 }}>
                      <div style={{ marginBottom: 8 }}><strong>Overall:</strong> <Badge status={gates.gate_status} /></div>
                      <p className="rex-muted" style={{ marginBottom: 8 }}>{gates.summary_message}</p>
                      <div className="rex-card" style={{ padding: 0 }}>
                        {gates.gate_results?.map((g, i) => (
                          <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "8px 14px", borderBottom: i < gates.gate_results.length - 1 ? "1px solid var(--rex-border)" : "none", fontSize: 14 }}>
                            <span>{g.gate_name}</span><Badge status={g.status} />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              </>
            ) : <p className="rex-muted" style={{ textAlign: "center", padding: "2rem 0" }}>Select a milestone.</p>}
          </div>
        </div>
      )}
    </div>
  );
}
