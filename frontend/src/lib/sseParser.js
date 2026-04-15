// Pure SSE frame parser — dependency-free so it can be unit-tested
// from Node without pulling in the rest of lib/sse.js's browser
// imports (fetch, ReadableStream, apiUrl). lib/sse.js imports
// parseSseFrame from here for the live-stream path; tests import it
// directly.
//
// Handles the SSE frame surface that real servers actually emit:
//   - `event: <name>` line (defaults to "message" when missing)
//   - one or more `data: <line>` lines (joined with \n per spec)
//   - `: <comment>` keep-alive lines (returned as null)
//   - unknown field lines (id:, retry:) silently ignored
//   - empty / whitespace-only frames (returned as null)
//   - non-JSON data (passed through as a raw string)

export function parseSseFrame(frame) {
  const trimmed = frame.trim();
  if (!trimmed) return null;
  let eventName = "message";
  const dataLines = [];
  for (const rawLine of trimmed.split("\n")) {
    // Strip any trailing CR that might have survived pre-normalization
    // so `line.startsWith(...)` comparisons work the same for CRLF
    // servers that leaked through unnormalized buffers.
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    if (line.startsWith("event:")) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      // SSE spec: strip a single leading space only
      dataLines.push(line.slice(5).replace(/^ /, ""));
    } else if (line.startsWith(":")) {
      // SSE comment — ignore
    }
    // All other lines (id:, retry:, unknown fields) are silently dropped.
  }
  if (dataLines.length === 0) return null;
  const dataStr = dataLines.join("\n");
  try {
    return { event: eventName, data: JSON.parse(dataStr) };
  } catch {
    return { event: eventName, data: dataStr };
  }
}
