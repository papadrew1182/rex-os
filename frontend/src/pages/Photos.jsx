import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import { useProject } from "../project";
import { Badge, StatCard, Card, Row, PageLoader, Flash } from "../ui";

const fmtDate = (d) => d ? new Date(d + "T00:00:00").toLocaleDateString() : "—";

function fmtFileSize(bytes) {
  if (bytes == null) return "—";
  if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}

export default function Photos() {
  const { selected: project, selectedId } = useProject();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [albumFilter, setAlbumFilter] = useState("");
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!selectedId) return;
    setData(null); setError(null); setSelected(null);
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

  const photos = useMemo(() => {
    if (!data) return [];
    return Array.isArray(data.photos) ? data.photos : (data.photos?.items || data.photos?.photos || []);
  }, [data]);

  const albums = useMemo(() => data?.albums || [], [data]);
  const albumMap = useMemo(() => data?.albumMap || {}, [data]);

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
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Photo Gallery</h1>
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
            <button className="rex-detail-panel-close" onClick={() => setSelected(null)}>×</button>
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
    </div>
  );
}
