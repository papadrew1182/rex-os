// Subtle build-identity chip shown at the bottom of the sidebar.
//
// Shows the frontend commit that Vite baked in at build time (via
// version.js / vite.config.js define) plus the backend commit/version/env
// returned by /api/version. Clicking the chip toggles a compact popup with
// full details, including copy buttons and build timestamps. This is the
// ops/support escape hatch that lets anyone confirm which deployed build is
// actually serving traffic without running console commands.
//
// Gracefully degrades if /api/version is unreachable — in that case only
// frontend identity is shown and we annotate the backend line as "offline".

import { useState, useEffect, useRef } from "react";
import { api } from "./api";
import { GIT_SHA, BUILD_TIME } from "./version";

function shortSha(s) {
  if (!s || s === "dev") return s || "dev";
  return s.length > 7 ? s.slice(0, 7) : s;
}

function fmtTime(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function BuildVersionChip() {
  const [open, setOpen] = useState(false);
  const [backend, setBackend] = useState(null);
  const [backendErr, setBackendErr] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    let cancelled = false;
    api("/version")
      .then((d) => { if (!cancelled) setBackend(d); })
      .catch(() => { if (!cancelled) setBackendErr(true); });
    return () => { cancelled = true; };
  }, []);

  // Click-outside / ESC to close.
  useEffect(() => {
    if (!open) return;
    const onDown = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const feSha = shortSha(GIT_SHA);
  const beSha = backend ? shortSha(backend.commit) : backendErr ? "offline" : "…";
  const env = backend?.environment;

  return (
    <div ref={ref} style={{ position: "relative", marginTop: 8 }}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Show build identity"
        title="Click for full build info"
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 6,
          fontSize: 10,
          fontFamily: "'DM Mono', ui-monospace, monospace",
          color: "var(--rex-sidebar-muted)",
          background: "transparent",
          border: "1px solid rgba(255,255,255,0.12)",
          borderRadius: 4,
          padding: "4px 8px",
          cursor: "pointer",
          letterSpacing: "0.02em",
          textAlign: "left",
        }}
      >
        <span>fe&nbsp;{feSha}</span>
        <span>·</span>
        <span>be&nbsp;{beSha}</span>
        {env && env !== "production" && (
          <span
            style={{
              marginLeft: 4,
              padding: "0 4px",
              borderRadius: 3,
              background: "var(--rex-amber)",
              color: "#fff",
              fontWeight: 700,
              fontSize: 9,
              textTransform: "uppercase",
            }}
          >
            {env}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Build identity"
          style={{
            position: "absolute",
            bottom: "calc(100% + 6px)",
            left: 0,
            right: 0,
            background: "var(--rex-bg-card)",
            color: "var(--rex-text)",
            border: "1px solid var(--rex-border)",
            borderRadius: 6,
            boxShadow: "var(--rex-shadow-md)",
            padding: 12,
            fontSize: 11,
            lineHeight: 1.5,
            zIndex: 50,
          }}
        >
          <div style={{ fontWeight: 700, color: "var(--rex-text-bold)", marginBottom: 6 }}>Build Identity</div>

          <div style={{ marginBottom: 8 }}>
            <div style={{ color: "var(--rex-text-muted)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.05em" }}>Frontend</div>
            <div style={{ fontFamily: "ui-monospace, monospace" }}>
              commit <strong>{shortSha(GIT_SHA)}</strong>
            </div>
            {BUILD_TIME && <div style={{ color: "var(--rex-text-faint)", fontSize: 10 }}>built {fmtTime(BUILD_TIME)}</div>}
          </div>

          <div>
            <div style={{ color: "var(--rex-text-muted)", fontSize: 10, textTransform: "uppercase", letterSpacing: "0.05em" }}>Backend</div>
            {backend ? (
              <>
                <div style={{ fontFamily: "ui-monospace, monospace" }}>
                  {backend.service} <strong>v{backend.version}</strong>
                </div>
                <div style={{ fontFamily: "ui-monospace, monospace" }}>
                  commit <strong>{shortSha(backend.commit)}</strong>
                </div>
                {backend.build_time && <div style={{ color: "var(--rex-text-faint)", fontSize: 10 }}>built {fmtTime(backend.build_time)}</div>}
                {backend.environment && (
                  <div style={{ color: "var(--rex-text-faint)", fontSize: 10 }}>env {backend.environment}</div>
                )}
              </>
            ) : backendErr ? (
              <div style={{ color: "var(--rex-red)", fontSize: 10 }}>unable to reach /api/version</div>
            ) : (
              <div style={{ color: "var(--rex-text-faint)", fontSize: 10 }}>loading…</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
