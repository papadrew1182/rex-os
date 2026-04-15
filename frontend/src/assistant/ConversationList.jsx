// ConversationList — recent assistant conversations.
//
// Data source: `conversations` bucket in the assistant reducer, loaded
// by AppContext's `loadConversations` once identity is known.

import { useAssistantClient } from "./useAssistantClient";

function formatRelative(iso) {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffMin = Math.round((now - then) / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  return `${diffDay}d ago`;
}

export default function ConversationList() {
  const { assistant, selectConversation } = useAssistantClient();
  const { loading, error, items } = assistant.conversations;
  const activeId = assistant.activeConversation.id;

  if (loading && items.length === 0) {
    return (
      <div className="rex-assistant-list rex-assistant-list--loading">
        <p className="rex-muted" style={{ fontSize: 12 }}>Loading history…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rex-assistant-list rex-assistant-list--error">
        <p className="rex-muted" style={{ fontSize: 12, color: "var(--rex-red)" }}>
          Couldn't load history: {error}
        </p>
      </div>
    );
  }

  if (!items || items.length === 0) {
    return (
      <div className="rex-assistant-list rex-assistant-list--empty">
        <p className="rex-muted" style={{ fontSize: 12 }}>
          No past conversations yet. Ask a question or launch a quick action to start one.
        </p>
      </div>
    );
  }

  return (
    <ul className="rex-assistant-list" role="list">
      {items.map((conv) => (
        <li
          key={conv.id}
          className={`rex-assistant-list__item${activeId === conv.id ? " rex-assistant-list__item--active" : ""}`}
        >
          <button
            type="button"
            className="rex-assistant-list__button"
            onClick={() => selectConversation(conv.id)}
            aria-current={activeId === conv.id ? "true" : undefined}
          >
            <div className="rex-assistant-list__title">{conv.title || "Untitled"}</div>
            {conv.last_message_preview && (
              <div className="rex-assistant-list__preview">{conv.last_message_preview}</div>
            )}
            <div className="rex-assistant-list__meta">
              {conv.active_action_slug && <span className="rex-assistant-list__slug">{conv.active_action_slug}</span>}
              <span className="rex-assistant-list__time">{formatRelative(conv.last_message_at)}</span>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
