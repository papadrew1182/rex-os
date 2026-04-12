/**
 * Reusable file preview drawer.
 *
 * Supported preview modes:
 *   - PDF: inline via <iframe> using a blob: URL fetched through the auth-gated
 *     /api/attachments/{id}/download endpoint
 *   - Image (image/*): inline <img> using the same blob URL
 *   - Other: metadata + download/open-in-new-tab buttons
 *
 * Auth model: never bypasses auth. The download endpoint already enforces
 * project-scoped access; we just fetch through it with the user's bearer token
 * and turn the response into a blob URL for the browser to render.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { getToken, apiUrl } from "./api";
import { Spinner, Flash, Card, Row } from "./ui";

const fmtDate = (d) => d ? new Date(d).toLocaleString() : "—";
const fmtSize = (n) => {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
};

function isPdf(ct) { return (ct || "").toLowerCase().includes("pdf"); }
function isImage(ct) { return (ct || "").toLowerCase().startsWith("image/"); }

/**
 * FilePreviewDrawer
 *
 * Props:
 *   - open: boolean
 *   - onClose: () => void
 *   - attachment: full attachment object OR just { id, filename, content_type, file_size }
 *   - directUrl?: optional already-resolved URL (e.g. drawings.image_url) — if provided,
 *     we render directly from it without hitting /download. Used by Drawings.image_url.
 */
export function FilePreviewDrawer({ open, onClose, attachment, directUrl, title, subtitle }) {
  const [blobUrl, setBlobUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const lastIdRef = useRef(null);

  // Reset state on close
  useEffect(() => {
    if (!open) {
      setBlobUrl(null); setError(null); setLoading(false);
      return;
    }
  }, [open]);

  // Fetch the file via the auth-gated download endpoint
  useEffect(() => {
    if (!open || !attachment) return;
    if (directUrl) {
      // Use the direct URL — useful for drawings.image_url where storage_key isn't an attachment
      setBlobUrl(directUrl);
      return;
    }
    if (!attachment.id) return;

    // Avoid re-fetching the same attachment when the parent re-renders
    if (lastIdRef.current === attachment.id && blobUrl) return;
    lastIdRef.current = attachment.id;

    let cancelled = false;
    setLoading(true);
    setError(null);
    setBlobUrl(null);

    const token = getToken();
    fetch(apiUrl(`/attachments/${attachment.id}/download`), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(`Download failed: ${res.status} ${res.statusText}`);
        }
        return res.blob();
      })
      .then((blob) => {
        if (cancelled) return;
        const url = URL.createObjectURL(blob);
        setBlobUrl(url);
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e.message || "Failed to load file");
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });

    return () => { cancelled = true; };
  }, [open, attachment, directUrl]); // eslint-disable-line react-hooks/exhaustive-deps

  // Cleanup the blob URL when the drawer closes or the attachment changes
  useEffect(() => {
    return () => {
      if (blobUrl && blobUrl.startsWith("blob:")) {
        URL.revokeObjectURL(blobUrl);
      }
    };
  }, [blobUrl]);

  // ESC to close
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const handleDownload = useCallback(() => {
    if (!attachment) return;
    if (directUrl) {
      window.open(directUrl, "_blank", "noopener,noreferrer");
      return;
    }
    const token = getToken();
    fetch(apiUrl(`/attachments/${attachment.id}/download`), {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => r.blob())
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = attachment.filename || "download";
        a.click();
        URL.revokeObjectURL(url);
      })
      .catch((e) => setError(e.message));
  }, [attachment, directUrl]);

  const handleOpenNewTab = useCallback(() => {
    if (directUrl) {
      window.open(directUrl, "_blank", "noopener,noreferrer");
      return;
    }
    if (blobUrl) {
      window.open(blobUrl, "_blank", "noopener,noreferrer");
    }
  }, [directUrl, blobUrl]);

  if (!open) return null;

  const ct = attachment?.content_type || (directUrl ? "image/" : "");
  const isPdfFile = isPdf(ct) || (attachment?.filename || "").toLowerCase().endsWith(".pdf");
  const isImageFile = isImage(ct) || /\.(png|jpe?g|gif|webp|svg|bmp)$/i.test(attachment?.filename || directUrl || "");
  const previewable = isPdfFile || isImageFile;

  return (
    <div className="rex-drawer-overlay" onClick={onClose}>
      <div
        className="rex-drawer"
        onClick={(e) => e.stopPropagation()}
        style={{ width: 720, display: "flex", flexDirection: "column" }}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12, paddingBottom: 12, borderBottom: "1px solid var(--rex-border)" }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div className="rex-h3" style={{ wordBreak: "break-all" }}>{title || attachment?.filename || "File"}</div>
            {subtitle && <div className="rex-muted" style={{ fontSize: 12, marginTop: 2 }}>{subtitle}</div>}
            {attachment && (
              <div className="rex-muted" style={{ fontSize: 11, marginTop: 4 }}>
                {ct || "—"} · {fmtSize(attachment.file_size)}
                {attachment.created_at && ` · uploaded ${fmtDate(attachment.created_at)}`}
              </div>
            )}
          </div>
          <button className="rex-detail-panel-close" onClick={onClose}>×</button>
        </div>

        {/* Action bar */}
        <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <button className="rex-btn rex-btn-outline" onClick={handleDownload}>Download</button>
          {(blobUrl || directUrl) && (
            <button className="rex-btn rex-btn-outline" onClick={handleOpenNewTab}>Open in new tab</button>
          )}
        </div>

        {/* Preview area */}
        <div style={{ flex: 1, minHeight: 400, background: "var(--rex-bg-stripe)", border: "1px solid var(--rex-border)", borderRadius: 6, overflow: "auto", display: "flex", alignItems: "center", justifyContent: "center", padding: previewable ? 0 : 24 }}>
          {loading && (
            <div style={{ textAlign: "center" }}>
              <Spinner size={24} />
              <p className="rex-muted" style={{ marginTop: 12 }}>Loading file...</p>
            </div>
          )}
          {error && !loading && (
            <Flash type="error" message={error} />
          )}
          {!loading && !error && !blobUrl && !directUrl && (
            <div className="rex-empty">
              <div className="rex-empty-icon">○</div>
              No preview available
            </div>
          )}
          {!loading && !error && (blobUrl || directUrl) && isPdfFile && (
            <iframe
              src={blobUrl || directUrl}
              title={attachment?.filename || "PDF preview"}
              style={{ width: "100%", height: "100%", minHeight: 480, border: "none" }}
            />
          )}
          {!loading && !error && (blobUrl || directUrl) && isImageFile && (
            <img
              src={blobUrl || directUrl}
              alt={attachment?.filename || "Image preview"}
              style={{ maxWidth: "100%", maxHeight: "70vh", objectFit: "contain" }}
            />
          )}
          {!loading && !error && (blobUrl || directUrl) && !previewable && (
            <div className="rex-empty">
              <div className="rex-empty-icon">○</div>
              <div>This file type cannot be previewed inline.</div>
              <div style={{ marginTop: 12 }}>
                <button className="rex-btn rex-btn-primary" onClick={handleDownload}>Download to view</button>
              </div>
            </div>
          )}
        </div>

        {/* Metadata footer for attachments */}
        {attachment && !directUrl && (
          <Card title="File details" style={{ marginTop: 12 }}>
            <Row label="Filename" value={attachment.filename || "—"} />
            <Row label="Content type" value={attachment.content_type || "—"} />
            <Row label="Size" value={fmtSize(attachment.file_size)} />
            {attachment.source_type && <Row label="Source type" value={attachment.source_type} />}
            {attachment.created_at && <Row label="Uploaded" value={fmtDate(attachment.created_at)} />}
          </Card>
        )}
      </div>
    </div>
  );
}
