import { Component } from "react";
import { captureError } from "./sentry";

/**
 * RouteErrorBoundary — per-route crash isolator.
 *
 * Wraps every <Route element>. A render/runtime crash in one route is
 * reported to Sentry (if configured) and shown as a recoverable panel
 * instead of blanking the whole shell. Sidebar + topbar remain alive and
 * navigable. Clicking "Try again" resets local state WITHOUT a full page
 * reload, so the user keeps their project selection and auth session.
 *
 * Accepts an optional `routeKey` prop — when it changes (i.e. the user
 * navigated to a different route), the boundary resets automatically so a
 * stuck error panel does not persist across navigation.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null, errorInfo: null };
    this.handleRetry = this.handleRetry.bind(this);
    this.handleReload = this.handleReload.bind(this);
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo });
    try {
      captureError(error, {
        componentStack: errorInfo?.componentStack,
        routeKey: this.props.routeKey,
      });
    } catch {
      /* never let telemetry break the shell */
    }
    // Always log — even without Sentry, devtools should see it.
    // eslint-disable-next-line no-console
    console.error("[RouteErrorBoundary]", error, errorInfo);
  }

  componentDidUpdate(prevProps) {
    // Auto-reset when route changes. Without this, after a crash the user
    // cannot simply click a sidebar item to recover.
    if (this.state.error && prevProps.routeKey !== this.props.routeKey) {
      this.setState({ error: null, errorInfo: null });
    }
  }

  handleRetry() {
    this.setState({ error: null, errorInfo: null });
  }

  handleReload() {
    window.location.reload();
  }

  render() {
    if (!this.state.error) return this.props.children;

    const msg = this.state.error?.message || "Unexpected error";
    return (
      <div
        role="alert"
        style={{
          padding: "1.75rem 2rem",
          maxWidth: 620,
          margin: "2.5rem auto",
          background: "var(--rex-bg-card, #fff)",
          border: "1px solid var(--rex-border, #e0e0e0)",
          borderLeft: "3px solid var(--rex-red, #DC2626)",
          borderRadius: 8,
          boxShadow: "var(--rex-shadow-sm, 0 1px 3px rgba(0,0,0,0.06))",
        }}
      >
        <div
          style={{
            fontFamily: "'Syne', sans-serif",
            fontSize: 18,
            fontWeight: 800,
            color: "var(--rex-text-bold, #0F172A)",
            marginBottom: 6,
          }}
        >
          This page hit an unexpected error
        </div>
        <p
          style={{
            color: "var(--rex-text-muted, #475569)",
            fontSize: 13,
            margin: "0 0 14px",
            lineHeight: 1.5,
          }}
        >
          The rest of the app is still running. You can retry this page or
          navigate somewhere else from the sidebar.
        </p>
        <pre
          style={{
            background: "var(--rex-bg-stripe, #FBF9FE)",
            border: "1px solid var(--rex-border, #E2E0E8)",
            borderRadius: 6,
            padding: "8px 10px",
            margin: "0 0 14px",
            fontSize: 11,
            color: "var(--rex-text-muted, #475569)",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            maxHeight: 120,
            overflow: "auto",
          }}
        >
          {msg}
        </pre>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            onClick={this.handleRetry}
            className="rex-btn rex-btn-primary"
          >
            Try again
          </button>
          <button
            type="button"
            onClick={this.handleReload}
            className="rex-btn rex-btn-outline"
          >
            Reload page
          </button>
        </div>
      </div>
    );
  }
}
