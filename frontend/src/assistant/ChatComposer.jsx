// ChatComposer — free-form prompt input for the assistant.
//
// Keyboard: Enter submits, Shift+Enter inserts a newline.
// Disabled while a send is pending (POST in flight OR stream running)
// so users can't pile up racing requests. Uses the `pending` flag
// from the assistant reducer which is set at SEND_PENDING and cleared
// at SEND_SETTLED or STREAM_CLOSED.
//
// NOTE: This is a <div>, not a <form>. The submit button is
// type="button" with an explicit onClick handler. Reason: the legacy
// Playwright smoke suite uses generic `button[type="submit"]`
// locators that assume exactly one submit button on the page (the
// active drawer form). A second submit button from the right-rail
// composer would trigger strict-mode violations.

import { useState, useCallback } from "react";
import { useAssistantClient } from "./useAssistantClient";

export default function ChatComposer() {
  const { assistant, sendMessage } = useAssistantClient();
  const [value, setValue] = useState("");
  const pending = assistant.ui.pending;
  const streaming = assistant.activeConversation.streaming;
  const disabled = pending || streaming;

  const submit = useCallback(async () => {
    const text = value.trim();
    if (!text || disabled) return;
    setValue("");
    await sendMessage(text);
  }, [value, disabled, sendMessage]);

  const onKeyDown = useCallback((e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }, [submit]);

  return (
    <div
      className="rex-assistant-composer"
      role="group"
      aria-label="Message composer"
    >
      <textarea
        className="rex-assistant-composer__input"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKeyDown}
        placeholder={
          streaming ? "Assistant is responding…"
          : pending ? "Sending…"
          : "Ask Rex… (Enter to send, Shift+Enter for newline)"
        }
        rows={2}
        disabled={disabled}
        aria-label="Message the assistant"
      />
      <button
        type="button"
        className="rex-assistant-composer__submit"
        disabled={disabled || !value.trim()}
        onClick={submit}
        aria-label="Send message"
      >
        {streaming ? "…" : pending ? "…" : "Send"}
      </button>
    </div>
  );
}
