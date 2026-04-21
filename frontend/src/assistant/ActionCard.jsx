// frontend/src/assistant/ActionCard.jsx
// Unified Phase 6 action card. Renders all 4 states (approval,
// committed, failed, undone). Counts down 60s client-side on
// committed state and removes the Undo button when time runs out.

import { useEffect, useMemo, useState } from "react";
import "./actionCardStyles.css";

const UNDO_WINDOW_SECONDS = 60;

function formatTimestamp(iso) {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return "";
  }
}

function secondsRemaining(committedAt) {
  if (!committedAt) return 0;
  const start = new Date(committedAt).getTime();
  const elapsed = (Date.now() - start) / 1000;
  return Math.max(0, Math.floor(UNDO_WINDOW_SECONDS - elapsed));
}

export default function ActionCard({ action, onApprove, onDiscard, onUndo, onRetry, onDismiss }) {
  const [countdown, setCountdown] = useState(() =>
    action.state === "committed" ? secondsRemaining(action.committed_at) : 0,
  );

  useEffect(() => {
    if (action.state !== "committed" || !action.committed_at) return undefined;
    const tick = () => setCountdown(secondsRemaining(action.committed_at));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [action.state, action.committed_at]);

  const undoable = action.state === "committed" && countdown > 0;
  const variant = useMemo(() => {
    if (action.state === "approval") return "approval";
    if (action.state === "failed") return "failed";
    if (action.state === "undone") return "undone";
    if (action.state === "committed") return undoable ? "committed" : "history";
    return "history";
  }, [action.state, undoable]);

  const label = (() => {
    if (variant === "approval") return "⚠ Approval";
    if (variant === "committed") return `✓ Committed · ${countdown}s`;
    if (variant === "history") return `✓ Committed · ${formatTimestamp(action.committed_at)}`;
    if (variant === "failed") return "✗ Failed";
    if (variant === "undone") return "↩ Undone";
    return "";
  })();

  const busy = !!action.busy;

  return (
    <div className={`rex-action-card rex-action-card--${variant}`}>
      <div className="rex-action-card__label">{label}</div>
      <div className="rex-action-card__primary">{action.primary}</div>
      {action.secondary ? (
        <div className="rex-action-card__secondary">{action.secondary}</div>
      ) : null}

      {variant === "approval" && Array.isArray(action.effects) && action.effects.length > 0 ? (
        <div className="rex-action-card__meta">
          {action.effects.map((r, i) => (
            <span key={i}>{i > 0 ? " · " : "ⓘ "}{r}</span>
          ))}
        </div>
      ) : null}

      {variant === "failed" && action.error_excerpt ? (
        <div className="rex-action-card__error">{action.error_excerpt}</div>
      ) : null}

      <div className="rex-action-card__actions">
        {variant === "approval" ? (
          <>
            <button className="rex-btn rex-btn-outline" disabled={busy} onClick={() => onDiscard && onDiscard(action)}>
              Discard
            </button>
            <button className="rex-btn rex-btn-primary" disabled={busy} onClick={() => onApprove && onApprove(action)}>
              {busy ? "Approving…" : "Approve"}
            </button>
          </>
        ) : null}
        {variant === "committed" ? (
          <button className="rex-btn rex-btn-outline" disabled={busy} onClick={() => onUndo && onUndo(action)}>
            {busy ? "Undoing…" : "Undo"}
          </button>
        ) : null}
        {variant === "failed" ? (
          <>
            <button className="rex-btn rex-btn-outline" disabled={busy} onClick={() => onDismiss && onDismiss(action)}>
              Dismiss
            </button>
            <button className="rex-btn rex-btn-primary" disabled={busy} onClick={() => onRetry && onRetry(action)}>
              {busy ? "Retrying…" : "Retry"}
            </button>
          </>
        ) : null}
      </div>
    </div>
  );
}
