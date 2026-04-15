// CommandModePanel — thin first-pass command mode entry.
//
// Phase 6 of the roadmap is where command mode actually parses
// natural-language into approved actions. For this first pass we
// simply surface a distinct input that posts with `mode: "command"`
// so the backend AI spine (Session 1) can route the message to the
// command parser when it's live.
//
// The UX copy makes it clear that:
//   - this is early
//   - low-risk commands may auto-pass-through
//   - high-risk commands will queue for approval

import { useState, useCallback } from "react";
import { useAssistantClient } from "./useAssistantClient";

export default function CommandModePanel() {
  const { assistant, sendMessage } = useAssistantClient();
  const [value, setValue] = useState("");
  const streaming = assistant.activeConversation.streaming;

  const submit = useCallback(async () => {
    const text = value.trim();
    if (!text) return;
    setValue("");
    await sendMessage(text, { mode: "command" });
  }, [value, sendMessage]);

  return (
    <div className="rex-command-panel">
      <div className="rex-command-panel__header">
        <h4 className="rex-command-panel__title">Command mode</h4>
        <p className="rex-command-panel__subtitle">
          Type what you want done in plain English. Low-risk actions (tasks, notes,
          meeting packets) run immediately. Financial, schedule-affecting, or
          official Procore writes go to the approval queue.
        </p>
      </div>
      <div className="rex-command-panel__form" role="group" aria-label="Command mode composer">
        <textarea
          className="rex-command-panel__input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={'e.g. "Create a task for Mitch to verify the concrete pour at Bishop Modern tomorrow morning"'}
          rows={4}
          disabled={streaming}
          aria-label="Command mode input"
        />
        {/* type="button" per the same Playwright collision rationale in ChatComposer.jsx */}
        <button
          type="button"
          className="rex-command-panel__submit"
          disabled={streaming || !value.trim()}
          onClick={submit}
        >
          {streaming ? "Parsing…" : "Run command"}
        </button>
      </div>
      <div className="rex-command-panel__note">
        Command mode is in the <strong>writeback_pending</strong> readiness tier
        until Session 1 lands the command parser + action queue. You can type
        messages now — they will be routed as regular chat until the parser is
        live.
      </div>
    </div>
  );
}
