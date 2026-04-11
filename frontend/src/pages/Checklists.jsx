import { useState, useEffect, useCallback } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { useProject } from "../project";
import { Badge, ProgressBar, PageLoader, Flash, Spinner } from "../ui";

const TEMPLATE_STANDARD = "a0000001-0000-0000-0000-000000000001";

export default function Checklists() {
  const { user } = useAuth();
  const { selected: project, selectedId } = useProject();
  const isAdmin = user?.is_admin || user?.global_role === "vp";
  const [checklists, setChecklists] = useState([]);
  const [sel, setSel] = useState(null);
  const [items, setItems] = useState([]);
  const [pageLoad, setPageLoad] = useState(true);
  const [itemLoad, setItemLoad] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [creating, setCreating] = useState(false);
  const [scDate, setScDate] = useState("2026-06-01");

  const flash = (m) => { setSuccess(m); setTimeout(() => setSuccess(null), 3000); };
  const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "";

  const load = useCallback(() => {
    if (!selectedId) return;
    setPageLoad(true);
    api(`/closeout-checklists/?project_id=${selectedId}&limit=50`).then(setChecklists).catch((e) => setError(e.message)).finally(() => setPageLoad(false));
  }, [selectedId]);

  useEffect(() => { setSel(null); setItems([]); load(); }, [load]);

  const pick = async (cl) => {
    setSel(cl); setItems([]); setItemLoad(true);
    try { setItems(await api(`/closeout-checklist-items/?checklist_id=${cl.id}&limit=200`)); } catch (e) { setError(e.message); }
    finally { setItemLoad(false); }
  };

  const create = async () => {
    setCreating(true); setError(null);
    try {
      const cl = await api("/closeout-checklists/from-template", { method: "POST", body: { project_id: selectedId, template_id: TEMPLATE_STANDARD, substantial_completion_date: scDate } });
      load(); pick(cl); flash(`Checklist created — ${cl.total_items} items`);
    } catch (e) { setError(e.message); }
    finally { setCreating(false); }
  };

  const toggle = async (item) => {
    setItemLoad(true); setError(null);
    try {
      const body = { status: item.status === "complete" ? "not_started" : "complete" };
      if (body.status === "complete") body.completed_date = new Date().toISOString().slice(0, 10);
      await api(`/closeout-checklist-items/${item.id}`, { method: "PATCH", body });
      const [fi, fc] = await Promise.all([api(`/closeout-checklist-items/?checklist_id=${sel.id}&limit=200`), api(`/closeout-checklists/${sel.id}`)]);
      setItems(fi); setSel(fc); load();
    } catch (e) { setError(e.message); }
    finally { setItemLoad(false); }
  };

  if (!selectedId) return <p className="rex-muted">Select a project.</p>;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Closeout Checklists</h1>
      <p className="rex-muted" style={{ marginBottom: 16 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <Flash type="error" message={error} onDismiss={() => setError(null)} />
      <Flash message={success} />

      {isAdmin && (
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16, background: "var(--rex-accent-lighter)", padding: "10px 14px", borderRadius: 8 }}>
          <span className="rex-section-label">Substantial Completion:</span>
          <input type="date" value={scDate} onChange={(e) => setScDate(e.target.value)} className="rex-input" />
          <button onClick={create} disabled={creating} className="rex-btn rex-btn-primary">
            {creating ? <><Spinner size={14} /> Creating...</> : "Create from Template"}
          </button>
        </div>
      )}

      {pageLoad ? <PageLoader text="Loading checklists..." /> : (
        <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 14 }}>
          {/* Sidebar */}
          <div className="rex-card" style={{ padding: 0, overflow: "hidden", maxHeight: 550, overflowY: "auto" }}>
            {checklists.length === 0 ? (
              <p className="rex-muted" style={{ padding: 16 }}>No checklists.{isAdmin ? " Create one above." : ""}</p>
            ) : checklists.map((cl, i) => (
              <div key={cl.id} onClick={() => pick(cl)} style={{
                padding: "12px 16px", cursor: "pointer", borderBottom: "1px solid var(--rex-border)",
                background: sel?.id === cl.id ? "var(--rex-accent-light)" : "transparent",
              }}>
                <div style={{ fontWeight: 700, fontSize: 13 }}>Checklist {i + 1}
                  {cl.substantial_completion_date && <span className="rex-muted" style={{ fontWeight: 400, marginLeft: 6 }}>SC {fmtDate(cl.substantial_completion_date)}</span>}
                </div>
                <div className="rex-muted" style={{ fontSize: 12 }}>{cl.completed_items}/{cl.total_items} ({cl.percent_complete?.toFixed(0)}%)</div>
                <ProgressBar pct={cl.percent_complete || 0} height={4} />
              </div>
            ))}
          </div>

          {/* Items */}
          <div>
            {sel ? (
              <>
                <div style={{ marginBottom: 14 }}>
                  <h2 className="rex-h2">{sel.percent_complete?.toFixed(1)}% complete</h2>
                  <span className="rex-muted">{sel.completed_items} of {sel.total_items} items done</span>
                  <ProgressBar pct={sel.percent_complete || 0} height={8} />
                </div>
                {itemLoad && items.length === 0 ? <PageLoader text="Loading items..." /> : items.length === 0 ? <p className="rex-muted">No items.</p> : (
                  <div className="rex-card" style={{ padding: 0 }}>
                    {items.map((item, idx) => (
                      <div key={item.id} style={{
                        display: "flex", alignItems: "center", gap: 12, padding: "10px 16px",
                        borderBottom: idx < items.length - 1 ? "1px solid var(--rex-border)" : "none",
                        background: idx % 2 === 1 ? "var(--rex-bg-stripe)" : "transparent",
                        opacity: itemLoad ? 0.6 : 1,
                      }}>
                        <input type="checkbox" checked={item.status === "complete"} onChange={() => toggle(item)} disabled={itemLoad}
                          style={{ width: 18, height: 18, accentColor: "var(--rex-accent)", cursor: "pointer", flexShrink: 0 }} />
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 500, textDecoration: item.status === "complete" ? "line-through" : "none", color: item.status === "complete" ? "var(--rex-text-muted)" : "var(--rex-text)" }}>
                            {item.name || `Item ${item.sort_order}`}
                          </div>
                          <div style={{ fontSize: 11, color: "var(--rex-text-faint)" }}>
                            {item.category}{item.due_date && <span style={{ marginLeft: 8 }}>Due {fmtDate(item.due_date)}</span>}
                          </div>
                        </div>
                        <Badge status={item.status} />
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : <p className="rex-muted" style={{ textAlign: "center", padding: "2rem 0" }}>Select a checklist.</p>}
          </div>
        </div>
      )}
    </div>
  );
}
