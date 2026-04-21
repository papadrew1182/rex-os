// ChatThread — the active conversation message list.
//
// Renders messages from `assistant.activeConversation.messages`.
// Streaming assistant messages are tagged `streaming: true` and render
// with a blinking cursor. Errored messages show an error banner with
// a retry button (pulls from `activeConversation.lastFailedMessage`).
// Aborted messages (user navigated away mid-stream) render in a muted
// style with an "aborted" tag.
//
// Follow-up chips render below the last assistant message when the
// stream is idle and `followups` is populated. Action suggestions
// render alongside, labelled — these come from the defensive
// STREAM_ACTION_SUGGESTIONS handler in the reducer.

import { useContext, useEffect, useRef } from "react";
import { useAssistantClient } from "./useAssistantClient";
import { AppContext } from "../app/AppContext";
import ActionCard from "./ActionCard.jsx";
import { ASSISTANT_ACTIONS } from "./useAssistantState";
import { approveAction, discardAction, undoAction } from "../lib/actionsApi.js";

export default function ChatThread() {
  const { assistant, sendMessage, retryLastFailed } = useAssistantClient();
  const ctx = useContext(AppContext);
  const {
    loading,
    error,
    messages,
    streaming,
    followups,
    actionSuggestions,
    lastFailedMessage,
  } = assistant.activeConversation;
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, streaming]);

  // ── Action card handlers ─────────────────────────────────────────
  // Wire ActionCard buttons (Approve / Discard / Undo / Retry /
  // Dismiss) through actionsApi and dispatch reducer updates based on
  // the HTTP response. All handlers flip `busy` true at entry and
  // clear it at exit so the ActionCard disables buttons during the
  // round-trip.

  const markBusy = (action_id, busy) =>
    ctx.assistantDispatch({
      type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
      payload: { action_id, busy },
    });

  const handleApprove = async (action) => {
    markBusy(action.action_id, true);
    try {
      await approveAction(action.action_id);
      ctx.assistantDispatch({
        type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
        payload: {
          action_id: action.action_id,
          state: "committed",
          committed_at: new Date().toISOString(),
          busy: false,
        },
      });
    } catch (e) {
      ctx.assistantDispatch({
        type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
        payload: {
          action_id: action.action_id,
          state: "failed",
          error_excerpt: (e && e.message) || String(e),
          busy: false,
        },
      });
    }
  };

  const handleDiscard = async (action) => {
    markBusy(action.action_id, true);
    try {
      await discardAction(action.action_id);
      ctx.assistantDispatch({
        type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
        payload: { action_id: action.action_id, state: "undone", busy: false },
      });
    } catch (e) {
      markBusy(action.action_id, false);
      // Non-fatal — just surface via console; no UI change.
      // eslint-disable-next-line no-console
      console.error("discard failed", e);
    }
  };

  const handleUndo = async (action) => {
    markBusy(action.action_id, true);
    const { status, body } = await undoAction(action.action_id);
    if (status === 200) {
      ctx.assistantDispatch({
        type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
        payload: {
          action_id: action.action_id,
          state: "undone",
          undone_at: new Date().toISOString(),
          busy: false,
        },
      });
    } else if (status === 400) {
      // Window expired — drop the busy flag; ActionCard will re-render
      // as history (no Undo button) when countdown hits 0.
      ctx.assistantDispatch({
        type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
        payload: { action_id: action.action_id, busy: false },
      });
    } else {
      ctx.assistantDispatch({
        type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
        payload: {
          action_id: action.action_id,
          state: "failed",
          error_excerpt:
            (body && (body.detail || body.error)) ||
            `undo failed (status ${status})`,
          busy: false,
        },
      });
    }
  };

  const handleRetry = (action) => handleApprove(action);

  const handleDismiss = (action) => {
    // Local hide — backend row stays for audit. Flip to 'undone' so the
    // ActionCard renders as strikethrough history.
    ctx.assistantDispatch({
      type: ASSISTANT_ACTIONS.ACTION_STATE_UPDATED,
      payload: { action_id: action.action_id, state: "undone", busy: false },
    });
  };

  if (loading) {
    return (
      <div className="rex-assistant-thread rex-assistant-thread--loading" role="status">
        <p className="rex-muted" style={{ fontSize: 12 }}>Loading conversation…</p>
      </div>
    );
  }

  const hasMessages = messages && messages.length > 0;

  if (!hasMessages && !error) {
    return (
      <div className="rex-assistant-thread rex-assistant-thread--empty" role="status">
        <p className="rex-muted" style={{ fontSize: 12 }}>
          No messages yet. Type below, or pick a quick action from the Actions tab.
        </p>
      </div>
    );
  }

  return (
    <div className="rex-assistant-thread" role="log" aria-live="polite" aria-label="Assistant conversation">
      {messages.map((msg) => {
        if (msg.type === "action") {
          return (
            <ActionCard
              key={msg.action_id}
              action={msg}
              onApprove={handleApprove}
              onDiscard={handleDiscard}
              onUndo={handleUndo}
              onRetry={handleRetry}
              onDismiss={handleDismiss}
            />
          );
        }
        return <MessageBubble key={msg.id} message={msg} />;
      })}

      {streaming && (
        <div className="rex-assistant-thread__status" aria-live="polite">
          <span className="rex-assistant-thread__dot" aria-hidden="true" />
          Streaming…
        </div>
      )}

      {error && !streaming && (
        <div className="rex-assistant-thread__error" role="alert">
          <div className="rex-assistant-thread__error-title">Something interrupted the response</div>
          <div className="rex-assistant-thread__error-detail">{error}</div>
          {lastFailedMessage && (
            <button
              type="button"
              className="rex-assistant-thread__retry"
              onClick={retryLastFailed}
            >
              Retry
            </button>
          )}
        </div>
      )}

      {!streaming && followups && followups.length > 0 && (
        <div className="rex-assistant-thread__followups" aria-label="Suggested follow-ups">
          {followups.map((f, i) => (
            <button
              key={i}
              type="button"
              className="rex-assistant-thread__followup-chip"
              onClick={() => sendMessage(f)}
              disabled={assistant.ui.pending}
            >
              {f}
            </button>
          ))}
        </div>
      )}

      {!streaming && actionSuggestions && actionSuggestions.length > 0 && (
        <div className="rex-assistant-thread__suggestions" aria-label="Suggested actions">
          <div className="rex-assistant-thread__suggestions-label">Related actions</div>
          <div className="rex-assistant-thread__suggestions-chips">
            {actionSuggestions.map((s, i) => {
              // Defensive render: accept object {slug, reason}, string,
              // or unknown — only render what we can safely display.
              const slug = typeof s === "string" ? s : s?.slug;
              const reason = typeof s === "string" ? null : s?.reason;
              if (!slug) return null;
              return (
                <button
                  key={`${slug}-${i}`}
                  type="button"
                  className="rex-assistant-thread__suggestion-chip"
                  title={reason || slug}
                  onClick={() => sendMessage(`Run ${slug}`, { activeActionSlug: slug })}
                  disabled={assistant.ui.pending}
                >
                  {slug.replace(/_/g, " ")}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div ref={bottomRef} aria-hidden="true" />
    </div>
  );
}

function MessageBubble({ message }) {
  const isUser = message.sender_type === "user";
  const classes = [
    "rex-assistant-msg",
    isUser ? "rex-assistant-msg--user" : "rex-assistant-msg--assistant",
    message.aborted ? "rex-assistant-msg--aborted" : "",
    message.error ? "rex-assistant-msg--error" : "",
  ].filter(Boolean).join(" ");

  return (
    <div className={classes}>
      <div className="rex-assistant-msg__sender">
        {isUser ? "You" : "Rex"}
        {message.aborted && <span className="rex-assistant-msg__tag">aborted</span>}
        {message.error && <span className="rex-assistant-msg__tag rex-assistant-msg__tag--error">error</span>}
      </div>
      <div className="rex-assistant-msg__content">
        {message.content || (message.streaming ? " " : "")}
        {message.streaming && <span className="rex-assistant-msg__cursor" aria-hidden="true">▍</span>}
      </div>
    </div>
  );
}
