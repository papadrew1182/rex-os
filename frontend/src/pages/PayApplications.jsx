import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

const fmt = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

export default function PayApplications() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null);
    api(`/projects/${selectedId}/pay-app-summary`).then(setData).catch((e) => setError(e.message));
  }, [selectedId]);

  const filtered = useMemo(() => {
    if (!data?.pay_apps) return [];
    const q = search.toLowerCase();
    return data.pay_apps.filter((r) => {
      const matchSearch = !q || (r.number || "").toString().toLowerCase().includes(q) || (r.vendor_name || "").toLowerCase().includes(q);
      const matchStatus = !statusFilter || r.status === statusFilter;
      return matchSearch && matchStatus;
    });
  }, [data, search, statusFilter]);

  const statuses = useMemo(() => {
    if (!data?.pay_apps) return [];
    return [...new Set(data.pay_apps.map((r) => r.status).filter(Boolean))];
  }, [data]);

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading pay applications..." />;

  const summary = data.summary || {};

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Pay Applications</h1>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Pay Apps" value={summary.total_count ?? (data.pay_apps?.length || 0)} />
        <StatCard label="This Period" value={fmt(summary.this_period_amount)} color="amber" />
        <StatCard label="Total Completed" value={fmt(summary.total_completed)} color="green" />
        <StatCard label="Retention Held" value={fmt(summary.retention_held)} color="red" />
        <StatCard label="Net Due" value={fmt(summary.net_due)} />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search pay app # or vendor..."
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
        <div className="rex-empty"><div className="rex-empty-icon">📄</div>No pay applications found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Pay App #</th>
                <th>Vendor</th>
                <th>Status</th>
                <th>Period</th>
                <th style={{ textAlign: "right" }}>This Period</th>
                <th style={{ textAlign: "right" }}>Total Completed</th>
                <th style={{ textAlign: "right" }}>Retention</th>
                <th style={{ textAlign: "right" }}>Net Due</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr key={row.id || i} onClick={() => setSelected(selected?.id === row.id ? null : row)}>
                  <td><strong>{row.number || "—"}</strong></td>
                  <td>{row.vendor_name || "—"}</td>
                  <td><Badge status={row.status} /></td>
                  <td>{fmtDate(row.period_start)}{row.period_end ? ` – ${fmtDate(row.period_end)}` : ""}</td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.this_period_amount)}</td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.total_completed_amount)}</td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.retention_amount)}</td>
                  <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.net_due)}</td>
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
              <div className="rex-h3">Pay App #{selected.number} — {selected.vendor_name}</div>
              <div style={{ marginTop: 4 }}><Badge status={selected.status} /></div>
            </div>
            <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>×</button>
          </div>
          <div className="rex-grid-2">
            <Card title="Payment Details">
              <Row label="Period Start" value={fmtDate(selected.period_start)} />
              <Row label="Period End" value={fmtDate(selected.period_end)} />
              <Row label="Invoice Date" value={fmtDate(selected.invoice_date)} />
              <Row label="Due Date" value={fmtDate(selected.due_date)} />
            </Card>
            <Card title="Amounts">
              <Row label="This Period" value={fmt(selected.this_period_amount)} />
              <Row label="Total Completed" value={fmt(selected.total_completed_amount)} />
              <Row label="Retention" value={fmt(selected.retention_amount)} />
              <Row label="Net Due" value={fmt(selected.net_due)} />
            </Card>
          </div>
          {(selected.lien_waiver_status || selected.lien_waiver_received != null) && (
            <Card title="Lien Waiver" style={{ marginTop: 12 }}>
              <Row label="Status" value={<Badge status={selected.lien_waiver_status} />} />
              <Row label="Received" value={selected.lien_waiver_received ? "Yes" : "No"} />
              {selected.lien_waiver_date && <Row label="Date" value={fmtDate(selected.lien_waiver_date)} />}
            </Card>
          )}
          {selected.description && (
            <div style={{ marginTop: 12 }}>
              <div className="rex-section-label" style={{ marginBottom: 6 }}>Description</div>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.description}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
