import assert from "node:assert";
import { inferApiBaseFromHost } from "../apiBase.js";

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`  ok  ${name}`);
    passed += 1;
  } catch (e) {
    console.error(`  FAIL  ${name}\n        ${e.message}`);
    failed += 1;
  }
}

test("maps rex production hosts to Railway production API", () => {
  assert.strictEqual(
    inferApiBaseFromHost("www.rex.papadrew.com"),
    "https://rex-os-api-production.up.railway.app",
  );
  assert.strictEqual(
    inferApiBaseFromHost("rex-os.vercel.app"),
    "https://rex-os-api-production.up.railway.app",
  );
  assert.strictEqual(
    inferApiBaseFromHost("rex-os-git-fix-foo-bar.vercel.app"),
    "https://rex-os-api-production.up.railway.app",
  );
});

test("maps demo hosts to Railway demo API", () => {
  assert.strictEqual(
    inferApiBaseFromHost("rex-os-demo.vercel.app"),
    "https://rex-os-demo.up.railway.app",
  );
  assert.strictEqual(
    inferApiBaseFromHost("rex-os-demo-git-phase-e-abc.vercel.app"),
    "https://rex-os-demo.up.railway.app",
  );
});

test("falls back to empty string for unknown hosts", () => {
  assert.strictEqual(inferApiBaseFromHost("localhost"), "");
  assert.strictEqual(inferApiBaseFromHost("example.com"), "");
  assert.strictEqual(inferApiBaseFromHost(""), "");
});

console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
