import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

const fmt = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

export default function Commitments() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null); setDetail(null);
    api(`/commitments?project_id=${selectedId}&limit=200`).then(setData).catch((e) => setError(e.message));
  }, [selectedId]);

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.commitments || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q || (r.number || "").toLowerCase().includes(q) || (r.title || "").toLowerCase().includes(q) || (r.vendor_name || "").toLowerCase().includes(q);
      const matchStatus = !statusFilter || r.status === statusFilter;
      const matchType = !typeFilter || r.commitment_type === typeFilter;
      return matchSearch && matchStatus && matchType;
    });
  }, [items, search, statusFilter, typeFilter]);

  const statuses = useMemo(() => [...new Set(items.map((r) => r.status).filter(Boolean))], [items]);
  const types = useMemo(() => [...new Set(items.map((r) => r.commitment_type).filter(Boolean))], [items]);

  const summary = useMemo(() => ({
    total: items.length,
    originalValue: items.reduce((s, r) => s + (r.original_value ?? 0), 0),
    revisedValue: items.reduce((s, r) => s + (r.revised_value ?? 0), 0),
    invoiced: items.reduce((s, r) => s + (r.invoiced_amount ?? 0), 0),
    remaining: items.reduce((s, r) => s + ((r.revised_value ?? 0) - (r.invoiced_amount ?? 0)), 0),
  }), [items]);

  function handleSelectRow(row) {
    if (selected?.id === row.id) { setSelected(null); setDetail(null); return; }
    setSelected(row);
    setDetail(null);
    setDetailLoading(true);
    api(`/commitments/${row.id}/summary`)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading commitments..." />;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Commitments</h1>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Commitments" value={summary.total} />
        <StatCard label="Original Value" value={fmt(summary.originalValue)} />
        <StatCard label="Revised Value" value={fmt(summary.revisedValue)} color="amber" />
        <StatCard label="Invoiced" value={fmt(summary.invoiced)} color="red" />
        <StatCard label="Remaining" value={fmt(summary.remaining)} color="green" />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search number, title, vendor..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 280 }}
        />
        <select className="rex-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: 160 }}>
          <option value="">All Statuses</option>
          {statuses.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <select className="rex-input" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} style={{ width: 160 }}>
          <option value="">All Types</option>
          {types.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
        </select>
        <span className="rex-muted">{filtered.length} record{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">📑</div>No commitments found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Number</th>
                <th>Title</th>
                <th>Vendor</th>
                <th>Type</th>
                <th>Status</th>
                <th style={{ textAlign: "right" }}>Original</th>
                <th style={{ textAlign: "right" }}>Approved COs</th>
                <th style={{ textAlign: "right" }}>Revised</th>
                <th style={{ textAlign: "right" }}>Invoiced</th>
                <th style={{ textAlign: "right" }}>Remaining</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr key={row.id || i} onClick={() => handleSelectRow(row)}>
                  <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.number || "—"}</span></td>
                  <td>{row.title || "—"}</td>
                  <td>{row.vendor_name || "—"}</td>
                  <td><span className="rex-muted" style={{ fontSize: 12 }}>{row.commitment_type || "—"}</span></td>
                  <td><Badge status={row.status} /></td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.original_value)}</td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.approved_co_amount)}</td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.revised_value)}</td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.invoiced_amount)}</td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt((row.revised_value ?? 0) - (row.invoiced_amount ?? 0))}</td>
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
              <div className="rex-h3">{selected.number} — {selected.title}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8 }}>
                <Badge status={selected.status} />
                {selected.commitment_type && <span className="rex-badge rex-badge-gray">{selected.commitment_type.replace(/_/g, " ")}</span>}
              </div>
            </div>
            <button className="rex-detail-panel-close" onClick={() => { setSelected(null); setDetail(null); }}>×</button>
          </div>
          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Details">
              <Row label="Vendor" value={selected.vendor_name || "—"} />
              <Row label="Type" value={selected.commitment_type || "—"} />
              <Row label="Executed Date" value={fmtDate(selected.executed_date)} />
              <Row label="Completion Date" value={fmtDate(selected.completion_date)} />
            </Card>
            <Card title="Financials">
              <Row label="Original Value" value={fmt(selected.original_value)} />
              <Row label="Approved COs" value={fmt(selected.approved_co_amount)} />
              <Row label="Revised Value" value={fmt(selected.revised_value)} />
              <Row label="Invoiced" value={fmt(selected.invoiced_amount)} />
            </Card>
            <Card title="Activity">
              {detailLoading ? <span className="rex-muted">Loading...</span> : detail ? (
                <>
                  <Row label="PCO Count" value={detail.pco_count ?? "—"} />
                  <Row label="CCO Count" value={detail.cco_count ?? "—"} />
                  <Row label="Pay Apps" value={detail.pay_app_count ?? "—"} />
                </>
              ) : <span className="rex-muted">No activity data.</span>}
            </Card>
          </div>
          {selected.scope_of_work && (
            <div style={{ marginBottom: 12 }}>
              <div className="rex-section-label" style={{ marginBottom: 6 }}>Scope of Work</div>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.scope_of_work}</p>
            </div>
          )}
          {selected.notes && (
            <div>
              <div className="rex-section-label" style={{ marginBottom: 6 }}>Notes</div>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.notes}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
