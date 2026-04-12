import { useState, useEffect, useMemo, useCallback } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";
import {
  FormDrawer, useFormState, Field, NumberField, DateField, TextArea, Select, Checkbox,
  WriteButton, cleanPayload,
} from "../forms";
import { usePermissions } from "../permissions";
import { FilePreviewDrawer } from "../preview";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

const DRAWING_DEFAULT = {
  drawing_number: "",
  title: "",
  discipline: null,
  drawing_area_id: null,
  current_revision: 0,
  current_revision_date: null,
  is_current: true,
  image_url: "",
};

const REV_DEFAULT = {
  drawing_id: null,
  revision_number: null,
  revision_date: null,
  description: "",
  image_url: "",
};

const DISCIPLINES = [
  { value: "architectural", label: "Architectural" },
  { value: "structural", label: "Structural" },
  { value: "mechanical", label: "Mechanical" },
  { value: "electrical", label: "Electrical" },
  { value: "plumbing", label: "Plumbing" },
  { value: "civil", label: "Civil" },
];

export default function Drawings() {
  const { selected: project, selectedId } = useProject();
  const { canWrite } = usePermissions();

  const [data, setData] = useState(null);
  const [drawingAreas, setDrawingAreas] = useState({});
  const [areaList, setAreaList] = useState([]);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [disciplineFilter, setDisciplineFilter] = useState("");
  const [areaFilter, setAreaFilter] = useState("");
  const [selected, setSelected] = useState(null);
  const [revisions, setRevisions] = useState(null);

  // Drawing form drawer
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerMode, setDrawerMode] = useState("create");
  const [editing, setEditing] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const form = useFormState(DRAWING_DEFAULT);

  // Revision form drawer
  const [revDrawerOpen, setRevDrawerOpen] = useState(false);
  const [revSubmitting, setRevSubmitting] = useState(false);
  const [revSubmitError, setRevSubmitError] = useState(null);
  const revForm = useFormState(REV_DEFAULT);

  // Preview drawer
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewAttachment, setPreviewAttachment] = useState(null);
  const [previewDirectUrl, setPreviewDirectUrl] = useState(null);

  function openDrawingPreview(drawing) {
    setPreviewAttachment({
      id: drawing.id,
      filename: drawing.title || drawing.drawing_number,
      content_type: "image/*",
    });
    setPreviewDirectUrl(drawing.image_url);
    setPreviewOpen(true);
  }

  const refresh = useCallback(() => {
    if (!selectedId) return;
    Promise.all([
      api(`/drawings?project_id=${selectedId}&limit=500`),
      api(`/drawing-areas?project_id=${selectedId}&limit=100`),
    ])
      .then(([drawings, areas]) => {
        setData(drawings);
        const al = Array.isArray(areas) ? areas : (areas?.items || []);
        setAreaList(al);
        const areaMap = {};
        al.forEach((a) => { areaMap[a.id] = a.name || a.area_name || a.id; });
        setDrawingAreas(areaMap);
      })
      .catch((e) => setError(e.message));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null); setRevisions(null);
    refresh();
  }, [selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  function handleRowClick(row) {
    if (selected?.id === row.id) { setSelected(null); setRevisions(null); return; }
    setSelected(row);
    setRevisions(null);
    api(`/drawing-revisions?drawing_id=${row.id}&limit=50`).then(setRevisions).catch(() => setRevisions([]));
  }

  function openCreate() {
    setDrawerMode("create");
    setEditing(null);
    form.setAll({ ...DRAWING_DEFAULT });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  function openEdit(row) {
    setDrawerMode("edit");
    setEditing(row);
    form.setAll({ ...row });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  async function onSubmit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const payload = cleanPayload(form.values);
      if (drawerMode === "create") {
        await api("/drawings/", { method: "POST", body: { ...payload, project_id: selectedId } });
      } else {
        const { project_id, ...updateOnly } = payload;
        await api(`/drawings/${editing.id}`, { method: "PATCH", body: updateOnly });
      }
      setDrawerOpen(false);
      if (drawerMode === "edit" && selected?.id === editing?.id) {
        setSelected(null); setRevisions(null);
      }
      refresh();
    } catch (e) {
      setSubmitError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  function openAddRevision(drawing) {
    revForm.setAll({ drawing_id: drawing.id, revision_number: null, revision_date: null });
    setRevSubmitError(null);
    setRevDrawerOpen(true);
  }

  async function onRevSubmit() {
    setRevSubmitting(true);
    setRevSubmitError(null);
    try {
      const payload = cleanPayload(revForm.values);
      await api("/drawing-revisions/", { method: "POST", body: payload });
      setRevDrawerOpen(false);
      if (selected) {
        setRevisions(null);
        api(`/drawing-revisions?drawing_id=${selected.id}&limit=50`).then(setRevisions).catch(() => setRevisions([]));
      }
    } catch (e) {
      setRevSubmitError(e.message);
    } finally {
      setRevSubmitting(false);
    }
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

  const areaOptions = useMemo(() => areaList.map((a) => ({ value: a.id, label: a.name || a.area_name || a.id })), [areaList]);

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading drawings..." />;

  const revList = Array.isArray(revisions) ? revisions : (revisions?.items || []);
  const sortedRevs = [...revList].sort((a, b) => (b.revision_number || 0) - (a.revision_number || 0));

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <h1 className="rex-h1">Drawings</h1>
        <WriteButton onClick={openCreate}>+ New Drawing</WriteButton>
      </div>
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
                      ? <button className="rex-btn rex-btn-outline" onClick={(e) => { e.stopPropagation(); openDrawingPreview(row); }} style={{ padding: "2px 8px", fontSize: 12 }}>Preview</button>
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
            <div style={{ display: "flex", gap: 8 }}>
              {canWrite && (
                <button className="rex-btn rex-btn-outline" style={{ marginRight: 8 }} onClick={() => openEdit(selected)}>
                  Edit
                </button>
              )}
              <button className="rex-detail-panel-close" onClick={() => { setSelected(null); setRevisions(null); }}>×</button>
            </div>
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
                ? <button className="rex-btn rex-btn-outline" onClick={() => openDrawingPreview(selected)} style={{ padding: "2px 8px", fontSize: 12 }}>Preview Drawing</button>
                : "—"} />
            </Card>
          </div>
          {revisions === null ? (
            <p className="rex-muted" style={{ fontSize: 12 }}>Loading revisions…</p>
          ) : (
            <Card title="Revision History">
              <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
                <WriteButton onClick={() => openAddRevision(selected)} variant="outline">+ Add Revision</WriteButton>
              </div>
              {sortedRevs.length > 0 ? (
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
              ) : (
                <p className="rex-muted" style={{ fontSize: 12, margin: 0 }}>No revisions yet.</p>
              )}
            </Card>
          )}
        </div>
      )}

      {/* Drawing create/edit drawer */}
      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title={drawerMode === "create" ? "New Drawing" : "Edit Drawing"}
        subtitle={drawerMode === "edit" ? editing?.drawing_number : undefined}
        mode={drawerMode}
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
      >
        <Field label="Drawing Number" name="drawing_number" value={form.values.drawing_number} onChange={form.setField} required autoFocus />
        <Field label="Title" name="title" value={form.values.title} onChange={form.setField} required />
        <Select
          label="Discipline"
          name="discipline"
          value={form.values.discipline}
          onChange={form.setField}
          options={DISCIPLINES}
          required
        />
        <Select
          label="Drawing Area"
          name="drawing_area_id"
          value={form.values.drawing_area_id}
          onChange={form.setField}
          options={areaOptions}
          required
          placeholder="Select area…"
        />
        <NumberField label="Current Revision" name="current_revision" value={form.values.current_revision} onChange={form.setField} step={1} />
        <DateField label="Current Revision Date" name="current_revision_date" value={form.values.current_revision_date} onChange={form.setField} />
        <Checkbox label="Is Current" name="is_current" value={form.values.is_current} onChange={form.setField} />
        <Field label="Image URL" name="image_url" value={form.values.image_url} onChange={form.setField} placeholder="https://..." />
      </FormDrawer>

      {/* Drawing revision add drawer */}
      <FormDrawer
        open={revDrawerOpen}
        onClose={() => setRevDrawerOpen(false)}
        title="Add Revision"
        subtitle={selected ? `${selected.drawing_number} — ${selected.title}` : undefined}
        mode="create"
        onSubmit={onRevSubmit}
        onReset={revForm.reset}
        dirty={revForm.dirty}
        submitting={revSubmitting}
        error={revSubmitError}
      >
        <NumberField label="Revision Number" name="revision_number" value={revForm.values.revision_number} onChange={revForm.setField} required step={1} />
        <DateField label="Revision Date" name="revision_date" value={revForm.values.revision_date} onChange={revForm.setField} required />
        <TextArea label="Description" name="description" value={revForm.values.description} onChange={revForm.setField} />
        <Field label="Image URL" name="image_url" value={revForm.values.image_url} onChange={revForm.setField} required placeholder="https://..." />
      </FormDrawer>

      <FilePreviewDrawer
        open={previewOpen}
        onClose={() => { setPreviewOpen(false); setPreviewDirectUrl(null); }}
        attachment={previewAttachment}
        directUrl={previewDirectUrl}
        title={previewAttachment?.filename}
        subtitle="Drawing"
      />
    </div>
  );
}
