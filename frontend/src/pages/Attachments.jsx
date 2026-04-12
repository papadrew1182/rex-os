import { useState, useEffect, useCallback } from "react";
import { api, getToken, apiUrl } from "../api";
import { useProject } from "../project";
import { Badge, PageLoader, Flash, Spinner } from "../ui";
import { FilePreviewDrawer } from "../preview";

export default function Attachments() {
  const { selected: project, selectedId } = useProject();
  const [attachments, setAttachments] = useState([]);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [pageLoad, setPageLoad] = useState(true);
  const [sourceType, setSourceType] = useState("rfi");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewAttachment, setPreviewAttachment] = useState(null);
  const flash = (m) => { setSuccess(m); setTimeout(() => setSuccess(null), 3000); };

  function openPreview(attachment) { setPreviewAttachment(attachment); setPreviewOpen(true); }

  const load = useCallback(() => { if (!selectedId) return; setPageLoad(true); api(`/attachments/?project_id=${selectedId}&limit=50`).then(setAttachments).catch((e) => setError(e.message)).finally(() => setPageLoad(false)); }, [selectedId]);
  useEffect(() => { load(); }, [load]);

  const upload = async (e) => {
    e.preventDefault(); const form = e.target; if (!form.elements.file.files.length) return;
    setUploading(true); setError(null);
    try {
      const fd = new FormData(); fd.append("project_id", selectedId); fd.append("source_type", sourceType); fd.append("source_id", crypto.randomUUID()); fd.append("file", form.elements.file.files[0]);
      const r = await api("/attachments/upload", { method: "POST", body: fd }); form.reset(); setSourceType("rfi"); load(); flash(`Uploaded ${r.filename} (${fmt(r.file_size)})`);
    } catch (e) { setError(e.message); } finally { setUploading(false); }
  };

  const download = async (att) => {
    try {
      const res = await fetch(apiUrl(`/attachments/${att.id}/download`), { headers: { Authorization: `Bearer ${getToken()}` } });
      if (!res.ok) { const err = await res.json().catch(() => ({})); throw new Error(err.detail || `HTTP ${res.status}`); }
      const url = URL.createObjectURL(await res.blob()); const a = document.createElement("a"); a.href = url; a.download = att.filename; a.click(); URL.revokeObjectURL(url);
    } catch (e) { setError(e.message); }
  };

  if (!selectedId) return <p className="rex-muted">Select a project.</p>;

  return (
    <div>
      <h1 className="rex-h1" style={{ marginBottom: 4 }}>Attachments</h1>
      <p className="rex-muted" style={{ marginBottom: 16 }}>Project: <strong style={{ color: "var(--rex-text-bold)" }}>{project?.name}</strong></p>
      <Flash type="error" message={error} onDismiss={() => setError(null)} />
      <Flash message={success} />

      <div className="rex-card" style={{ marginBottom: 20 }}>
        <form onSubmit={upload} style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <span className="rex-section-label">Upload File</span>
          <select value={sourceType} onChange={(e) => setSourceType(e.target.value)} className="rex-input">
            <option value="rfi">RFI</option><option value="submittal">Submittal</option><option value="punch_item">Punch Item</option><option value="daily_log">Daily Log</option><option value="inspection">Inspection</option>
          </select>
          <input type="file" name="file" required style={{ fontSize: 13 }} />
          <button type="submit" disabled={uploading} className="rex-btn rex-btn-primary">{uploading ? <><Spinner size={14} /> Uploading...</> : "Upload"}</button>
        </form>
      </div>

      {pageLoad ? <PageLoader text="Loading attachments..." /> : attachments.length === 0 ? (
        <p className="rex-muted" style={{ textAlign: "center", padding: "2rem 0" }}>No attachments for this project.</p>
      ) : (
        <div className="rex-table-wrap">
          <table className="rex-table">
            <thead><tr><th>Filename</th><th>Type</th><th>Source</th><th>Size</th><th>Uploaded</th><th></th></tr></thead>
            <tbody>
              {attachments.map((att) => (
                <tr key={att.id}>
                  <td style={{ fontWeight: 600 }}>{att.filename}</td>
                  <td><span className="rex-muted">{att.content_type}</span></td>
                  <td><Badge status={att.source_type === "rfi" ? "purple" : "gray"} label={att.source_type?.replace(/_/g, " ")} /></td>
                  <td>{fmt(att.file_size)}</td>
                  <td>{new Date(att.created_at).toLocaleDateString()}</td>
                  <td>
                    <button className="rex-btn rex-btn-outline" onClick={(e) => { e.stopPropagation(); openPreview(att); }} style={{ padding: "4px 10px", fontSize: 12, marginRight: 4 }}>Preview</button>
                    <button onClick={() => download(att)} className="rex-btn rex-btn-outline" style={{ padding: "4px 10px", fontSize: 12 }}>Download</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <FilePreviewDrawer open={previewOpen} onClose={() => setPreviewOpen(false)} attachment={previewAttachment} />
    </div>
  );
}

function fmt(b) { if (b == null) return "---"; if (b < 1024) return b + " B"; if (b < 1048576) return (b / 1024).toFixed(1) + " KB"; return (b / 1048576).toFixed(1) + " MB"; }
