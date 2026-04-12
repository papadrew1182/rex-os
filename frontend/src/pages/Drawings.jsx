import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

export default function Drawings() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [drawingAreas, setDrawingAreas] = useState({});
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [disciplineFilter, setDisciplineFilter] = useState("");
  const [areaFilter, setAreaFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [revisions, setRevisions] = useState(null);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null); setRevisions(null);
    Promise.all([
      api(`/drawings?project_id=${selectedId}&limit=500`),
      api(`/drawing-areas?project_id=${selectedId}&limit=100`),
    ])
      .then(([drawings, areas]) => {
        setData(drawings);
        const areaList = Array.isArray(areas) ? areas : (areas?.items || []);
        const areaMap = {};
        areaList.forEach((a) => { areaMap[a.id] = a.name || a.area_name || a.id; });
        setDrawingAreas(areaMap);
      })
      .catch((e) => setError(e.message));
  }, [selectedId]);

  function handleRowClick(row) {
    if (selected?.id === row.id) { setSelected(null); setRevisions(null); return; }
    setSelected(row);
    setRevisions(null);
    api(`/drawing-revisions?drawing_id=${row.id}&limit=50`).then(setRevisions).catch(() => setRevisions([]));
  }

  const items = useMemo(() => Array.isArray(data) ? data : (data?.items || data?.drawings || []), [data]);

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return items.filter((r) => {
      const matchSearch = !q
        || (r.drawing_number || "").toLowerCase().includes(q)
        || (r.title || "").toLowerCase().includes(q);
      const matchDisc = !disciplineFilter || r.discipline === disciplineFilter;
      const matchArea = !areaFilter || r.drawing_area_id === areaFilter;
      return matchSearch && matchDisc && matchArea;
    });
  }, [items, search, disciplineFilter, areaFilter]);

  const disciplines = useMemo(() => [...new Set(items.map((r) => r.discipline).filter(Boolean))].sort(), [items]);
  const areas = useMemo(() => [...new Set(items.map((r) => r.drawing_area_id).filter(Boolean))], [items]);

  const summary = useMemo(() => {
    const current = items.filter((r) => r.is_current === true).length;
    const totalRevs = items.reduce((s, r) => s + (r.current_revision || 0), 0);
    const uniqueDisciplines = new Set(items.map((r) => r.discipline).filter(Boolean)).size;
    return { total: items.length, current, totalRevs, uniqueDisciplines };
  }, [items]);

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading drawings..." />;

  const revList = Array.isArray(revisions) ? revisions : (revisions?.items || []);
  const sortedRevs = [...revList].sort((a, b) => (b.revision_number || 0) - (a.revision_number || 0));

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Drawings</h1>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-4" style={{ marginBottom: 24 }}>
        <StatCard label="Total Drawings" value={summary.total} />
        <StatCard label="Current Sheets" value={summary.current} color="green" />
        <StatCard label="Total Revisions" value={summary.totalRevs} />
        <StatCard label="Disciplines" value={summary.uniqueDisciplines} />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search number or title..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 260 }}
        />
        <select className="rex-input" value={disciplineFilter} onChange={(e) => setDisciplineFilter(e.target.value)} style={{ width: 150 }}>
          <option value="">All Disciplines</option>
          {disciplines.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <select className="rex-input" value={areaFilter} onChange={(e) => setAreaFilter(e.target.value)} style={{ width: 160 }}>
          <option value="">All Areas</option>
          {areas.map((id) => <option key={id} value={id}>{drawingAreas[id] || id}</option>)}
        </select>
        <span className="rex-muted">{filtered.length} record{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">○</div>No drawings found.</div>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead>
              <tr>
                <th>Drawing #</th>
                <th>Title</th>
                <th>Discipline</th>
                <th>Rev</th>
                <th>Area</th>
                <th>Rev Date</th>
                <th>Status</th>
                <th>Image</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, i) => (
                <tr key={row.id || i} onClick={() => handleRowClick(row)}>
                  <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>{row.drawing_number || "—"}</span></td>
                  <td>{row.title || "—"}</td>
                  <td>{row.discipline ? <span className="rex-badge rex-badge-gray">{row.discipline.toUpperCase()}</span> : "—"}</td>
                  <td>{row.current_revision != null ? `Rev ${row.current_revision}` : "—"}</td>
                  <td>{drawingAreas[row.drawing_area_id] || "—"}</td>
                  <td>{fmtDate(row.current_revision_date)}</td>
                  <td>
                    {row.is_current
                      ? <span className="rex-badge rex-badge-green">CURRENT</span>
                      : <span className="rex-badge rex-badge-gray">OBSOLETE</span>}
                  </td>
                  <td>
                    {row.image_url
                      ? <a href={row.image_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()} style={{ fontSize: 12, color: "var(--rex-accent)" }}>View</a>
                      : "—"}
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
              <div className="rex-h3">{selected.drawing_number} — {selected.title}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                {selected.is_current
                  ? <span className="rex-badge rex-badge-green">CURRENT</span>
                  : <span className="rex-badge rex-badge-gray">OBSOLETE</span>}
                {selected.discipline && <span className="rex-badge rex-badge-gray">{selected.discipline.toUpperCase()}</span>}
              </div>
            </div>
            <button className="rex-detail-panel-close" onClick={() => { setSelected(null); setRevisions(null); }}>×</button>
          </div>
          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Drawing Info">
              <Row label="Number" value={selected.drawing_number || "—"} />
              <Row label="Title" value={selected.title || "—"} />
              <Row label="Discipline" value={selected.discipline?.toUpperCase() || "—"} />
              <Row label="Current Rev" value={selected.current_revision != null ? `Rev ${selected.current_revision}` : "—"} />
              <Row label="Is Current" value={selected.is_current ? "Yes" : "No"} />
            </Card>
            <Card title="Area">
              <Row label="Drawing Area" value={drawingAreas[selected.drawing_area_id] || "—"} />
              <Row label="Area ID" value={selected.drawing_area_id || "—"} />
            </Card>
            <Card title="Current Revision">
              <Row label="Revision" value={selected.current_revision != null ? `Rev ${selected.current_revision}` : "—"} />
              <Row label="Rev Date" value={fmtDate(selected.current_revision_date)} />
              <Row label="Image" value={selected.image_url
                ? <a href={selected.image_url} target="_blank" rel="noreferrer" style={{ color: "var(--rex-accent)", fontSize: 12 }}>View</a>
                : "—"} />
            </Card>
          </div>
          {revisions === null ? (
            <p className="rex-muted" style={{ fontSize: 12 }}>Loading revisions…</p>
          ) : sortedRevs.length > 0 ? (
            <Card title="Revision History">
              <div className="rex-table-wrap" style={{ marginTop: 8 }}>
                <table className="rex-table">
                  <thead>
                    <tr>
                      <th>Rev #</th>
                      <th>Date</th>
                      <th>Description</th>
                      <th>Image</th>
                      <th>Uploaded By</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedRevs.map((rev, i) => (
                      <tr key={rev.id || i}>
                        <td><span style={{ fontFamily: "monospace", fontSize: 12 }}>Rev {rev.revision_number}</span></td>
                        <td>{fmtDate(rev.revision_date || rev.date)}</td>
                        <td>{rev.description || "—"}</td>
                        <td>
                          {rev.image_url
                            ? <a href={rev.image_url} target="_blank" rel="noreferrer" style={{ fontSize: 12, color: "var(--rex-accent)" }}>View</a>
                            : "—"}
                        </td>
                        <td>{rev.uploaded_by || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          ) : null}
        </div>
      )}
    </div>
  );
}
