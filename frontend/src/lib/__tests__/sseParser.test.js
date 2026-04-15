// Unit tests for the SSE frame parser used by lib/sse.js.
//
// Run: node src/lib/__tests__/sseParser.test.js
//
// We only test the pure `parseSseFrame` helper (exported as
// `__parseSseFrameForTests`). It's what every live chunk feeds through
// once split at a frame delimiter. These tests exercise the shapes
// real servers actually emit: single-line data, multi-line data,
// missing event: (should default to 'message'), keep-alive comments
// (should return null), trailing CR (should not leak into event name).

import assert from "node:assert";
import { parseSseFrame } from "../sseParser.js";

let passed = 0, failed = 0;
function test(name, fn) {
  try { fn(); console.log(`  ok  ${name}`); passed += 1; }
  catch (e) { console.error(`  FAIL  ${name}\n        ${e.message}`); failed += 1; }
}

test("parses a single-line event + JSON data", () => {
  const frame = `event: message.delta\ndata: {"delta":"Hello"}`;
  const parsed = parseSseFrame(frame);
  assert.deepStrictEqual(parsed, { event: "message.delta", data: { delta: "Hello" } });
});

test("parses multi-line data joined with newlines per SSE spec", () => {
  const frame = `event: message.completed\ndata: line one\ndata: line two`;
  const parsed = parseSseFrame(frame);
  assert.strictEqual(parsed.event, "message.completed");
  // data lines are joined then JSON-parsed — if JSON fails it falls
  // through to the raw string.
  assert.strictEqual(parsed.data, "line one\nline two");
});

test("defaults event to 'message' when event: line is missing", () => {
  const frame = `data: {"ping":"pong"}`;
  const parsed = parseSseFrame(frame);
  assert.strictEqual(parsed.event, "message");
  assert.deepStrictEqual(parsed.data, { ping: "pong" });
});

test("returns null for keep-alive comment frames (': keepalive')", () => {
  const frame = `: keepalive`;
  assert.strictEqual(parseSseFrame(frame), null);
});

test("returns null for empty/whitespace frames", () => {
  assert.strictEqual(parseSseFrame(""), null);
  assert.strictEqual(parseSseFrame("   "), null);
  assert.strictEqual(parseSseFrame("\n\n"), null);
});

test("handles data without leading space (data:{...})", () => {
  const frame = `event: action.suggestions\ndata:{"suggestions":[{"slug":"x"}]}`;
  const parsed = parseSseFrame(frame);
  assert.strictEqual(parsed.event, "action.suggestions");
  assert.deepStrictEqual(parsed.data, { suggestions: [{ slug: "x" }] });
});

test("strips only one leading space from data line (preserves intentional indent)", () => {
  const frame = `event: message.delta\ndata:  leading-space-token`;
  const parsed = parseSseFrame(frame);
  // " leading-space-token" — first space stripped, JSON parse fails,
  // falls through to raw string.
  assert.strictEqual(parsed.data, " leading-space-token");
});

test("silently ignores unknown field lines like id: 42", () => {
  const frame = `id: 42\nevent: message.started\ndata: {"x":1}`;
  const parsed = parseSseFrame(frame);
  assert.strictEqual(parsed.event, "message.started");
});

test("falls through to raw string when data is not JSON", () => {
  const frame = `event: error\ndata: something broke`;
  const parsed = parseSseFrame(frame);
  assert.strictEqual(parsed.event, "error");
  assert.strictEqual(parsed.data, "something broke");
});

test("handles message.delta with accumulated and delta fields", () => {
  const frame = `event: message.delta\ndata: {"delta":" world","accumulated":"Hello world"}`;
  const parsed = parseSseFrame(frame);
  assert.strictEqual(parsed.event, "message.delta");
  assert.strictEqual(parsed.data.delta, " world");
  assert.strictEqual(parsed.data.accumulated, "Hello world");
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
