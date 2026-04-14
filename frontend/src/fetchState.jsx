// Shared empty/error/loading states for data-heavy pages.
//
// Rex already has <PageLoader> and <Flash>, but error cases were mostly
// surfaced as a single red banner that couldn't distinguish:
//   • "you're logged out" — recoverable via login, user fault
//   • "network failed / backend down" — recoverable via retry, ops fault
//   • "legit empty dataset" — not an error at all
//   • "render crash" — caught by ErrorBoundary, not here
//
// This module gives pages one primitive — <LoadState /> — that renders the
// right panel for each case, with a retry button where it makes sense. It is
// additive: nothing breaks if a page keeps using the old patterns.

import { PageLoader } from "./ui";

export function classifyError(err) {
  if (!err) return null;
  const msg = typeof err === "string" ? err : err?.message || "";
  if (/unauthori[sz]ed|401|not authenticated/i.test(msg)) return "auth";
  if (/failed to fetch|network|typeerror.*fetch|cors|err_connection/i.test(msg)) return "network";
  return "server";
}

export function LoadState({ loading, error, empty, emptyMessage, loadingText, onRetry, children }) {
  if (loading) return <PageLoader text={loadingText || "Loading..."} />;

  if (error) {
    const kind = classifyError(error);
    const title =
      kind === "auth"
        ? "Your session expired"
        : kind === "network"
          ? "Can't reach the server"
          : "Something went wrong loading this page";
    const body =
      kind === "auth"
        ? "Please sign in again to continue."
        : kind === "network"
          ? "Check your connection, then retry. If the issue persists the backend may be degraded."
          : typeof error === "string"
            ? error
            : error?.message || "Unexpected error";

    return (
      <div
        role="alert"
        style={{
          padding: "1.5rem 1.75rem",
          maxWidth: 620,
          margin: "1.5rem 0",
          background: "var(--rex-bg-card)",
          border: "1px solid var(--rex-border)",
          borderLeft: `3px solid var(--rex-${kind === "network" ? "amber" : "red"})`,
          borderRadius: 8,
          boxShadow: "var(--rex-shadow-sm)",
        }}
      >
        <div
          style={{
            fontFamily: "'Syne', sans-serif",
            fontSize: 17,
            fontWeight: 800,
            color: "var(--rex-text-bold)",
            marginBottom: 6,
          }}
        >
          {title}
        </div>
        <p style={{ color: "var(--rex-text-muted)", fontSize: 13, margin: "0 0 12px", lineHeight: 1.5 }}>{body}</p>
        <div style={{ display: "flex", gap: 8 }}>
          {kind === "auth" ? (
            <button type="button" className="rex-btn rex-btn-primary" onClick={() => { window.location.hash = "#/login"; }}>
              Sign in
            </button>
          ) : onRetry ? (
            <button type="button" className="rex-btn rex-btn-primary" onClick={onRetry}>
              Retry
            </button>
          ) : null}
        </div>
      </div>
    );
  }

  if (empty) {
    return (
      <div className="rex-empty" role="status">
        <div className="rex-empty-icon">▦</div>
        {emptyMessage || "No records yet."}
      </div>
    );
  }

  return children;
}
