// ChatThread — the active conversation message list.
//
// Renders user + assistant messages from `assistant.activeConversation.messages`.
// Streaming assistant messages are marked `streaming: true` and render
// with a blinking cursor suffix. Follow-up chips render below the last
// assistant message if `assistant.activeConversation.followups` is
// populated by the `followups.generated` SSE event.

import { useEffect, useRef } from "react";
import { useAssistantClient } from "./useAssistantClient";

export default function ChatThread() {
  const { assistant, sendMessage } = useAssistantClient();
  const { loading, error, messages, streaming, followups } = assistant.activeConversation;
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, streaming]);

  if (loading) {
    return (
      <div className="rex-assistant-thread rex-assistant-thread--loading">
        <p className="rex-muted" style={{ fontSize: 12 }}>Loading conversation…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rex-assistant-thread rex-assistant-thread--error">
        <p className="rex-muted" style={{ fontSize: 12, color: "var(--rex-red)" }}>
          {error}
        </p>
      </div>
    );
  }

  if (!messages || messages.length === 0) {
    return (
      <div className="rex-assistant-thread rex-assistant-thread--empty">
        <p className="rex-muted" style={{ fontSize: 12 }}>
          No messages yet. Type below, or pick a quick action from the Actions tab.
        </p>
      </div>
    );
  }

  return (
    <div className="rex-assistant-thread" role="log" aria-live="polite" aria-label="Assistant conversation">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      {followups && followups.length > 0 && !streaming && (
        <div className="rex-assistant-thread__followups">
          {followups.map((f, i) => (
            <button
              key={i}
              type="button"
              className="rex-assistant-thread__followup-chip"
              onClick={() => sendMessage(f)}
            >
              {f}
            </button>
          ))}
        </div>
      )}
      <div ref={bottomRef} aria-hidden="true" />
    </div>
  );
}

function MessageBubble({ message }) {
  const isUser = message.sender_type === "user";
  return (
    <div className={`rex-assistant-msg rex-assistant-msg--${isUser ? "user" : "assistant"}`}>
      <div className="rex-assistant-msg__sender">
        {isUser ? "You" : "Rex"}
      </div>
      <div className="rex-assistant-msg__content">
        {message.content}
        {message.streaming && <span className="rex-assistant-msg__cursor" aria-hidden="true">▍</span>}
      </div>
    </div>
  );
}
