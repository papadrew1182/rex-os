/* Shared UI — Rex Procore visual language (Direction A) */

const STATUS_MAP = {
  pass: "rex-badge-green", warning: "rex-badge-amber", fail: "rex-badge-red",
  not_started: "rex-badge-gray", not_applicable: "rex-badge-gray",
  pending: "rex-badge-gray", achieved: "rex-badge-green",
  complete: "rex-badge-green", in_progress: "rex-badge-purple",
  n_a: "rex-badge-gray", active: "rex-badge-green", draft: "rex-badge-gray",
  open: "rex-badge-amber", closed: "rex-badge-green",
};

export function Spinner({ size = 16 }) {
  return <span className="rex-spinner" style={{ width: size, height: size }} />;
}

export function PageLoader({ text = "Loading..." }) {
  return (
    <div style={{ padding: "3rem", textAlign: "center" }}>
      <Spinner size={24} />
      <p className="rex-muted" style={{ marginTop: 12 }}>{text}</p>
    </div>
  );
}

export function Flash({ type = "success", message, onDismiss }) {
  if (!message) return null;
  const cls = type === "error" ? "rex-alert-red" : "rex-alert-green";
  return (
    <div className={`rex-alert ${cls}`}>
      <span style={{ flex: 1 }}>{message}</span>
      {onDismiss && <button onClick={onDismiss} style={{ background: "none", border: "none", cursor: "pointer", fontWeight: 700, fontSize: 16, color: "inherit" }}>×</button>}
    </div>
  );
}

export function Badge({ status, label }) {
  return <span className={`rex-badge ${STATUS_MAP[status] || "rex-badge-gray"}`}>{label || status?.replace(/_/g, " ") || "---"}</span>;
}

export function StatCard({ label, value, color, sub }) {
  return (
    <div className={`rex-stat-card ${color || ""}`}>
      <div className="rex-stat-label">{label}</div>
      <div className={`rex-stat-num ${color || ""}`}>{value}</div>
      {sub && <div className="rex-stat-sub">{sub}</div>}
    </div>
  );
}

export function ProgressBar({ pct, height = 6 }) {
  const p = Math.min(pct || 0, 100);
  const bg = p >= 100 ? "var(--rex-green)" : p >= 80 ? "var(--rex-amber)" : "var(--rex-accent)";
  return (
    <div className="rex-progress" style={{ height }}>
      <div className="rex-progress-fill" style={{ width: `${p}%`, background: bg }} />
    </div>
  );
}

export function Card({ title, children, action }) {
  return (
    <div className="rex-card">
      {title && <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}><h4 className="rex-h4">{title}</h4>{action}</div>}
      {children}
    </div>
  );
}

export function Row({ label, value }) {
  return <div className="rex-row"><span className="rex-row-label">{label}</span><span className="rex-row-value">{value}</span></div>;
}
