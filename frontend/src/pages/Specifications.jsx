import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

export default function Specifications() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [divisionFilter, setDivisionFilter] = useState("");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null);
    api(`/specifications?project_id=${selectedId}&limit=500`)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [selectedId]);

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.specifications || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q
        || (r.section_number || "").toLowerCase().includes(q)
        || (r.title || "").toLowerCase().includes(q);
      const matchDiv = !divisionFilter || r.division === divisionFilter;
      return matchSearch && matchDiv;
    });
  }, [items, search, divisionFilter]);

  const divisions = useMemo(() => [...new Set(items.map((r) => r.division).filter(Boolean))].sort(), [items]);

  const summary = useMemo(() => {
    const uniqueDivisions = new Set(items.map((r) => r.division).filter(Boolean)).size;
    const revised = items.filter((r) => (r.current_revision || 0) > 0).length;
    const withAttachments = items.filter((r) => r.attachment_id != null).length;
    return { total: items.length, uniqueDivisions, revised, withAttachments };
  }, [items]);

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading specifications..." />;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Specifications</h1>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-4" style={{ marginBottom: 24 }}>
        <StatCard label="Total Sections" value={summary.total} />
        <StatCard label="Divisions" value={summary.uniqueDivisions} />
        <StatCard label="Revised" value={summary.revised} color={summary.revised > 0 ? "amber" : ""} />
        <StatCard label="With Attachments" value={summary.withAttachments} color={summary.withAttachments > 0 ? "green" : ""} />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search section # or title..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 260 }}
        />
        <select className="rex-input" value={divisionFilter} onChange={(e) => setDivisionFilter(e.target.value)} style={{ width: 160 }}>
          <option value="">All Divisions</option>
          {divisions.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <span className="rex-muted">{filtered.length} record{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No specifications found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Section #</th>
                <th>Title</th>
                <th>Division</th>
                <th>Rev</th>
                <th>Rev Date</th>
                <th>Attachment</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr key={row.id || i} onClick={() => setSelected(selected?.id === row.id ? null : row)}>
                  <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.section_number || "—"}</span></td>
                  <td>{row.title || "—"}</td>
                  <td>{row.division ? <span className="rex-badge rex-badge-gray">{row.division}</span> : "—"}</td>
                  <td>{row.current_revision != null ? `Rev ${row.current_revision}` : "—"}</td>
                  <td>{fmtDate(row.revision_date)}</td>
                  <td>
                    {row.attachment_id
                      ? <span className="rex-badge rex-badge-green">FILE</span>
                      : <span className="rex-badge rex-badge-gray">—</span>}
                  </td>
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
              <div className="rex-h3">{selected.section_number} — {selected.title}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                {selected.division && <span className="rex-badge rex-badge-gray">{selected.division}</span>}
                {selected.attachment_id && <span className="rex-badge rex-badge-green">FILE</span>}
              </div>
            </div>
            <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>×</button>
          </div>
          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Section Info">
              <Row label="Section #" value={<span style={{ fontFamily: "monospace", fontSize: 12 }}>{selected.section_number || "—"}</span>} />
              <Row label="Title" value={selected.title || "—"} />
              <Row label="Division" value={selected.division || "—"} />
            </Card>
            <Card title="Revision">
              <Row label="Current Rev" value={selected.current_revision != null ? `Rev ${selected.current_revision}` : "—"} />
              <Row label="Revision Date" value={fmtDate(selected.revision_date)} />
            </Card>
            <Card title="Attachment">
              <Row label="Attachment ID" value={
                selected.attachment_id
                  ? <span style={{ fontFamily: "monospace", fontSize: 11 }}>{selected.attachment_id}</span>
                  : "—"
              } />
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
