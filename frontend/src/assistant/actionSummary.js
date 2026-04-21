// frontend/src/assistant/actionSummary.js
// Pure utility: translate an action's (slug, tool_args, result) into
// (primary, secondary) strings for the ActionCard. All logic is
// tool-specific; adding a new tool requires one case here.

function truncate(s, n = 120) {
  if (!s) return "";
  const str = String(s);
  return str.length > n ? str.slice(0, n - 1) + "…" : str;
}

const HANDLERS = {
  create_task: (args, result) => ({
    primary: "Create task",
    secondary: truncate(args?.title ?? result?.title ?? "(no title)"),
  }),
  update_task_status: (args, result) => ({
    primary: "Update task status",
    secondary: result?.previous_status
      ? `${result.previous_status} → ${args?.status ?? result?.new_status ?? "?"}`
      : `status → ${args?.status ?? "?"}`,
  }),
  create_note: (args, result) => ({
    primary: "Create note",
    secondary: truncate(args?.content ?? result?.content ?? ""),
  }),
  answer_rfi: (args) => ({
    primary: "Answer RFI",
    secondary: truncate(args?.answer ?? "(no answer)", 140),
  }),
  save_meeting_packet: (args) => ({
    primary: "Save meeting packet",
    secondary: truncate(args?.packet_url ?? "(no url)"),
  }),
  save_draft: (args) => ({
    primary: "Save draft email",
    secondary: truncate(args?.subject ?? "(no subject)"),
  }),
  create_alert: (args) => ({
    primary: "Create alert",
    secondary: truncate(args?.title ?? "(no title)"),
  }),
  delete_task: (args, result) => ({
    primary: "Delete task",
    secondary: truncate(result?.snapshot?.title ?? `task ${args?.task_id ?? "?"}`),
  }),
  delete_note: (args, result) => ({
    primary: "Delete note",
    secondary: truncate(result?.snapshot?.content ?? `note ${args?.note_id ?? "?"}`),
  }),
};

export function formatActionSummary(slug, toolArgs, resultPayload) {
  const handler = HANDLERS[slug];
  if (!handler) {
    return { primary: slug, secondary: "" };
  }
  try {
    return handler(toolArgs || {}, resultPayload || null);
  } catch (_e) {
    return { primary: slug, secondary: "" };
  }
}
