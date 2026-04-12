import { useState, useEffect, useCallback } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { useProject } from "../project";
import { Badge, Card, Row, ProgressBar, PageLoader, Flash, Spinner } from "../ui";
import { FormDrawer, useFormState, Field, NumberField, DateField, TextArea, Select } from "../forms";
import { usePermissions } from "../permissions";

// ─── helpers ──────────────────────────────────────────────────────────────────

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

function milestoneHealth(m) {
  if (m.status === "achieved") return { label: "ACHIEVED", color: "rex-badge-green" };
  if (m.status === "overdue")  return { label: "OVERDUE",  color: "rex-badge-red"   };
  if (!m.scheduled_date)       return { label: "UNSCHEDULED", color: "rex-badge-gray" };
  const today = new Date();
  const sched = new Date(m.scheduled_date + "T00:00:00");
  if (sched < today) return { label: "OVERDUE", color: "rex-badge-red" };
  if (m.forecast_date) {
    const forecast = new Date(m.forecast_date + "T00:00:00");
    const slipDays = Math.floor((forecast - sched) / 86400000);
    if (slipDays > 7) return { label: "AT RISK",   color: "rex-badge-red"   };
    if (slipDays > 0) return { label: "SLIPPING",  color: "rex-badge-amber" };
  }
  return { label: "ON TRACK", color: "rex-badge-green" };
}

function forecastVariantStyle(m) {
  if (!m.forecast_date || !m.scheduled_date) return {};
  const sched    = new Date(m.scheduled_date  + "T00:00:00");
  const forecast = new Date(m.forecast_date   + "T00:00:00");
  const slipDays = Math.floor((forecast - sched) / 86400000);
  if (slipDays > 7)  return { color: "var(--rex-red)"   };
  if (slipDays > 0)  return { color: "var(--rex-amber)" };
  return { color: "var(--rex-green)" };
}

// ─── Edit-milestone drawer ─────────────────────────────────────────────────

const STATUS_OPTS = ["pending", "achieved", "overdue"];

function EditMilestoneDrawer({ open, onClose, milestone, onSaved }) {
  const { values, setField, reset, dirty } = useFormState(
    milestone ? {
      milestone_name:   milestone.milestone_name   ?? "",
      status:           milestone.status            ?? "pending",
      scheduled_date:   milestone.scheduled_date    ?? null,
      forecast_date:    milestone.forecast_date     ?? null,
      actual_date:      milestone.actual_date        ?? null,
      percent_complete: milestone.percent_complete  ?? 0,
      variance_days:    milestone.variance_days     ?? null,
      notes:            milestone.notes              ?? "",
      sort_order:       milestone.sort_order        ?? null,
    } : {}
  );
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const updated = await api(`/completion-milestones/${milestone.id}`, {
        method: "PATCH",
        body: values,
      });
      onSaved(updated);
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <FormDrawer
      open={open}
      onClose={onClose}
      title="Edit Milestone"
      subtitle={milestone?.milestone_name}
      mode="edit"
      dirty={dirty}
      submitting={submitting}
      error={error}
      onSubmit={handleSubmit}
      onReset={reset}
    >
      <Field       label="Milestone Name"   name="milestone_name"   value={values.milestone_name}   onChange={setField} required />
      <Select      label="Status"           name="status"           value={values.status}           onChange={setField} options={STATUS_OPTS} />
      <DateField   label="Scheduled Date"   name="scheduled_date"   value={values.scheduled_date}   onChange={setField} />
      <DateField   label="Forecast Date"    name="forecast_date"    value={values.forecast_date}    onChange={setField} />
      <DateField   label="Actual Date"      name="actual_date"      value={values.actual_date}      onChange={setField} />
      <NumberField label="% Complete"       name="percent_complete" value={values.percent_complete} onChange={setField} step={1} placeholder="0–100" />
      <NumberField label="Variance (days)"  name="variance_days"    value={values.variance_days}    onChange={setField} step={1} />
      <TextArea    label="Notes"            name="notes"            value={values.notes}            onChange={setField} rows={3} />
      <NumberField label="Sort Order"       name="sort_order"       value={values.sort_order}       onChange={setField} step={1} />
    </FormDrawer>
  );
}

// ─── Main page ─────────────────────────────────────────────────────────────

export default function Milestones() {
  const { user }                 = useAuth();
  const { canWrite }             = usePermissions();
  const { selected: project, selectedId } = useProject();
  const isAdmin   = user?.is_admin || user?.global_role === "vp";
  const personId  = user?.person_id;

  const [milestones, setMilestones] = useState([]);
  const [sel,        setSel]        = useState(null);
  const [evidence,   setEvidence]   = useState(null);
  const [gates,      setGates]      = useState(null);
  const [error,      setError]      = useState(null);
  const [success,    setSuccess]    = useState(null);
  const [busy,       setBusy]       = useState(false);
  const [pageLoad,   setPageLoad]   = useState(true);
  const [editOpen,   setEditOpen]   = useState(false);

  const flash = (m) => { setSuccess(m); setTimeout(() => setSuccess(null), 3000); };

  const pick = async (m) => {
    setSel(m); setEvidence(null); setGates(null); setError(null);
    try { setEvidence(await api(`/completion-milestones/${m.id}/evidence-checklist`)); } catch (e) { setEvidence({ error: e.message }); }
  };

  const load = useCallback(() => {
    if (!selectedId) return;
    setPageLoad(true);
    api(`/completion-milestones/?project_id=${selectedId}&limit=50`)
      .then((list) => {
        setMilestones(list);
        if (list.length) pick(list.find((m) => m.status === "pending") || list[0]);
      })
      .catch((e) => setError(e.message))
      .finally(() => setPageLoad(false));
  }, [selectedId]);

  useEffect(() => { setSel(null); setEvidence(null); setGates(null); load(); }, [selectedId]);

  const refresh = async () => {
    const ms = await api(`/completion-milestones/?project_id=${selectedId}&limit=50`);
    setMilestones(ms);
    if (sel) { const f = ms.find((m) => m.id === sel.id); if (f) setSel(f); }
  };

  // existing workflows — unchanged
  const evalEvidence = async () => {
    setBusy(true); setError(null);
    try {
      await api(`/completion-milestones/${sel.id}/evaluate-evidence`, { method: "POST", body: { all_items_complete: true, notes: "All confirmed" } });
      await refresh();
      setEvidence(await api(`/completion-milestones/${sel.id}/evidence-checklist`));
      flash("Evidence complete");
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  const certify = async () => {
    setBusy(true); setError(null);
    try {
      await api(`/completion-milestones/${sel.id}/certify`, { method: "POST", body: { certified_by: personId, actual_date: new Date().toISOString().slice(0, 10), notes: "Certified via UI" } });
      await refresh();
      flash("Milestone certified");
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  const evalGates = async () => {
    setBusy(true); setError(null);
    try { setGates(await api(`/completion-milestones/${sel.id}/evaluate-gates`, { method: "POST" })); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  // called after successful edit save
  const handleSaved = (updated) => {
    setMilestones((prev) => prev.map((m) => m.id === updated.id ? updated : m));
    setSel(updated);
    flash("Milestone updated");
  };

  if (!selectedId) return <p className="rex-muted">Select a project.</p>;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Completion Milestones</h1>
      <p className="rex-muted" style={{ marginBottom: 16 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>
      <Flash type="error" message={error} onDismiss={() => setError(null)} />
      <Flash message={success} />

      {pageLoad ? <PageLoader text="Loading milestones..." /> : (
        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 14 }}>

          {/* ── Sidebar list ── */}
          <div className="rex-card" style={{ padding: 0, maxHeight: 600, overflowY: "auto" }}>
            {milestones.length === 0
              ? <p className="rex-muted" style={{ padding: 16 }}>No milestones.</p>
              : milestones.map((m) => {
                  const health    = milestoneHealth(m);
                  const pct       = m.percent_complete ?? 0;
                  const hasForecast = !!m.forecast_date;
                  const fStyle    = forecastVariantStyle(m);

                  return (
                    <div
                      key={m.id}
                      onClick={() => pick(m)}
                      style={{
                        padding: "10px 16px",
                        cursor: "pointer",
                        borderBottom: "1px solid var(--rex-border)",
                        background: sel?.id === m.id ? "var(--rex-accent-light)" : "transparent",
                      }}
                    >
                      {/* name + type + status badges */}
                      <div style={{ fontWeight: 600, fontSize: 14 }}>{m.milestone_name}</div>
                      <div style={{ display: "flex", gap: 6, alignItems: "center", marginTop: 3, flexWrap: "wrap" }}>
                        <span className="rex-muted" style={{ fontSize: 12 }}>{m.milestone_type?.replace(/_/g, " ")}</span>
                        <Badge status={m.status} />
                        {m.is_evidence_complete && <Badge status="pass" label="evidence" />}
                        <span className={`rex-badge ${health.color}`} style={{ fontSize: 10 }}>{health.label}</span>
                      </div>

                      {/* progress bar */}
                      <div style={{ marginTop: 6 }}>
                        <ProgressBar pct={pct} height={4} />
                      </div>

                      {/* date row */}
                      <div style={{ display: "flex", gap: 8, marginTop: 4, fontSize: 11, color: "var(--rex-muted)" }}>
                        {m.scheduled_date && <span>Sched: {fmtDate(m.scheduled_date)}</span>}
                        {hasForecast && (
                          <span style={fStyle}>Fcst: {fmtDate(m.forecast_date)}</span>
                        )}
                      </div>
                    </div>
                  );
                })}
          </div>

          {/* ── Detail panel ── */}
          <div>
            {sel ? (
              <>
                {/* header */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
                  <h2 className="rex-h2">{sel.milestone_name}</h2>
                  <Badge status={sel.status} />
                  {sel.is_evidence_complete && <Badge status="pass" label="evidence" />}
                  {(() => {
                    const h = milestoneHealth(sel);
                    return <span className={`rex-badge ${h.color}`}>{h.label}</span>;
                  })()}
                  {canWrite && (
                    <button
                      className="rex-btn rex-btn-outline"
                      style={{ marginLeft: "auto", fontSize: 12 }}
                      onClick={() => setEditOpen(true)}
                    >
                      Edit Milestone
                    </button>
                  )}
                </div>

                {/* ── Schedule & Progress card ── */}
                <Card title="Schedule & Progress">
                  {(() => {
                    const isSlipping = sel.forecast_date && sel.scheduled_date &&
                      new Date(sel.forecast_date + "T00:00:00") > new Date(sel.scheduled_date + "T00:00:00");
                    const pct = sel.percent_complete ?? 0;
                    return (
                      <>
                        <Row label="Scheduled Date" value={fmtDate(sel.scheduled_date)} />
                        <Row
                          label="Forecast Date"
                          value={
                            <span style={isSlipping ? { color: "var(--rex-red)", fontWeight: 600 } : {}}>
                              {fmtDate(sel.forecast_date)}
                            </span>
                          }
                        />
                        <Row label="Actual Date"    value={fmtDate(sel.actual_date)} />
                        <Row
                          label="Variance"
                          value={sel.variance_days != null ? `${sel.variance_days}d` : "—"}
                        />
                        <Row
                          label="Progress"
                          value={
                            <span style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 120 }}>
                              <span style={{ flex: 1 }}><ProgressBar pct={pct} height={6} /></span>
                              <span style={{ fontSize: 12, whiteSpace: "nowrap" }}>{Math.round(pct)}%</span>
                            </span>
                          }
                        />
                        {(sel.status === "overdue" || isSlipping) && (
                          <div style={{
                            marginTop: 8,
                            padding: "6px 10px",
                            background: "var(--rex-red-bg, rgba(239,68,68,0.08))",
                            borderLeft: "3px solid var(--rex-red)",
                            borderRadius: 4,
                            fontSize: 12,
                            color: "var(--rex-red)",
                          }}>
                            {sel.status === "overdue" ? "This milestone is overdue." : "Forecast date is later than scheduled date."}
                          </div>
                        )}
                      </>
                    );
                  })()}
                </Card>

                {/* ── Evidence Checklist card — unchanged ── */}
                <Card title="Evidence Checklist">
                  {evidence?.error
                    ? <p style={{ color: "var(--rex-red)", fontSize: 13 }}>Failed: {evidence.error}</p>
                    : !evidence
                    ? <Spinner size={20} />
                    : evidence.checklist?.length === 0
                    ? <p className="rex-muted">No evidence items defined.</p>
                    : <>
                        {evidence.checklist.map((ev, i) => (
                          <div key={i} style={{ padding: "4px 0", fontSize: 14, display: "flex", gap: 8 }}>
                            <span>{ev.is_complete ? "✅" : "⬜"}</span>
                            <span>{ev.item}{ev.source && <span className="rex-muted" style={{ marginLeft: 6 }}>({ev.source})</span>}</span>
                          </div>
                        ))}
                        {sel.is_evidence_complete
                          ? <p style={{ color: "var(--rex-green)", marginTop: 8, fontWeight: 600, fontSize: 13 }}>All evidence confirmed.</p>
                          : <button onClick={evalEvidence} disabled={busy} className="rex-btn rex-btn-primary" style={{ marginTop: 10 }}>
                              {busy ? <><Spinner size={14} /> Saving...</> : "Mark All Evidence Complete"}
                            </button>
                        }
                      </>}
                </Card>

                {/* ── Certification card — unchanged ── */}
                <Card title="Certification">
                  {sel.status === "achieved"
                    ? <p style={{ color: "var(--rex-green)", fontWeight: 600 }}>Milestone is certified.</p>
                    : isAdmin
                    ? <button onClick={certify} disabled={busy} className="rex-btn rex-btn-primary">
                        {busy ? <><Spinner size={14} /> Certifying...</> : "Certify Milestone"}
                      </button>
                    : <p className="rex-muted">Only admins can certify.</p>}
                </Card>

                {/* ── Gate Evaluation card — unchanged ── */}
                <Card title="Gate Evaluation">
                  {isAdmin
                    ? <button onClick={evalGates} disabled={busy} className="rex-btn rex-btn-primary">
                        {busy ? <><Spinner size={14} /> Evaluating...</> : "Evaluate Gates"}
                      </button>
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

      {/* Edit drawer — outside the grid so it overlays correctly */}
      {sel && (
        <EditMilestoneDrawer
          open={editOpen}
          onClose={() => setEditOpen(false)}
          milestone={sel}
          onSaved={handleSaved}
        />
      )}
    </div>
  );
}
