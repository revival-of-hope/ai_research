import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
const modules = new Map();
async function sourceModule(relative) {
  if (modules.has(relative)) return modules.get(relative);
  let source = await readFile(new URL(relative, import.meta.url), "utf8");
  for (const alias of new Set([...source.matchAll(/from\s+["'](@\/[^"']+)["']/g)].map((match) => match[1]))) {
    let dependency;
    for (const extension of [".ts", ".tsx"]) {
      try { dependency = await sourceModule(`../src/${alias.slice(2)}${extension}`); break; }
      catch (reason) { if (reason.code !== "ENOENT") throw reason; }
    }
    if (!dependency) throw new Error(`Cannot resolve ${alias}`);
    source = source.replaceAll(`"${alias}"`, JSON.stringify(dependency));
  }
  let { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } });
  outputText = outputText.replace(/from\s+["']([^"']+)["']/g, (full, name) => name.startsWith("data:") ? full : `from ${JSON.stringify(pathToFileURL(require.resolve(name, { paths: [fileURLToPath(new URL("..", import.meta.url))] })).href)}`);
  const result = `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`;
  modules.set(relative, result);
  return result;
}

const { ResearchComposer } = await import(await sourceModule("../src/components/research/research-composer.tsx"));
const { RunActivity } = await import(await sourceModule("../src/components/research/run-activity.tsx"));
const { MessageList } = await import(await sourceModule("../src/components/research/message-list.tsx"));
const callbacks = Object.fromEntries(["onChange", "onToggleDocument", "onToggleWeb", "onModeChange", "onMaxAgentsChange", "onMaxDepthChange", "onSelectProvider", "onConfigureProviders", "onOpenSources", "onSubmit", "onStop"].map((name) => [name, () => {}]));
const composer = { value: "Explain this", documents: [], providers: [], selectedDocs: [], webSearch: true, maxAgents: 3, maxDepth: 1, busy: false, ...callbacks };

test("deep research settings stay expanded above the composer while quick mode has no research controls", () => {
  const deep = renderToStaticMarkup(createElement(ResearchComposer, { ...composer, mode: "deep" }));
  assert.match(deep, /<fieldset[^>]*aria-label="深度研究设置"/);
  assert.match(deep, /aria-label="最大智能体数"/);
  assert.match(deep, /aria-label="子智能体最大派生层级"/);
  assert.ok(deep.indexOf("深度研究设置") < deep.indexOf("<textarea"));
  assert.doesNotMatch(deep, /模型推理|推理强度/);
  const quick = renderToStaticMarkup(createElement(ResearchComposer, { ...composer, mode: "quick" }));
  assert.match(quick, /由所选模型直接回答/);
  assert.match(quick, /联网搜索/);
  assert.match(quick, /资料/);
  assert.doesNotMatch(quick, /深度研究设置|最大智能体数|子智能体最大派生层级|模型推理|推理强度/);
});

test("quick replies never render research cards even with historical research events", () => {
  const message = { role: "assistant", content: "", mode: "quick", status: "running", events: [{ type: "plan", data: { steps: [{ id: "1", title: "Historical research plan" }] } }] };
  assert.equal(renderToStaticMarkup(createElement(RunActivity, { message, active: true })), "");
  const markup = renderToStaticMarkup(createElement(MessageList, { messages: [message], busy: true, onEditQuestion() {} }));
  assert.match(markup, /正在生成回答/);
  assert.doesNotMatch(markup, /研究进行中|研究运行记录|研究计划|协作智能体树|Historical research plan/);
});

test("quick failure and cancellation keep errors and partial answers without research placeholders", () => {
  for (const status of ["failed", "cancelled"]) {
    const markup = renderToStaticMarkup(createElement(MessageList, { messages: [{ role: "assistant", mode: "quick", content: "Partial answer", status, error: status === "failed" ? "连接应用服务失败" : undefined }], busy: false, onEditQuestion() {} }));
    assert.match(markup, /Partial answer/);
    assert.match(markup, /编辑问题后重试/);
    assert.match(markup, status === "failed" ? /连接应用服务失败/ : /已停止回答/);
    assert.doesNotMatch(markup, /研究运行记录|查看研究过程|这次研究/);
  }
});

test("deep replies still display collaboration while quick search has a small status only", () => {
  const deep = renderToStaticMarkup(createElement(RunActivity, { message: { mode: "deep", status: "running", events: [] }, active: true }));
  assert.match(deep, /研究进行中/);
  const quick = renderToStaticMarkup(createElement(MessageList, { messages: [{ role: "assistant", mode: "quick", content: "", status: "running", events: [{ type: "search", data: { status: "searching" } }] }], busy: true, onEditQuestion() {} }));
  assert.match(quick, /正在使用服务商联网搜索/);
  assert.doesNotMatch(quick, /研究进行中|研究计划|研究运行记录/);
});
