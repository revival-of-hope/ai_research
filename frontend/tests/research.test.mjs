import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

async function moduleUrl(relative, replacements = {}) {
  let source = await readFile(new URL(relative, import.meta.url), "utf8");
  for (const [from, to] of Object.entries(replacements)) source = source.replaceAll(from, to);
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
  return `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`;
}
const apiUrl = await moduleUrl("../src/lib/api.ts");
const { streamSse, api } = await import(apiUrl);
const { restoreResearchHistory } = await import(await moduleUrl("../src/lib/research-history.ts"));
const { runResearchStream } = await import(await moduleUrl("../src/lib/research-stream.ts", { '"@/lib/api"': JSON.stringify(apiUrl) }));

test("SSE preserves Unicode and CRLF across arbitrary byte boundaries, multiline data and final events", async (context) => {
  const original = globalThis.fetch;
  context.after(() => { globalThis.fetch = original; });
  const bytes = new TextEncoder().encode(': ping\r\n\r\nevent: plan\r\ndata: {"steps":\r\ndata: [{"id":"r1","title":"研究计划"}]}\r\n\r\nevent: content\r\ndata: {"delta":"你好 🌏"}\r\n\r\nevent: done\r\ndata: {"saved":true}');
  globalThis.fetch = async () => new Response(new ReadableStream({ start(controller) { for (const byte of bytes) controller.enqueue(Uint8Array.of(byte)); controller.close(); } }));
  const received = [];
  await streamSse("/research/ask/stream", {}, (event) => received.push(event));
  assert.deepEqual(received.map((event) => event.type), ["plan", "content", "done"]);
  assert.equal(received[0].data.steps[0].title, "研究计划");
  assert.equal(received[1].data.delta, "你好 🌏");
  assert.equal(received[2].data.saved, true);
});

test("SSE forwards cancellation to fetch and releases its reader after abort", async (context) => {
  const original = globalThis.fetch;
  context.after(() => { globalThis.fetch = original; });
  const abort = new AbortController();
  let body;
  globalThis.fetch = async (_url, options) => {
    assert.equal(options.signal, abort.signal);
    body = new ReadableStream({ start(controller) {
      controller.enqueue(new TextEncoder().encode('event: content\ndata: {"delta":"partial"}\n\n'));
      options.signal.addEventListener("abort", () => controller.error(new DOMException("Aborted", "AbortError")), { once: true });
    } });
    return new Response(body);
  };
  await assert.rejects(streamSse("/research/ask/stream", {}, () => abort.abort(), abort.signal), { name: "AbortError" });
  assert.equal(body.locked, false);
});

test("validation errors remain readable instead of rendering an object", async (context) => {
  const original = globalThis.fetch;
  context.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: [{ msg: "Question is too short" }] }), { status: 422 });
  await assert.rejects(api("/research/conversations"), { message: "Question is too short", status: 422 });
});

test("safe service errors stay specific for model discovery and research streams", async (context) => {
  const original = globalThis.fetch;
  context.after(() => { globalThis.fetch = original; });
  const message = "服务商拒绝请求（401）：请检查 API Key 与模型权限。";
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: message }), { status: 502 });
  await assert.rejects(api("/account/provider-models", { method: "POST", body: "{}" }), { message, status: 502 });
  globalThis.fetch = async () => new Response(`event: error\ndata: ${JSON.stringify({ message })}\n\n`);
  await assert.rejects(runResearchStream({}, { onMeta() {}, onDelta() {}, onEvent() {}, onDone() { assert.fail("an errored stream cannot complete"); } }, new AbortController().signal), { message });
});

test("history restores failed and cancelled activity beside the correct question without duplicating reports", () => {
  const sources = [{ label: "Doc 1", title: "notes.md" }];
  const events = [{ type: "agent", data: { id: "child", parent_id: "r1", name: "证据核验", status: "failed" } }];
  const history = [
    { id: 1, role: "user", content: "success", run_id: "ok" },
    { id: 2, role: "assistant", content: "report", run_id: "ok", sources },
    { id: 3, role: "user", content: "failure", run_id: "failed" },
    { id: 4, role: "user", content: "stop", run_id: "cancelled" },
  ];
  const runs = [
    { id: "cancelled", status: "cancelled", sources: [], events: [], usage: { total_tokens: 5 } },
    { id: "failed", status: "failed", error: "Upstream unavailable", sources, events, usage: { total_tokens: 30 } },
    { id: "ok", status: "completed" },
  ];
  const restored = restoreResearchHistory(history, runs);
  assert.deepEqual(restored.map((message) => message.role), ["user", "assistant", "user", "assistant", "user", "assistant"]);
  assert.equal(restored.filter((message) => message.run_id === "ok" && message.role === "assistant").length, 1);
  assert.equal(restored[3].error, "Upstream unavailable");
  assert.deepEqual(restored[3].sources, sources);
  assert.deepEqual(restored[3].events, events);
  assert.equal(restored[5].status, "cancelled");
  assert.equal(restored[5].total_tokens, 5);
});

test("an unattached running record remains running and legacy messages remain readable", () => {
  const restored = restoreResearchHistory([
    { id: 1, role: "user", content: "legacy" },
    { id: 2, role: "assistant", content: "old report" },
    { id: 3, role: "user", content: "live", run_id: "live" },
  ], [{ id: "live", status: "running", events: [], sources: [] }]);
  assert.equal(restored[1].content, "old report");
  assert.deepEqual(restored[1].sources, []);
  assert.equal(restored[3].status, "running");
  assert.equal(restored[3].content, "");
});

test("research protocol delivers public activity and report sources without private reasoning", async (context) => {
  const original = globalThis.fetch;
  context.after(() => { globalThis.fetch = original; });
  const wire = [
    ["meta", { conversation_id: 12 }],
    ["thinking", { delta: "PRIVATE_MODEL_REASONING" }],
    ["plan", { steps: [{ id: "r1", title: "Check evidence" }] }],
    ["agent", { id: "r1", parent_id: null, name: "Researcher", status: "running" }],
    ["content", { delta: "Report [Web 1]" }],
    ["done", { conversation_id: 12, saved: true, sources: [{ label: "Web 1", title: "Evidence", url: "https://example.org" }], usage: { total_tokens: 42 } }],
  ].map(([type, data]) => `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`).join("");
  globalThis.fetch = async () => new Response(wire);
  const received = { ids: [], text: "", events: [], done: null };
  await runResearchStream({}, {
    onMeta: (id) => received.ids.push(id), onDelta: (delta) => { received.text += delta; },
    onEvent: (event) => received.events.push(event), onDone: (done) => { received.done = done; },
  }, new AbortController().signal);
  assert.deepEqual(received.ids, [12]);
  assert.equal(received.text, "Report [Web 1]");
  assert.deepEqual(received.events.map((event) => event.type), ["plan", "agent"]);
  assert.equal(received.done.sources[0].label, "Web 1");
  assert.equal(JSON.stringify(received).includes("PRIVATE_MODEL_REASONING"), false);
});

test("research never treats an incomplete stream as a saved result", async (context) => {
  const original = globalThis.fetch;
  context.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async () => new Response('event: content\ndata: {"delta":"partial"}\n\n');
  const callbacks = { onMeta() {}, onDelta() {}, onEvent() {}, onDone() { assert.fail("an incomplete stream cannot complete"); } };
  await assert.rejects(runResearchStream({}, callbacks, new AbortController().signal), /连接已中断/);
  const abort = new AbortController();
  await assert.rejects(runResearchStream({}, { ...callbacks, onDelta() { abort.abort(); } }, abort.signal), { name: "AbortError" });
});
