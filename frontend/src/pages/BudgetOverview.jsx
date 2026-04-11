import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

const fmt = (n) => n == null ? "—" : "$" + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function BudgetOverview() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null);
    api(`/projects/${selectedId}/budget-summary`).then(setData).catch((e) => setError(e.message));
  }, [selectedId]);

  const filtered = useMemo(() => {
    if (!data?.line_items) return [];
    const q = search.toLowerCase();
    return data.line_items.filter((r) =>
      !q || (r.cost_code || "").toLowerCase().includes(q) || (r.description || "").toLowerCase().includes(q)
    );
  }, [data, search]);

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading budget..." />;

  const summary = data.summary || {};
  const overUnder = (summary.projected_cost ?? 0) - (summary.revised_budget ?? 0);
  const overUnderColor = overUnder > 0 ? "red" : "green";

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Budget Overview</h1>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Original Budget" value={fmt(summary.original_budget)} />
        <StatCard label="Revised Budget" value={fmt(summary.revised_budget)} />
        <StatCard label="Committed" value={fmt(summary.committed_cost)} color="amber" />
        <StatCard label="Projected" value={fmt(summary.projected_cost)} />
        <StatCard label="Over / Under" value={fmt(Math.abs(overUnder))} color={overUnderColor} sub={overUnder > 0 ? "Over Budget" : "Under Budget"} />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search cost code or description..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 340 }}
        />
        <span className="rex-muted">{filtered.length} line item{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">📋</div>No line items found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Cost Code</th>
                <th>Description</th>
                <th style={{ textAlign: "right" }}>Original</th>
                <th style={{ textAlign: "right" }}>Changes</th>
                <th style={{ textAlign: "right" }}>Revised</th>
                <th style={{ textAlign: "right" }}>Committed</th>
                <th style={{ textAlign: "right" }}>Direct</th>
                <th style={{ textAlign: "right" }}>Pending</th>
                <th style={{ textAlign: "right" }}>Projected</th>
                <th style={{ textAlign: "right" }}>Over / Under</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => {
                const ou = (row.projected_cost ?? 0) - (row.revised_budget ?? 0);
                return (
                  <tr key={row.id || i} onClick={() => setSelected(selected?.id === row.id ? null : row)}>
                    <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.cost_code || "—"}</span></td>
                    <td>{row.description || "—"}</td>
                    <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.original_budget)}</td>
                    <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.approved_changes)}</td>
                    <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.revised_budget)}</td>
                    <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.committed_cost)}</td>
                    <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.direct_cost)}</td>
                    <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.pending_changes)}</td>
                    <td style={{ textAlign: "right" }} className="rex-money">{fmt(row.projected_cost)}</td>
                    <td style={{ textAlign: "right" }} className={`rex-money ${ou > 0 ? "rex-text-red" : "rex-text-green"}`}>
                      {fmt(Math.abs(ou))}{ou > 0 ? " ▲" : " ▼"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <div className="rex-detail-panel" style={{ marginTop: 16 }}>
          <div className="rex-detail-panel-header">
            <div>
              <div className="rex-h3">{selected.cost_code} — {selected.description}</div>
            </div>
            <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>×</button>
          </div>
          <div className="rex-grid-3">
            <Card title="Budget">
              <Row label="Original" value={fmt(selected.original_budget)} />
              <Row label="Approved Changes" value={fmt(selected.approved_changes)} />
              <Row label="Revised Budget" value={fmt(selected.revised_budget)} />
            </Card>
            <Card title="Costs">
              <Row label="Committed" value={fmt(selected.committed_cost)} />
              <Row label="Direct Cost" value={fmt(selected.direct_cost)} />
              <Row label="Pending Changes" value={fmt(selected.pending_changes)} />
            </Card>
            <Card title="Forecast">
              <Row label="Projected Cost" value={fmt(selected.projected_cost)} />
              <Row label="Over / Under" value={
                <span className={(selected.projected_cost ?? 0) - (selected.revised_budget ?? 0) > 0 ? "rex-text-red" : "rex-text-green"}>
                  {fmt(Math.abs((selected.projected_cost ?? 0) - (selected.revised_budget ?? 0)))}
                </span>
              } />
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
