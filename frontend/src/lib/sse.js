// SSE stream adapter for POST /api/assistant/chat.
//
// Contract-frozen event vocabulary (Session 3 packet §chat SSE):
//   conversation.created
//   message.started
//   message.delta
//   message.completed
//   followups.generated
//   action.suggestions
//   error
//
// Two code paths share a single public API:
//   - Mock emitter: synthesises a realistic token-by-token stream,
//     honours close() immediately, suppresses late callbacks after
//     close (so React gets no reducer dispatches against a dead tree)
//   - Live fetch+ReadableStream: POSTs the payload, parses SSE frames
//     off the response body via the pure parseSseFrame from sseParser.js,
//     aborts via AbortController, also suppresses late callbacks after close
//
// Live path cutover notes:
//   - The buffer normalizes \r\n → \n on every chunk so real servers
//     that emit CRLF frame boundaries (\r\n\r\n) tokenize identically
//     to LF-only servers. The parser also strips a trailing \r per line
//     as a safety net.
//   - The first successfully-parsed frame marks the `chatStream`
//     surface as `live` in integrationSource. Fetch errors mark it
//     `unavailable`. Aborts do neither (normal close).
//   - Unknown event names (e.g. an experimental backend emitting
//     `tool.called`) produce a one-shot console.warn per event name
//     via isKnownSseEvent and are still forwarded to the reducer,
//     which default-drops them. This surfaces vocabulary drift without
//     breaking thread render.
//
// Open Session 1 question: the `action.suggestions` payload shape is
// not fully contract-frozen. The frontend accepts two shapes
// defensively in the reducer (see safeActionSuggestions() in
// assistant/useAssistantState.js) — { suggestions: [{slug, reason}] }
// or a bare [slug, ...] array. When Session 1 freezes the shape,
// update contractProbes.js to enforce it and trim the reducer fallback.
//
// Public API:
//
//   const handle = openAssistantStream(payload, {
//     onEvent(eventName, data) { ... },
//     onError(err) { ... },
//     onClose() { ... },
//   });
//   handle.close();   // abort — safe to call multiple times

import { apiUrl, getToken } from "../api";
import { shouldUseMocks } from "./api";
import { markLive, markMock, markUnavailable, markPending } from "./integrationSource";
import { isKnownSseEvent } from "./contractProbes";
import { parseSseFrame } from "./sseParser";

/**
 * Open an assistant chat stream.
 *
 * @param {object} payload   - POST /api/assistant/chat request body
 * @param {object} handlers  - { onEvent, onError, onClose }
 * @returns {{ close: () => void, isClosed: () => boolean }}
 */
export function openAssistantStream(payload, handlers = {}) {
  // Wrap the caller's handlers with a "closed" guard so that late
  // events after handle.close() never dispatch into a dead UI tree.
  // Also route any unknown SSE event through a one-time developer
  // warning without dropping it — the reducer switches default-skips
  // unknown names anyway, but operators should see drift surfaced.
  let closed = false;
  const unknownSeen = new Set();
  const guarded = {
    onEvent: (event, data) => {
      if (closed) return;
      if (!isKnownSseEvent(event) && !unknownSeen.has(event)) {
        unknownSeen.add(event);
        // eslint-disable-next-line no-console
        console.warn(`[integration] unknown SSE event '${event}' — reducer will skip`);
      }
      try { handlers.onEvent?.(event, data); } catch { /* host errors are not stream errors */ }
    },
    onError: (err) => {
      if (closed) return;
      try { handlers.onError?.(err); } catch { /* ignore */ }
    },
    onClose: () => {
      try { handlers.onClose?.(); } catch { /* ignore */ }
    },
  };

  if (shouldUseMocks()) {
    markMock("chatStream");
    const handle = openMockStream(payload, guarded);
    return {
      close: () => {
        if (closed) return;
        closed = true;
        handle.close();
        guarded.onClose();
      },
      isClosed: () => closed,
    };
  }

  markPending("chatStream");

  // ── Live path ───────────────────────────────────────────────────────
  const controller = new AbortController();
  const token = getToken();

  let sawFirstEvent = false;

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
    .then(async (res) => {
      if (!res.ok || !res.body) {
        throw new Error(`Stream open failed: HTTP ${res.status}`);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      const dispatchFrame = (frame) => {
        const parsed = parseSseFrame(frame);
        if (!parsed) return;
        if (!sawFirstEvent) {
          sawFirstEvent = true;
          markLive("chatStream");
        }
        guarded.onEvent(parsed.event, parsed.data);
      };

      // eslint-disable-next-line no-constant-condition
      while (true) {
        let chunk;
        try {
          chunk = await reader.read();
        } catch (err) {
          if (err?.name === "AbortError" || closed) {
            guarded.onClose();
            return;
          }
          guarded.onError(err);
          guarded.onClose();
          return;
        }
        const { value, done } = chunk;
        if (done) {
          if (buffer.trim()) dispatchFrame(buffer);
          guarded.onClose();
          return;
        }
        // Normalize CRLF → LF so real servers that emit "\r\n\r\n"
        // frame boundaries tokenize the same as LF-only servers.
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        let idx;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const frame = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          dispatchFrame(frame);
        }
      }
    })
    .catch((err) => {
      if (closed || err?.name === "AbortError") {
        guarded.onClose();
        return;
      }
      markUnavailable("chatStream", { error: err });
      guarded.onError(err);
      guarded.onClose();
    });

  return {
    close: () => {
      if (closed) return;
      closed = true;
      try { controller.abort(); } catch { /* ignore */ }
      guarded.onClose();
    },
    isClosed: () => closed,
  };
}

// The real SSE frame parser lives in `sseParser.js` (pure, no browser
// imports) so it is Node-unit-testable without dragging fetch /
// ReadableStream / apiUrl through the import tree.

// ── Mock stream ───────────────────────────────────────────────────────────
//
// Simulates a realistic-looking streamed assistant response so the UI
// can develop against real SSE semantics without the backend being
// live. setTimeout callbacks are cancelled on close() so a rapid
// navigate-away doesn't leak pending timers into the dispatcher.

function openMockStream(payload, handlers) {
  const timers = [];
  let stopped = false;
  const schedule = (fn, delay) => {
    const t = setTimeout(() => {
      if (stopped) return;
      fn();
    }, delay);
    timers.push(t);
  };

  const conversationId = payload.conversation_id || "mock-conv-" + Date.now();
  const userMessage = payload.message || "(no message)";
  const actionSlug = payload.active_action_slug || null;
  const mode = payload.mode || "chat";

  const response = generateMockResponse(userMessage, actionSlug, mode);
  const tokens = response.split(" ");

  schedule(() => handlers.onEvent("conversation.created", { conversation_id: conversationId }), 0);
  schedule(() => handlers.onEvent("message.started", { conversation_id: conversationId, sender_type: "assistant" }), 10);

  let accumulated = "";
  tokens.forEach((tok, i) => {
    schedule(() => {
      accumulated += (i === 0 ? "" : " ") + tok;
      handlers.onEvent("message.delta", { delta: (i === 0 ? "" : " ") + tok, accumulated });
    }, 40 + i * 35);
  });

  const tEnd = 40 + tokens.length * 35 + 100;
  schedule(() => handlers.onEvent("message.completed", {
    conversation_id: conversationId,
    content: accumulated,
  }), tEnd);

  schedule(() => handlers.onEvent("followups.generated", {
    followups: generateMockFollowups(actionSlug),
  }), tEnd + 60);

  // Action suggestions are optional — only emit for a subset of slugs
  // so the defensive rendering path in the reducer gets exercised.
  if (actionSlug === "morning_briefing" || actionSlug === "my_day_briefing") {
    schedule(() => handlers.onEvent("action.suggestions", {
      suggestions: [
        { slug: "rfi_aging", reason: "2 RFIs aging past 7 days" },
        { slug: "submittal_sla", reason: "1 submittal overdue for A&E review" },
      ],
    }), tEnd + 120);
  }

  schedule(() => handlers.onClose?.(), tEnd + 200);

  return {
    close: () => {
      stopped = true;
      for (const t of timers) clearTimeout(t);
    },
  };
}

function generateMockResponse(userMessage, actionSlug, mode) {
  if (mode === "command") {
    return `Command mode is in writeback_pending readiness until Session 1 lands the command parser. I parsed your input as plain chat: "${userMessage}". Once the parser is live, low-risk commands (tasks, notes, meeting packets, drafts) will auto-pass-through and high-risk commands (financial, schedule, Procore writes) will queue for approval.`;
  }
  if (actionSlug === "budget_variance") {
    return "Budget Variance for Bishop Modern shows the current projected cost is 3.2% over the revised budget. The top three drivers are 03 Concrete (+$42k), 09 Finishes (+$18k), and 26 Electrical (+$12k). 01 General Requirements is tracking under by $9k.";
  }
  if (actionSlug === "morning_briefing" || actionSlug === "my_day_briefing") {
    return "Morning briefing: 2 RFIs are aging past 7 days on Bishop Modern and Jungle Lakewood. One submittal is overdue for A&E review. Schedule is on track for this week's 2-week lookahead milestones. Weather looks clear through Thursday.";
  }
  if (actionSlug === "rfi_aging") {
    return "There are 4 open RFIs past 7 days across the portfolio. Bishop Modern has 2, Jungle Lakewood has 1, Jungle Fort Worth has 1. The oldest is RFI-0042 on Bishop Modern at 12 days, ball-in-court with the architect.";
  }
  if (actionSlug === "critical_path_delays") {
    return "Critical path currently shows 3 tasks behind schedule on Bishop Modern. The structural steel delivery has pushed the frame-out milestone right by 4 days. No float remains on the concrete-to-steel handoff.";
  }
  if (actionSlug === "two_week_lookahead") {
    return "Next 14 days on Bishop Modern: MEP rough-in completes Wednesday, drywall starts Friday, fire sprinkler inspection scheduled Monday. Three trades need RFIs resolved before their windows — see follow-ups.";
  }
  if (actionSlug === "daily_log_summary") {
    return "Yesterday's daily log: 47 workers across 6 trades. Apex Concrete poured column footings F-3 through F-7. Voltmark Electric ran conduit on level 2 east. No safety incidents, no weather delays.";
  }
  return `I hear you asking about "${userMessage}". This is a mocked assistant response — the live AI spine lands in Session 1. Until then, the UI is fully exercising the streaming + follow-up path against this simulated data.`;
}

function generateMockFollowups(actionSlug) {
  if (actionSlug === "budget_variance") {
    return ["Show top 5 cost codes", "Compare against last month", "Export to PDF"];
  }
  if (actionSlug === "morning_briefing" || actionSlug === "my_day_briefing") {
    return ["Show RFI details", "Open punch list", "View schedule health"];
  }
  if (actionSlug === "rfi_aging") {
    return ["Open Bishop Modern RFIs", "Show ball-in-court breakdown", "Draft a reminder to the architect"];
  }
  if (actionSlug === "critical_path_delays") {
    return ["Show affected milestones", "View schedule variance", "Draft recovery plan"];
  }
  return ["Tell me more", "Show the underlying data", "Summarize for an exec email"];
}
