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
const { isDeepResearch } = await import(await moduleUrl("../src/lib/message-mode.ts"));
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

test("fetch failures retain their diagnostic cause and show an actionable connection message without retrying", async (context) => {
  const original = globalThis.fetch;
  context.after(() => { globalThis.fetch = original; });
  const failure = new TypeError("Failed to fetch");
  let requests = 0;
  globalThis.fetch = async () => { requests += 1; throw failure; };
  for (const send of [() => api("/account/providers", { method: "POST", body: "{}" }), () => streamSse("/research/ask/stream", {}, () => {})]) {
    await assert.rejects(send(), (reason) => {
      assert.equal(reason.name, "ApiConnectionError");
      assert.equal(reason.phase, "connect");
      assert.equal(reason.cause, failure);
      assert.match(reason.message, /连接应用服务失败/);
      assert.match(reason.message, /检查网络或服务状态后重试/);
      assert.doesNotMatch(reason.message, /Failed to fetch/);
      return true;
    });
  }
  assert.equal(requests, 2, "submissions are never retried automatically");
});

test("cancellation during fetch stays AbortError for both normal and streaming requests", async (context) => {
  const original = globalThis.fetch;
  context.after(() => { globalThis.fetch = original; });
  const cancellation = new DOMException("User stopped", "AbortError");
  globalThis.fetch = async () => { throw cancellation; };
  await assert.rejects(api("/research/conversations"), (reason) => reason === cancellation);
  await assert.rejects(streamSse("/research/ask/stream", {}, () => {}), (reason) => reason === cancellation);
});

test("a response body disconnect tells the user to check whether their submitted operation succeeded", async (context) => {
  const original = globalThis.fetch;
  context.after(() => { globalThis.fetch = original; });
  const failure = new TypeError("connection terminated");
  globalThis.fetch = async () => new Response(new ReadableStream({ start(controller) { controller.error(failure); } }));
  await assert.rejects(api("/account/providers", { method: "POST", body: "{}" }), (reason) => {
    assert.equal(reason.phase, "response");
    assert.equal(reason.cause, failure);
    assert.match(reason.message, /提交操作可能已经执行/);
    return true;
  });
});

test("stream reader disconnect preserves partial content and releases the reader with a recovery message", async (context) => {
  const original = globalThis.fetch;
  context.after(() => { globalThis.fetch = original; });
  const failure = new TypeError("network error");
  let sent = false;
  const body = new ReadableStream({ pull(controller) {
    if (!sent) { sent = true; controller.enqueue(new TextEncoder().encode('event: content\ndata: {"delta":"Partial answer"}\n\n')); }
    else controller.error(failure);
  } });
  globalThis.fetch = async () => new Response(body);
  let text = "";
  await assert.rejects(streamSse("/research/ask/stream", {}, (event) => { text += event.data.delta || ""; }), (reason) => {
    assert.equal(reason.phase, "stream");
    assert.equal(reason.cause, failure);
    assert.match(reason.message, /回答连接中断/);
    assert.match(reason.message, /先复制已有内容/);
    return true;
  });
  assert.equal(text, "Partial answer");
  assert.equal(body.locked, false);
});

test("an incomplete SSE event gives recovery guidance instead of a JSON parsing error", async (context) => {
  const original = globalThis.fetch;
  context.after(() => { globalThis.fetch = original; });
  globalThis.fetch = async () => new Response('event: content\ndata: {"delta":"partial"');
  await assert.rejects(streamSse("/research/ask/stream", {}, () => {}), (reason) => {
    assert.match(reason.message, /回答数据不完整或格式异常/);
    assert.match(reason.message, /先复制已有内容/);
    assert.equal(reason.cause.name, "SyntaxError");
    return true;
  });
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

test("history uses run modes for existing replies and interrupted placeholders without changing legacy messages", () => {
  const restored = restoreResearchHistory([
    { role: "user", content: "Quick", run_id: "quick" },
    { role: "assistant", content: "Direct answer", run_id: "quick" },
    { role: "user", content: "Quick failure", run_id: "failure" },
    { role: "assistant", content: "Explicit mode", run_id: "old", mode: "quick" },
    { role: "assistant", content: "Legacy" },
  ], [{ id: "quick", mode: "quick", status: "completed" }, { id: "failure", mode: "quick", status: "failed", error: "Disconnected" }, { id: "old", mode: "deep" }]);
  assert.equal(restored[1].mode, "quick");
  assert.equal(restored[3].mode, "quick");
  assert.equal(restored[3].error, "Disconnected");
  assert.equal(restored[4].mode, "quick");
  assert.equal(restored[5].mode, undefined);
  assert.equal(isDeepResearch({ mode: "quick", events: [{ type: "agent" }] }), false);
  assert.equal(isDeepResearch({ events: [{ type: "plan" }] }), true);
  assert.equal(isDeepResearch({ events: [{ type: "search" }] }), false);
  assert.equal(isDeepResearch({ content: "Legacy" }), false);
});

test("quick stream retains its mode and search results while suppressing research plan and agent activity", async (context) => {
  const original = globalThis.fetch;
  context.after(() => { globalThis.fetch = original; });
  const payload = { mode: "quick", question: "Explain this", provider_id: 1, conversation_id: null, document_ids: [], web_search: true };
  globalThis.fetch = async (url, options) => {
    assert.equal(url, "/api/research/ask/stream");
    assert.deepEqual(JSON.parse(options.body), payload);
    return new Response([
      ["meta", { conversation_id: 9, mode: "quick" }],
      ["plan", { steps: [{ id: "ignored", title: "Unexpected legacy event" }] }],
      ["agent", { id: "ignored" }],
      ["progress", { message: "Ignored research progress" }],
      ["search", { status: "searching" }],
      ["content", { delta: "Direct answer" }],
      ["done", { conversation_id: 9, mode: "quick", saved: true }],
    ].map(([type, data]) => `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`).join(""));
  };
  const received = { meta: undefined, content: "", events: [], done: undefined };
  await runResearchStream(payload, { onMeta: (id, mode) => { received.meta = { id, mode }; }, onDelta: (delta) => { received.content += delta; }, onEvent: (event) => received.events.push(event), onDone: (done) => { received.done = done; } }, new AbortController().signal);
  assert.deepEqual(received.meta, { id: 9, mode: "quick" });
  assert.equal(received.content, "Direct answer");
  assert.deepEqual(received.events.map((event) => event.type), ["search"]);
  assert.equal(received.done.mode, "quick");
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

test("a saved done event cancels its reader before a trailing network error can be read", async (context) => {
  const original = globalThis.fetch;
  context.after(() => { globalThis.fetch = original; });
  let reads = 0;
  let cancelled = 0;
  const body = new ReadableStream({
    pull(controller) {
      reads += 1;
      if (reads === 1) controller.enqueue(new TextEncoder().encode('event: done\ndata: {"conversation_id":11,"saved":true,"mode":"quick"}\n\n'));
      else controller.error(new TypeError("trailing network failure"));
    },
    cancel() { cancelled += 1; },
  }, { highWaterMark: 0 });
  globalThis.fetch = async () => new Response(body);
  const completions = [];
  await runResearchStream({ mode: "quick" }, { onMeta() {}, onDelta() {}, onEvent() {}, onDone: (done) => completions.push(done) }, new AbortController().signal);
  assert.equal(reads, 1);
  assert.equal(cancelled, 1);
  assert.equal(body.locked, false);
  assert.equal(completions.length, 1);
  assert.equal(completions[0].saved, true);
});

test("a done event completes without waiting for a stream that never sends EOF", async (context) => {
  const original = globalThis.fetch;
  context.after(() => { globalThis.fetch = original; });
  let controller;
  let reads = 0;
  let cancelled = 0;
  const body = new ReadableStream({
    start(streamController) { controller = streamController; },
    pull(streamController) {
      reads += 1;
      if (reads === 1) streamController.enqueue(new TextEncoder().encode('event: done\ndata: {"conversation_id":12,"saved":true}\n\n'));
      // The server keeps the connection open and sends no more data.
    },
    cancel() { cancelled += 1; },
  }, { highWaterMark: 0 });
  globalThis.fetch = async () => new Response(body);
  let completed = false;
  const running = runResearchStream({ mode: "deep" }, { onMeta() {}, onDelta() {}, onEvent() {}, onDone() { completed = true; } }, new AbortController().signal);
  let timeout;
  try {
    await Promise.race([running, new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error("Client waited for EOF after done")), 200); })]);
  } finally {
    clearTimeout(timeout);
    if (body.locked) controller.error(new Error("test cleanup"));
    await running.catch(() => undefined);
  }
  assert.equal(completed, true);
  assert.equal(reads, 1);
  assert.equal(cancelled, 1);
  assert.equal(body.locked, false);
});

test("callback exceptions remain failures and stop readers even for done callbacks", async (context) => {
  const original = globalThis.fetch;
  context.after(() => { globalThis.fetch = original; });
  for (const event of ["content", "done"]) {
    let cancelled = false;
    const body = new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode(`event: ${event}\ndata: {"conversation_id":13,"delta":"answer","saved":true}\n\n`)); }, cancel() { cancelled = true; } });
    globalThis.fetch = async () => new Response(body);
    const failure = new Error(`${event} callback failed`);
    const callbacks = { onMeta() {}, onEvent() {}, onDelta() { if (event === "content") throw failure; }, onDone() { if (event === "done") throw failure; } };
    await assert.rejects(runResearchStream({ mode: "quick" }, callbacks, new AbortController().signal), (reason) => reason === failure);
    assert.equal(cancelled, true);
    assert.equal(body.locked, false);
  }
});
