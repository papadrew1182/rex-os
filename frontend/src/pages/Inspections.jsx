import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

function resultBadge(result) {
  if (result === "pass") return <span className="rex-badge rex-badge-green">pass</span>;
  if (result === "fail") return <span className="rex-badge rex-badge-red">fail</span>;
  if (result === "n_a") return <span className="rex-badge rex-badge-gray">n/a</span>;
  if (result === "not_inspected") return <span className="rex-badge rex-badge-amber">not inspected</span>;
  return <span className="rex-badge rex-badge-gray">{result || "—"}</span>;
}

export default function Inspections() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [inspSummary, setInspSummary] = useState(null);
  const [inspItems, setInspItems] = useState(null);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null);
    api(`/inspections?project_id=${selectedId}&limit=200`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [selectedId]);

  function handleRowClick(row) {
    if (selected?.id === row.id) { setSelected(null); setInspSummary(null); setInspItems(null); return; }
    setSelected(row);
    setInspSummary(null);
    setInspItems(null);
    api(`/inspections/${row.id}/summary`).then(setInspSummary).catch(() => setInspSummary(null));
    api(`/inspection-items?inspection_id=${row.id}&limit=100`).then(setInspItems).catch(() => setInspItems([]));
  }

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.inspections || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q
        || (r.inspection_number || "").toLowerCase().includes(q)
        || (r.title || "").toLowerCase().includes(q)
        || (r.location || "").toLowerCase().includes(q);
      const matchStatus = !statusFilter || r.status === statusFilter;
      const matchType = !typeFilter || r.inspection_type === typeFilter;
      return matchSearch && matchStatus && matchType;
    });
  }, [items, search, statusFilter, typeFilter]);

  const statuses = useMemo(() => [...new Set(items.map((r) => r.status).filter(Boolean))], [items]);
  const types = useMemo(() => [...new Set(items.map((r) => r.inspection_type).filter(Boolean))], [items]);

  const summary = useMemo(() => {
    const openScheduled = items.filter((r) => r.status === "scheduled" || r.status === "in_progress").length;
    const completed = items.filter((r) => r.status === "passed" || r.status === "failed" || r.status === "partial").length;
    const failed = items.filter((r) => r.status === "failed").length;
    const passed = items.filter((r) => r.status === "passed").length;
    const passRate = (passed + failed) > 0 ? Math.round(passed / (passed + failed) * 100) + "%" : "—";
    return { total: items.length, openScheduled, completed, failed, passRate };
  }, [items]);

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading inspections..." />;

  const itemsList = Array.isArray(inspItems) ? inspItems : (inspItems?.items || []);

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Inspections</h1>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Inspections" value={summary.total} />
        <StatCard label="Open / Scheduled" value={summary.openScheduled} color={summary.openScheduled > 0 ? "amber" : ""} />
        <StatCard label="Completed" value={summary.completed} color="green" />
        <StatCard label="Failed" value={summary.failed} color={summary.failed > 0 ? "red" : ""} />
        <StatCard label="Pass Rate" value={summary.passRate} color="green" />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search #, title, or location..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 260 }}
        />
        <select className="rex-input" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} style={{ width: 150 }}>
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
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No inspections found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Insp #</th>
                <th>Title</th>
                <th>Type</th>
                <th>Status</th>
                <th>Scheduled</th>
                <th>Completed</th>
                <th>Inspector</th>
                <th>Location</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr key={row.id || i} onClick={() => handleRowClick(row)}>
                  <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.inspection_number || "—"}</span></td>
                  <td>{row.title || "—"}</td>
                  <td>{row.inspection_type ? <span className="rex-badge rex-badge-gray">{row.inspection_type.replace(/_/g, " ")}</span> : "—"}</td>
                  <td><Badge status={row.status} /></td>
                  <td>{fmtDate(row.scheduled_date)}</td>
                  <td>{fmtDate(row.completed_date)}</td>
                  <td>{row.inspector_name || "—"}</td>
                  <td>{row.location || "—"}</td>
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
              <div className="rex-h3">Inspection #{selected.inspection_number} — {selected.title}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Badge status={selected.status} />
                {selected.inspection_type && <span className="rex-badge rex-badge-gray">{selected.inspection_type.replace(/_/g, " ")}</span>}
              </div>
            </div>
            <button className="rex-detail-panel-close" onClick={() => { setSelected(null); setInspSummary(null); setInspItems(null); }}>×</button>
          </div>
          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Inspection Info">
              <Row label="Number" value={selected.inspection_number || "—"} />
              <Row label="Title" value={selected.title || "—"} />
              <Row label="Type" value={selected.inspection_type?.replace(/_/g, " ") || "—"} />
              <Row label="Status" value={<Badge status={selected.status} />} />
              <Row label="Scheduled" value={fmtDate(selected.scheduled_date)} />
              <Row label="Completed" value={fmtDate(selected.completed_date)} />
              <Row label="Inspector" value={selected.inspector_name || "—"} />
              <Row label="Location" value={selected.location || "—"} />
            </Card>
            <Card title="Results Summary">
              {inspSummary ? (
                <>
                  <Row label="Pass" value={inspSummary.items_by_result?.pass ?? "—"} />
                  <Row label="Fail" value={inspSummary.items_by_result?.fail ?? "—"} />
                  <Row label="N/A" value={inspSummary.items_by_result?.n_a ?? "—"} />
                  <Row label="Not Inspected" value={inspSummary.items_by_result?.not_inspected ?? "—"} />
                  <Row label="Unresolved Failures" value={
                    inspSummary.has_unresolved_failures
                      ? <span className="rex-badge rex-badge-red">YES</span>
                      : <span className="rex-badge rex-badge-green">NO</span>
                  } />
                </>
              ) : (
                <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>Loading…</p>
              )}
            </Card>
            <Card title="Linked Punch Items">
              {inspSummary ? (
                inspSummary.linked_punch_item_ids?.length > 0 ? (
                  <ul style={{ margin: 0, paddingLeft: 16, fontSize: 12, color: "var(--rex-text-muted)" }}>
                    {inspSummary.linked_punch_item_ids.map((id) => (
                      <li key={id}><span style={{ fontFamily: "monospace" }}>{id}</span></li>
                    ))}
                  </ul>
                ) : (
                  <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>None linked.</p>
                )
              ) : (
                <p className="rex-muted" style={{ margin: 0, fontSize: 12 }}>Loading…</p>
              )}
            </Card>
          </div>
          {selected.comments && (
            <Card title="Comments" style={{ marginBottom: 12 }}>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.comments}</p>
            </Card>
          )}
          {itemsList.length > 0 && (
            <Card title="Inspection Items">
              <div className="rex-table-wrap" style={{ marginTop: 8 }}>
                <table className="rex-table">
                  <thead>
                    <tr>
                      <th>Item #</th>
                      <th>Description</th>
                      <th>Result</th>
                      <th>Comments</th>
                    </tr>
                  </thead>
                  <tbody>
                    {itemsList.map((item, i) => (
                      <tr key={item.id || i}>
                        <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{item.item_number || i + 1}</span></td>
                        <td>{item.description || "—"}</td>
                        <td>{resultBadge(item.result)}</td>
                        <td>{item.comments || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
