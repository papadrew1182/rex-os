import { useEffect, useMemo, useRef, useState } from "react";
import { API_BASE, api, getToken } from "./api";

const FALLBACK_ACTIONS = [
  "rfi_aging",
  "submittal_sla",
  "budget_variance",
  "daily_log_summary",
  "critical_path_delays",
  "two_week_lookahead",
];

function toApiUrl(path) {
  if (path.startsWith("/api")) return `${API_BASE}${path}`;
  return `${API_BASE}/api${path}`;
}

export function AiFab({ onClick }) {
  return (
    <button className="rex-ai-fab" type="button" onClick={onClick} aria-label="Open AI quick actions panel">
      AI
    </button>
  );
}

export default function AiPanel({ open, onClose }) {
  const [catalog, setCatalog] = useState(FALLBACK_ACTIONS);
  const [prompt, setPrompt] = useState("");
  const [streamText, setStreamText] = useState("");
  const [loadingCatalog, setLoadingCatalog] = useState(false);
  const [sending, setSending] = useState(false);
  const streamRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    let mounted = true;
    setLoadingCatalog(true);
    api("/assistant/catalog")
      .then((res) => {
        if (!mounted) return;
        const items = Array.isArray(res?.actions)
          ? res.actions.map((a) => a.slug).filter(Boolean)
          : Array.isArray(res)
            ? res.map((a) => a.slug || a).filter(Boolean)
            : [];
        if (items.length > 0) setCatalog(items);
      })
      .catch(() => {
        if (mounted) setCatalog(FALLBACK_ACTIONS);
      })
      .finally(() => {
        if (mounted) setLoadingCatalog(false);
      });
    return () => {
      mounted = false;
    };
  }, [open]);

  useEffect(() => {
    return () => {
      if (streamRef.current) streamRef.current.abort();
    };
  }, []);

  const quickActions = useMemo(() => catalog.slice(0, 12), [catalog]);

  async function send() {
    const text = prompt.trim();
    if (!text || sending) return;
    setSending(true);
    setStreamText("");

    if (streamRef.current) streamRef.current.abort();
    const controller = new AbortController();
    streamRef.current = controller;

    try {
      const token = getToken();
      const res = await fetch(toApiUrl("/assistant/chat"), {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ message: text }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`HTTP ${res.status}`);
      }

      const decoder = new TextDecoder();
      const reader = res.body.getReader();
      let buffer = "";

      while (!controller.signal.aborted) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const payload = line.slice(5).trim();
          if (!payload || payload === "[DONE]") continue;
          try {
            const parsed = JSON.parse(payload);
            const chunk = parsed?.delta || parsed?.text || parsed?.message || "";
            if (chunk) setStreamText((prev) => prev + chunk);
          } catch {
            setStreamText((prev) => prev + payload);
          }
        }
      }
    } catch (err) {
      if (err?.name !== "AbortError") {
        setStreamText((prev) => `${prev}\n\n[assistant stream failed]`);
      }
    } finally {
      setSending(false);
    }
  }

  if (!open) return null;

  return (
    <>
      <div className="rex-ai-overlay" onClick={onClose} aria-hidden="true" />
      <aside className="rex-ai-panel" aria-label="AI quick actions panel">
        <div className="rex-ai-panel-header">
          <h3 className="rex-h3">AI Quick Actions</h3>
          <button type="button" className="rex-btn rex-btn-outline" onClick={onClose}>Close</button>
        </div>

        <p className="rex-muted" style={{ marginTop: 6 }}>
          Ask Rex Assistant to run analysis, draft updates, or queue actions for approval.
        </p>

        <div className="rex-ai-action-list" aria-live="polite">
          {(loadingCatalog ? FALLBACK_ACTIONS : quickActions).map((slug) => (
            <button
              type="button"
              key={slug}
              className="rex-ai-action-pill"
              onClick={() => setPrompt((p) => (p ? `${p} ${slug}` : slug))}
            >
              {slug}
            </button>
          ))}
        </div>

        <textarea
          className="rex-input rex-ai-input"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Type request for assistant..."
          rows={5}
        />

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button type="button" className="rex-btn rex-btn-outline" onClick={() => setPrompt("")}>
            Clear
          </button>
          <button type="button" className="rex-btn rex-btn-primary" onClick={send} disabled={sending || !prompt.trim()}>
            {sending ? "Streaming..." : "Send"}
          </button>
        </div>

        <div className="rex-ai-stream" role="status">
          {streamText || "Assistant response will stream here..."}
        </div>
      </aside>
    </>
  );
}
