// ChatComposer — free-form prompt input for the assistant.
//
// Keyboard: Enter submits, Shift+Enter inserts a newline.
// Disabled while streaming so users can't pile up racing requests.

import { useState, useCallback } from "react";
import { useAssistantClient } from "./useAssistantClient";

export default function ChatComposer() {
  const { assistant, sendMessage } = useAssistantClient();
  const [value, setValue] = useState("");
  const streaming = assistant.activeConversation.streaming;

  const submit = useCallback(async () => {
    const text = value.trim();
    if (!text) return;
    setValue("");
    await sendMessage(text);
  }, [value, sendMessage]);

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
        placeholder={streaming ? "Assistant is responding…" : "Ask Rex… (Enter to send, Shift+Enter for newline)"}
        rows={2}
        disabled={streaming}
        aria-label="Message the assistant"
      />
      {/*
        Intentionally type="button": using "submit" would collide with the
        existing Playwright e2e suite's generic `button[type="submit"]`
        selectors (which expect exactly one submit button on the page
        at a time — the active drawer form). Keyboard submission still
        works via the textarea's onKeyDown → submit().
      */}
      <button
        type="button"
        className="rex-assistant-composer__submit"
        disabled={streaming || !value.trim()}
        onClick={submit}
        aria-label="Send message"
      >
        {streaming ? "…" : "Send"}
      </button>
    </div>
  );
}
