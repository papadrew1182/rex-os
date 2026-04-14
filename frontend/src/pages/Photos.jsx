import { useState, useEffect, useMemo, useCallback } from "react";
import { api, apiUrl, getToken } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";
import {
  FormDrawer, useFormState, Field, NumberField, DateField, TextArea, Select,
  FileInput, WriteButton, cleanPayload,
} from "../forms";
import { usePermissions } from "../permissions";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

const PHOTO_EDIT_DEFAULT = {
  filename: "",
  photo_album_id: null,
  taken_at: null,
  location: "",
  description: "",
  latitude: null,
  longitude: null,
};

const PHOTO_UPLOAD_DEFAULT = {
  file: null,
  photo_album_id: null,
  new_album_name: "",
  taken_at: null,
  description: "",
  location: "",
  latitude: null,
  longitude: null,
  tags: "",
};

function fmtFileSize(bytes) {
  if (bytes == null) return "—";
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}

export default function Photos() {
  const { selected: project, selectedId } = useProject();
  const { canWrite } = usePermissions();

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [albumFilter, setAlbumFilter] = useState("");
  const [selected, setSelected] = useState(null);

  // Edit drawer
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const form = useFormState(PHOTO_EDIT_DEFAULT);

  // Upload drawer — multipart POST /photos/upload
  const [uploadOpen, setUploadOpen] = useState(false);
  const [uploadSubmitting, setUploadSubmitting] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const uploadForm = useFormState(PHOTO_UPLOAD_DEFAULT);

  const refresh = useCallback(() => {
    if (!selectedId) return;
    Promise.all([
      api(`/photos?project_id=${selectedId}&limit=500`),
      api(`/photo-albums?project_id=${selectedId}&limit=100`),
    ])
      .then(([photos, albums]) => {
        const albumList = Array.isArray(albums) ? albums : (albums?.items || []);
        const albumMap = {};
        albumList.forEach((a) => { albumMap[a.id] = a.name || a.id; });
        setData({ photos, albums: albumList, albumMap });
      })
      .catch((e) => setError(e.message));
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null);
    refresh();
  }, [selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  const photos = useMemo(() => {
    if (!data) return [];
    return Array.isArray(data.photos) ? data.photos : (data.photos?.items || data.photos?.photos || []);
  }, [data]);

  const albums = useMemo(() => data?.albums || [], [data]);
  const albumMap = useMemo(() => data?.albumMap || {}, [data]);

  const albumOptions = useMemo(
    () => albums.map((a) => ({ value: a.id, label: a.name || a.id })),
    [albums],
  );

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return photos.filter((p) => {
      const matchSearch = !q
        || (p.filename || "").toLowerCase().includes(q)
        || (p.description || "").toLowerCase().includes(q);
      const matchAlbum = !albumFilter || p.photo_album_id === albumFilter;
      return matchSearch && matchAlbum;
    });
  }, [photos, search, albumFilter]);

  const summary = useMemo(() => {
    const sevenDaysAgo = Date.now() - 7 * 86400000;
    const withLocation = photos.filter((p) => p.location || (p.latitude && p.longitude)).length;
    const recentUploads = photos.filter((p) => p.created_at && new Date(p.created_at).getTime() > sevenDaysAgo).length;
    const tagged = photos.filter((p) => {
      if (!p.tags) return false;
      if (Array.isArray(p.tags)) return p.tags.length > 0;
      if (typeof p.tags === "object") return Object.keys(p.tags).length > 0;
      return false;
    }).length;
    return { total: photos.length, albumCount: albums.length, withLocation, recentUploads, tagged };
  }, [photos, albums]);

  function openEditPhoto(row) {
    setEditing(row);
    form.setAll({
      filename: row.filename,
      photo_album_id: row.photo_album_id,
      taken_at: row.taken_at,
      location: row.location,
      description: row.description,
      latitude: row.latitude,
      longitude: row.longitude,
    });
    setSubmitError(null);
    setDrawerOpen(true);
  }

  async function onSubmit() {
    setSubmitting(true);
    setSubmitError(null);
    try {
      const payload = cleanPayload(form.values);
      await api(`/photos/${editing.id}`, { method: "PATCH", body: payload });
      setDrawerOpen(false);
      // Update selected if it matches
      if (selected?.id === editing.id) {
        setSelected((prev) => ({ ...prev, ...payload }));
      }
      refresh();
    } catch (e) {
      setSubmitError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  function openUpload() {
    uploadForm.setAll({ ...PHOTO_UPLOAD_DEFAULT });
    setUploadError(null);
    setUploadOpen(true);
  }

  async function onUpload() {
    setUploadSubmitting(true);
    setUploadError(null);
    try {
      const v = uploadForm.values;
      if (!v.file) throw new Error("Please choose a photo file");
      if (!(v.file instanceof File)) throw new Error("Invalid file");
      if (!v.file.type?.startsWith("image/")) throw new Error("Only image files are allowed");

      // If user typed a new album name, create it first, then attach its id.
      let albumId = v.photo_album_id || null;
      if (!albumId && v.new_album_name?.trim()) {
        const album = await api("/photo-albums/", {
          method: "POST",
          body: { project_id: selectedId, name: v.new_album_name.trim() },
        });
        albumId = album?.id;
      }

      const fd = new FormData();
      fd.append("project_id", selectedId);
      fd.append("file", v.file);
      if (albumId) fd.append("photo_album_id", albumId);
      if (v.taken_at) fd.append("taken_at", new Date(v.taken_at + "T00:00:00").toISOString());
      if (v.description) fd.append("description", v.description);
      if (v.location) fd.append("location", v.location);
      if (v.latitude != null) fd.append("latitude", String(v.latitude));
      if (v.longitude != null) fd.append("longitude", String(v.longitude));
      if (v.tags?.trim()) fd.append("tags", v.tags.trim());

      // Hand-rolled fetch so we preserve Bearer auth while letting the browser
      // set the multipart boundary header. api() would JSON-encode our body.
      const token = getToken();
      const res = await fetch(apiUrl("/photos/upload"), {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      setUploadOpen(false);
      refresh();
    } catch (e) {
      setUploadError(e.message || String(e));
    } finally {
      setUploadSubmitting(false);
    }
  }

  if (!selectedId) return <p className="rex-muted" style={{ padding: "2rem" }}>Select a project.</p>;
  if (error) return <Flash type="error" message={error} />;
  if (!data) return <PageLoader text="Loading photos..." />;

  const tagList = selected?.tags
    ? Array.isArray(selected.tags)
      ? selected.tags
      : typeof selected.tags === "object"
        ? Object.values(selected.tags)
        : []
    : [];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10, marginBottom: 4 }}>
        <h1 className="rex-h1" style={{ margin: 0 }}>Photo Gallery</h1>
        <WriteButton onClick={openUpload}>+ Upload Photo</WriteButton>
      </div>
      <p className="rex-muted" style={{ marginBottom: 20 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>

      <div className="rex-grid-5" style={{ marginBottom: 24 }}>
        <StatCard label="Total Photos" value={summary.total} />
        <StatCard label="Albums" value={summary.albumCount} />
        <StatCard label="With Location" value={summary.withLocation} />
        <StatCard label="Recent Uploads" value={summary.recentUploads} sub="last 7 days" />
        <StatCard label="Tagged" value={summary.tagged} />
      </div>

      <div className="rex-search-bar">
        <input
          className="rex-input"
          placeholder="Search filename or description..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 260 }}
        />
        <select className="rex-input" value={albumFilter} onChange={(e) => setAlbumFilter(e.target.value)} style={{ width: 180 }}>
          <option value="">All Albums</option>
          {albums.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
        <span className="rex-muted">{filtered.length} photo{filtered.length !== 1 ? "s" : ""}</span>
      </div>

      {filtered.length === 0 ? (
        <div className="rex-empty"><div className="rex-empty-icon">▦</div>No photos found.</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12 }}>
          {filtered.map((p) => (
            <div
              key={p.id}
              onClick={() => setSelected(selected?.id === p.id ? null : p)}
              style={{
                background: "var(--rex-bg-card)",
                border: selected?.id === p.id ? "2px solid var(--rex-accent)" : "1px solid var(--rex-border)",
                borderRadius: 8,
                overflow: "hidden",
                cursor: "pointer",
                boxShadow: "var(--rex-shadow-sm)",
              }}
            >
              <div style={{ aspectRatio: "4/3", background: "var(--rex-bg-stripe)", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
                {p.thumbnail_url || p.storage_url ? (
                  <img
                    src={p.thumbnail_url || p.storage_url}
                    alt={p.filename}
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    onError={(e) => { e.target.style.display = "none"; }}
                  />
                ) : (
                  <span className="rex-muted" style={{ fontSize: 28 }}>▦</span>
                )}
              </div>
              <div style={{ padding: 10 }}>
                <div style={{ fontSize: 12, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.filename}</div>
                <div className="rex-muted" style={{ fontSize: 11, marginTop: 3 }}>{albumMap[p.photo_album_id] || "—"}</div>
                <div className="rex-muted" style={{ fontSize: 11 }}>{p.taken_at ? fmtDate(p.taken_at) : fmtDate(p.created_at?.slice(0, 10))}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {selected && (
        <div className="rex-detail-panel">
          <div className="rex-detail-panel-header">
            <div>
              <div className="rex-h3">{selected.filename}</div>
              <div style={{ marginTop: 4, display: "flex", gap: 8, flexWrap: "wrap" }}>
                {selected.content_type && <span className="rex-badge rex-badge-gray">{selected.content_type}</span>}
                {albumMap[selected.photo_album_id] && (
                  <span className="rex-badge rex-badge-purple">{albumMap[selected.photo_album_id]}</span>
                )}
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {canWrite && (
                <button className="rex-btn rex-btn-outline" style={{ marginRight: 8 }} onClick={() => openEditPhoto(selected)}>
                  Edit Metadata
                </button>
              )}
              <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>×</button>
            </div>
          </div>

          {(selected.storage_url || selected.thumbnail_url) && (
            <div style={{ marginBottom: 16, textAlign: "center" }}>
              <img
                src={selected.storage_url || selected.thumbnail_url}
                alt={selected.filename}
                style={{ maxHeight: 400, maxWidth: "100%", objectFit: "contain", borderRadius: 6 }}
                onError={(e) => { e.target.style.display = "none"; }}
              />
            </div>
          )}

          <div className="rex-grid-3" style={{ marginBottom: 14 }}>
            <Card title="Photo Info">
              <Row label="Filename" value={selected.filename || "—"} />
              <Row label="Content Type" value={selected.content_type || "—"} />
              <Row label="File Size" value={fmtFileSize(selected.file_size)} />
              <Row label="Album" value={albumMap[selected.photo_album_id] || "—"} />
            </Card>
            <Card title="Location">
              <Row label="Location" value={selected.location || "—"} />
              <Row label="Latitude" value={selected.latitude != null ? selected.latitude : "—"} />
              <Row label="Longitude" value={selected.longitude != null ? selected.longitude : "—"} />
            </Card>
            <Card title="Metadata">
              <Row label="Taken At" value={selected.taken_at ? fmtDate(selected.taken_at) : "—"} />
              <Row label="Uploaded" value={selected.created_at ? new Date(selected.created_at).toLocaleDateString() : "—"} />
              <Row label="Uploaded By" value={selected.uploaded_by || "—"} />
              <Row label="Source Type" value={selected.source_type || "—"} />
              <Row label="Source ID" value={selected.source_id ? <span style={{ fontFamily: "monospace", fontSize: 11 }}>{selected.source_id.slice(0, 8)}…</span> : "—"} />
            </Card>
          </div>

          {selected.description && (
            <Card title="Description" style={{ marginBottom: 12 }}>
              <p style={{ margin: 0, fontSize: 13, color: "var(--rex-text-muted)" }}>{selected.description}</p>
            </Card>
          )}

          {tagList.length > 0 && (
            <Card title="Tags">
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {tagList.map((tag, i) => (
                  <span key={i} className="rex-badge rex-badge-gray">{String(tag)}</span>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* Upload photo drawer — multipart to /photos/upload */}
      <FormDrawer
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        title="Upload Photo"
        subtitle={project?.name}
        mode="create"
        onSubmit={onUpload}
        onReset={uploadForm.reset}
        dirty={uploadForm.dirty}
        submitting={uploadSubmitting}
        error={uploadError}
      >
        <FileInput
          label="Photo File"
          name="file"
          accept="image/*"
          file={uploadForm.values.file}
          onChange={uploadForm.setField}
          required
        />
        <Select
          label="Existing Album"
          name="photo_album_id"
          value={uploadForm.values.photo_album_id}
          onChange={uploadForm.setField}
          options={albumOptions}
          placeholder="No album / create new below"
        />
        <Field
          label="…or create new album"
          name="new_album_name"
          value={uploadForm.values.new_album_name}
          onChange={uploadForm.setField}
          placeholder="New album name"
        />
        <DateField label="Taken At" name="taken_at" value={uploadForm.values.taken_at} onChange={uploadForm.setField} />
        <Field label="Location" name="location" value={uploadForm.values.location} onChange={uploadForm.setField} placeholder="e.g. 3rd floor, North elevation" />
        <div className="rex-form-row">
          <NumberField label="Latitude" name="latitude" value={uploadForm.values.latitude} onChange={uploadForm.setField} step="0.000001" />
          <NumberField label="Longitude" name="longitude" value={uploadForm.values.longitude} onChange={uploadForm.setField} step="0.000001" />
        </div>
        <TextArea label="Description" name="description" value={uploadForm.values.description} onChange={uploadForm.setField} />
        <Field label="Tags (comma-separated)" name="tags" value={uploadForm.values.tags} onChange={uploadForm.setField} placeholder="e.g. punch, exterior, rough-in" />
      </FormDrawer>

      {/* Photo metadata edit drawer */}
      <FormDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title="Edit Photo Metadata"
        subtitle={editing?.filename}
        mode="edit"
        onSubmit={onSubmit}
        onReset={form.reset}
        dirty={form.dirty}
        submitting={submitting}
        error={submitError}
      >
        <Field label="Filename" name="filename" value={form.values.filename} onChange={form.setField} required autoFocus />
        <Select
          label="Album"
          name="photo_album_id"
          value={form.values.photo_album_id}
          onChange={form.setField}
          options={albumOptions}
          placeholder="No album"
        />
        <DateField label="Taken At" name="taken_at" value={form.values.taken_at} onChange={form.setField} />
        <Field label="Location" name="location" value={form.values.location} onChange={form.setField} />
        <TextArea label="Description" name="description" value={form.values.description} onChange={form.setField} />
        <NumberField label="Latitude" name="latitude" value={form.values.latitude} onChange={form.setField} />
        <NumberField label="Longitude" name="longitude" value={form.values.longitude} onChange={form.setField} />
      </FormDrawer>
    </div>
  );
}
