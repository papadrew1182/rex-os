import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

const fmt = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

export default function ChangeOrders() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null); setDetail(null);
    api(`/change-events?project_id=${selectedId}&limit=200`).then(setData).catch((e) => setError(e.message));
  }, [selectedId]);

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.change_events || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q || (r.number || "").toString().toLowerCase().includes(q) || (r.title || "").toLowerCase().includes(q);
      const matchStatus = !statusFilter || r.status === statusFilter;
      return matchSearch && matchStatus;
    });
  }, [items, search, statusFilter]);

  const statuses = useMemo(() => [...new Set(items.map((r) => r.status).filter(Boolean))], [items]);

  const summary = useMemo(() => ({
    total: items.length,
    open: items.filter((r) => r.status === "open").length,
    pending: items.filter((r) => r.status === "pending" || r.status === "in_progress").length,
    totalEstimated: items.reduce((s, r) => s + (r.estimated_amount ?? 0), 0),
    approved: items.filter((r) => r.status === "closed" || r.status === "approved" || r.status === "complete"),
  }), [items]);

  const approvedAmount = summary.approved.reduce((s, r) => s + (r.estimated_amount ?? 0), 0);

  function handleSelectRow(row) {
    if (selected?.id === row.id) { setSelected(null); setDetail(null); return; }
    setSelected(row);
    setDetail(null);
    setDetailLoading(true);
    api(`/change-events/${row.id}/detail`)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading change events..." />;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Change Orders</h1>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Events" value={summary.total} />
        <StatCard label="Open" value={summary.open} color={summary.open > 0 ? "amber" : ""} />
        <StatCard label="Pending" value={summary.pending} color={summary.pending > 0 ? "amber" : ""} />
        <StatCard label="Total Estimated" value={fmt(summary.totalEstimated)} color="red" />
        <StatCard label="Approved Amount" value={fmt(approvedAmount)} color="green" />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search event # or title..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 280 }}
        />
        <select className="rex-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: 160 }}>
          <option value="">All Statuses</option>
          {statuses.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <span className="rex-muted">{filtered.length} record{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">🔄</div>No change events found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Event #</th>
                <th>Title</th>
                <th>Status</th>
                <th>Scope</th>
                <th>Reason</th>
                <th>Type</th>
                <th style={{ textAlign: "right" }}>Estimated Amount</th>
                <th>RFI Link</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr key={row.id || i} onClick={() => handleSelectRow(row)}>
                  <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.number || "—"}</span></td>
                  <td>{row.title || "—"}</td>
                  <td><Badge status={row.status} /></td>
                  <td><span className="rex-muted" style={{ fontSize: 12 }}>{row.scope || "—"}</span></td>
                  <td><span className="rex-muted" style={{ fontSize: 12 }}>{row.reason || "—"}</span></td>
                  <td><span className="rex-muted" style={{ fontSize: 12 }}>{row.change_event_type || row.type || "—"}</span></td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.estimated_amount)}</td>
                  <td>{row.rfi_number ? <span className="rex-badge rex-badge-purple">RFI {row.rfi_number}</span> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <div className="rex-detail-panel">
          <div className="rex-detail-panel-header">
            <div>
              <div className="rex-h3">Event #{selected.number} — {selected.title}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8 }}>
                <Badge status={selected.status} />
                {selected.change_event_type && <span className="rex-badge rex-badge-gray">{selected.change_event_type}</span>}
              </div>
            </div>
            <button className="rex-detail-panel-close" onClick={() => { setSelected(null); setDetail(null); }}>×</button>
          </div>
          <div className="rex-grid-2" style={{ marginBottom: 14 }}>
            <Card title="Event Details">
              <Row label="Scope" value={selected.scope || "—"} />
              <Row label="Reason" value={selected.reason || "—"} />
              <Row label="Type" value={selected.change_event_type || selected.type || "—"} />
              <Row label="Estimated Amount" value={fmt(selected.estimated_amount)} />
              <Row label="Created" value={fmtDate(selected.created_at)} />
            </Card>
            <Card title="Linked Items">
              {detailLoading ? <span className="rex-muted">Loading...</span> : detail ? (
                <>
                  {detail.pcos?.length > 0 && (
                    <div style={{ marginBottom: 8 }}>
                      <div className="rex-section-label" style={{ marginBottom: 4 }}>PCOs ({detail.pcos.length})</div>
                      {detail.pcos.map((p, j) => (
                        <div key={j} style={{ fontSize: 12, padding: "3px 0", borderBottom: "1px solid var(--rex-border)" }}>
                          <strong>{p.number}</strong> — {p.title} <Badge status={p.status} />
                        </div>
                      ))}
                    </div>
                  )}
                  {detail.ccos?.length > 0 && (
                    <div>
                      <div className="rex-section-label" style={{ marginBottom: 4 }}>CCOs ({detail.ccos.length})</div>
                      {detail.ccos.map((c, j) => (
                        <div key={j} style={{ fontSize: 12, padding: "3px 0", borderBottom: "1px solid var(--rex-border)" }}>
                          <strong>{c.number}</strong> — {c.title} <Badge status={c.status} />
                        </div>
                      ))}
                    </div>
                  )}
                  {(!detail.pcos?.length && !detail.ccos?.length) && <span className="rex-muted">No linked PCOs or CCOs.</span>}
                </>
              ) : <span className="rex-muted">No additional details.</span>}
            </Card>
          </div>
          {selected.description && (
            <div>
              <div className="rex-section-label" style={{ marginBottom: 6 }}>Description</div>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.description}</p>
            </div>
          )}
          {detail?.line_items?.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <div className="rex-section-label" style={{ marginBottom: 8 }}>Line Items</div>
              <div className="rex-table-wrap">
                <table className="rex-table">
                  <thead>
                    <tr><th>Description</th><th style={{ textAlign: "right" }}>Amount</th></tr>
                  </thead>
                  <tbody>
                    {detail.line_items.map((li, j) => (
                      <tr key={j}>
                        <td>{li.description || "—"}</td>
                        <td style={{ textAlign: "right" }} className="rex-money">{fmt(li.amount)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
