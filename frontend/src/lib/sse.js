// SSE stream adapter for POST /api/assistant/chat.
//
// This is a thin client that handles the Session 1 event vocabulary:
//   conversation.created
//   message.started
//   message.delta
//   message.completed
//   followups.generated
//   action.suggestions
//   error
//
// When `USE_ASSISTANT_MOCKS` is true (default), `openAssistantStream`
// hands back a synthetic event emitter that simulates a streamed
// assistant response in ~2 seconds. The real implementation will use
// `fetch` with `body: ReadableStream` + `EventSource`-style parsing.

import { apiUrl, getToken } from "../api";
import { USE_ASSISTANT_MOCKS } from "./api";

/**
 * Open an assistant chat stream.
 *
 * @param {object} payload - POST /api/assistant/chat request body
 * @param {object} handlers - { onEvent(eventName, data), onError, onClose }
 * @returns {object} { close() } — call close() to abort the stream
 */
export function openAssistantStream(payload, handlers = {}) {
  if (USE_ASSISTANT_MOCKS) return openMockStream(payload, handlers);

  // Real path: POST to /api/assistant/chat with stream=true and parse
  // the SSE body. Not wired until Session 1 lands the endpoint.
  const controller = new AbortController();
  const token = getToken();

  fetch(apiUrl("/assistant/chat"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "text/event-stream",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ ...payload, stream: true }),
    signal: controller.signal,
  })
    .then((res) => {
      if (!res.ok || !res.body) {
        throw new Error(`Stream open failed: HTTP ${res.status}`);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const pump = async () => {
        while (true) {
          const { value, done } = await reader.read();
          if (done) {
            handlers.onClose?.();
            return;
          }
          buffer += decoder.decode(value, { stream: true });
          // Parse SSE frames separated by double newline
          let idx;
          while ((idx = buffer.indexOf("\n\n")) !== -1) {
            const frame = buffer.slice(0, idx);
            buffer = buffer.slice(idx + 2);
            const parsed = parseSseFrame(frame);
            if (parsed) handlers.onEvent?.(parsed.event, parsed.data);
          }
        }
      };

      pump().catch((err) => handlers.onError?.(err));
    })
    .catch((err) => handlers.onError?.(err));

  return { close: () => controller.abort() };
}

function parseSseFrame(frame) {
  let eventName = "message";
  let dataStr = "";
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) eventName = line.slice(6).trim();
    else if (line.startsWith("data:")) dataStr += line.slice(5).trim();
  }
  if (!dataStr) return null;
  try {
    return { event: eventName, data: JSON.parse(dataStr) };
  } catch {
    return { event: eventName, data: dataStr };
  }
}

// ── Mock stream ───────────────────────────────────────────────────────────
//
// Simulates a realistic-looking streamed assistant response so the UI can
// develop against real SSE semantics without the backend being live.

function openMockStream(payload, handlers) {
  let closed = false;
  const emit = (event, data) => {
    if (closed) return;
    queueMicrotask(() => handlers.onEvent?.(event, data));
  };

  const conversationId = payload.conversation_id || "mock-conv-" + Date.now();
  const userMessage = payload.message || "(no message)";
  const actionSlug = payload.active_action_slug || null;

  const response = generateMockResponse(userMessage, actionSlug);
  const tokens = response.split(" ");

  // Timeline:
  //   t=0:   conversation.created, message.started
  //   t=50..150ms × tokens: message.delta for each token
  //   t=end: message.completed, followups.generated
  setTimeout(() => emit("conversation.created", { conversation_id: conversationId }), 0);
  setTimeout(() => emit("message.started", { conversation_id: conversationId, sender_type: "assistant" }), 10);

  let accumulated = "";
  tokens.forEach((tok, i) => {
    setTimeout(() => {
      accumulated += (i === 0 ? "" : " ") + tok;
      emit("message.delta", { delta: (i === 0 ? "" : " ") + tok, accumulated });
    }, 40 + i * 45);
  });

  const tEnd = 40 + tokens.length * 45 + 100;
  setTimeout(() => emit("message.completed", {
    conversation_id: conversationId,
    content: accumulated,
  }), tEnd);

  setTimeout(() => emit("followups.generated", {
    followups: generateMockFollowups(actionSlug),
  }), tEnd + 80);

  setTimeout(() => handlers.onClose?.(), tEnd + 200);

  return {
    close: () => {
      closed = true;
      handlers.onClose?.();
    },
  };
}

function generateMockResponse(userMessage, actionSlug) {
  if (actionSlug === "budget_variance") {
    return "Budget Variance for Tower 3 shows the current projected cost is 3.2% over the revised budget. The top three drivers are 03 Concrete (+$42k), 09 Finishes (+$18k), and 26 Electrical (+$12k). 01 General Requirements is tracking under by $9k.";
  }
  if (actionSlug === "morning_briefing") {
    return "Morning briefing: 2 RFIs are aging past 7 days on Tower 3 and Jungle Lakewood. One submittal is overdue for A&E review. Schedule is on track for this week's 2-week lookahead milestones.";
  }
  if (actionSlug === "rfi_aging") {
    return "There are 4 open RFIs past 7 days across the portfolio. Tower 3 has 2, Jungle Lakewood has 1, Jungle Fort Worth has 1. The oldest is RFI-0042 on Tower 3 at 12 days.";
  }
  return `I hear you asking about "${userMessage}". This is a mocked assistant response — the live AI spine lands in Session 1. Until then, the UI is fully exercising the streaming + follow-up path against this simulated data.`;
}

function generateMockFollowups(actionSlug) {
  if (actionSlug === "budget_variance") {
    return ["Show top 5 cost codes", "Compare against last month", "Export to PDF"];
  }
  if (actionSlug === "morning_briefing") {
    return ["Show RFI details", "Open punch list", "View schedule health"];
  }
  return ["Tell me more", "Show the underlying data", "Summarize for an exec email"];
}
