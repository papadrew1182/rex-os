// Pure-Node tests for actionSummary. Matches the pattern in
// useAssistantState.test.js — Node's built-in assert, run via
// `node frontend/src/assistant/__tests__/actionSummary.test.js`.
import assert from "node:assert/strict";
import { formatActionSummary } from "../actionSummary.js";

// create_task — uses args.title
{
  const s = formatActionSummary("create_task",
    { title: "Check the duct conflict", project_id: "abc" },
    null);
  assert.equal(s.primary, "Create task");
  assert.equal(s.secondary, "Check the duct conflict");
}

// create_task — falls back to result.title on auto-commit
{
  const s = formatActionSummary("create_task",
    {},
    { task_id: "x", task_number: 14, title: "Inspect grid B/4" });
  assert.equal(s.primary, "Create task");
  assert.ok(s.secondary.includes("Inspect grid B/4"));
}

// update_task_status — with previous_status shows transition
{
  const s = formatActionSummary("update_task_status",
    { task_id: "t", status: "complete" },
    { previous_status: "open", new_status: "complete" });
  assert.equal(s.primary, "Update task status");
  assert.ok(/open/.test(s.secondary));
  assert.ok(/complete/.test(s.secondary));
}

// update_task_status — without previous_status shows new status only
{
  const s = formatActionSummary("update_task_status",
    { task_id: "t", status: "in_progress" },
    null);
  assert.equal(s.primary, "Update task status");
  assert.ok(/in_progress/.test(s.secondary));
}

// create_note
{
  const s = formatActionSummary("create_note",
    { content: "Remember to chase insulation sub" },
    null);
  assert.equal(s.primary, "Create note");
  assert.ok(s.secondary.startsWith("Remember to chase"));
}

// answer_rfi
{
  const s = formatActionSummary("answer_rfi",
    { rfi_id: "r", answer: "Confirmed — use revised detail A-501" },
    null);
  assert.equal(s.primary, "Answer RFI");
  assert.ok(s.secondary.includes("Confirmed"));
}

// save_meeting_packet
{
  const s = formatActionSummary("save_meeting_packet",
    { meeting_id: "m", packet_url: "https://ex.com/packet.pdf" },
    null);
  assert.equal(s.primary, "Save meeting packet");
  assert.ok(s.secondary.includes("packet.pdf"));
}

// save_draft
{
  const s = formatActionSummary("save_draft",
    { subject: "Duct conflict follow-up", body: "..." },
    null);
  assert.equal(s.primary, "Save draft email");
  assert.ok(s.secondary.includes("Duct conflict follow-up"));
}

// create_alert
{
  const s = formatActionSummary("create_alert",
    { severity: "warning", title: "Daily log missing" },
    null);
  assert.equal(s.primary, "Create alert");
  assert.ok(s.secondary.includes("Daily log missing"));
}

// delete_task — uses snapshot from result
{
  const s = formatActionSummary("delete_task",
    { task_id: "t" },
    { snapshot: { title: "Old obsolete task", task_number: 9 } });
  assert.equal(s.primary, "Delete task");
  assert.ok(s.secondary.includes("Old obsolete task"));
}

// delete_note — snapshot
{
  const s = formatActionSummary("delete_note",
    { note_id: "n" },
    { snapshot: { content: "Scratch note to discard" } });
  assert.equal(s.primary, "Delete note");
  assert.ok(s.secondary.includes("Scratch note"));
}

// Unknown slug degrades gracefully
{
  const s = formatActionSummary("mystery_tool", { foo: "bar" }, null);
  assert.equal(s.primary, "mystery_tool");
  assert.ok(typeof s.secondary === "string");
}

// Null/undefined inputs don't crash
{
  const s = formatActionSummary("create_task", null, null);
  assert.equal(s.primary, "Create task");
  assert.ok(typeof s.secondary === "string");
}

console.log("actionSummary: all tests passed");
