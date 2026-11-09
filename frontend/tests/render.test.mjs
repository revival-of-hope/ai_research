import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createMemoryRouter, MemoryRouter, RouterProvider } from "react-router-dom";
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
const { ResearchControls } = await import(await sourceModule("../src/components/research/research-controls.tsx"));
const { RunActivity } = await import(await sourceModule("../src/components/research/run-activity.tsx"));
const { MessageList } = await import(await sourceModule("../src/components/research/message-list.tsx"));
const { ComparisonPage } = await import(await sourceModule("../src/pages/workspace/comparison.tsx"));
const { ComparisonSourceStep } = await import(await sourceModule("../src/components/comparison-source-step.tsx"));
const { ComparisonReview } = await import(await sourceModule("../src/components/comparison-review.tsx"));
const { WorkspaceNavigation } = await import(await sourceModule("../src/components/shell/workspace-navigation.tsx"));
const { WorkspaceBreadcrumb } = await import(await sourceModule("../src/components/shell/workspace-breadcrumb.tsx"));
const { shouldBlockUnsavedChanges } = await import(await sourceModule("../src/lib/use-unsaved-changes.ts"));
const { AuthProvider } = await import(await sourceModule("../src/lib/auth.tsx"));
const { ResearchTaskNavigation } = await import(await sourceModule("../src/components/research/research-task-navigation.tsx"));
const { WorkspaceHistory } = await import(await sourceModule("../src/components/shell/workspace-history.tsx"));
const { ResearchSidebar } = await import(await sourceModule("../src/components/research/research-sidebar.tsx"));
const callbacks = Object.fromEntries(["onChange", "onToggleDocument", "onToggleWeb", "onModeChange", "onMaxAgentsChange", "onMaxDepthChange", "onSelectProvider", "onConfigureProviders", "onOpenSources", "onSubmit", "onStop"].map((name) => [name, () => {}]));
const composer = { value: "Explain this", documents: [], providers: [], selectedDocs: [], webSearch: true, maxAgents: 3, maxDepth: 1, busy: false, ...callbacks };

test("sidebar research controls keep expanded deep settings and hide them in quick mode", () => {
  const controls = { maxAgents: 4, maxDepth: 2, disabled: false, ...callbacks };
  const deep = renderToStaticMarkup(createElement(ResearchControls, { ...controls, mode: "deep" }));
  assert.match(deep, /<fieldset[^>]*aria-label="深度研究设置"/);
  assert.match(deep, /aria-label="最大智能体数"/);
  assert.match(deep, /aria-label="子智能体最大派生层级"/);
  assert.match(deep, /<option value="4" selected="">4 个/);
  assert.match(deep, /<option value="2" selected="">2 层/);
  assert.doesNotMatch(deep, /模型推理|推理强度/);
  const quick = renderToStaticMarkup(createElement(ResearchControls, { ...controls, mode: "quick" }));
  assert.match(quick, /由所选模型直接回答/);
  assert.match(quick, /联网搜索/);
  assert.match(quick, /资料/);
  assert.doesNotMatch(quick, /深度研究设置|最大智能体数|子智能体最大派生层级|模型推理|推理强度/);
  for (const mode of ["deep", "quick"]) {
    const input = renderToStaticMarkup(createElement(ResearchComposer, { ...composer, mode }));
    assert.doesNotMatch(input, /回答模式|深度研究设置|最大智能体数|子智能体最大派生层级/);
    assert.match(input, /<textarea/);
    assert.match(input, /联网搜索/);
    assert.match(input, /资料/);
  }
});

test("sidebar mode and collaboration controls lock while the workspace is unavailable", () => {
  const locked = renderToStaticMarkup(createElement(ResearchControls, { mode: "deep", maxAgents: 3, maxDepth: 1, disabled: true, ...callbacks }));
  assert.equal((locked.match(/<button[^>]*disabled=""/g) || []).length, 2);
  assert.match(locked, /<fieldset disabled="" aria-label="深度研究设置"/);
  assert.equal((locked.match(/aria-pressed="true"/g) || []).length, 1);
  assert.equal((locked.match(/aria-pressed="false"/g) || []).length, 1);
});

test("both workspaces use matching research and comparison navigation actions", () => {
  for (const pathname of ["/research", "/research/comparisons"]) {
    const html = renderToStaticMarkup(createElement(MemoryRouter, { initialEntries: [pathname] },
      createElement(WorkspaceNavigation, { isAdmin: true })));
    assert.equal((html.match(/aria-label="工作区功能导航"/g) || []).length, 1);
    assert.equal((html.match(/aria-label="工作区常用功能"/g) || []).length, 1);
    assert.match(html, /href="\/research"[^>]*>.*?新建研究/);
    assert.match(html, /href="\/research\/comparisons"[^>]*>.*?实验核验/);
    for (const [path, label] of [
      ["/sources", "资料库"],
      ["/settings", "模型预设"],
      ["/usage", "Token 用量"],
      ["/guide", "使用说明"],
      ["/admin", "用户管理"],
    ]) {
      assert.match(html, new RegExp(`href="${path}"[^>]*>.*?${label}`));
    }
    assert.equal((html.match(/h-11 w-full items-center/g) || []).length, 2);
  }
});

test("shared breadcrumb keeps page hierarchy without duplicating page headers", () => {
  for (const page of ["研究问答", "实验核验", "Token 用量"]) {
    const html = renderToStaticMarkup(createElement(MemoryRouter, null,
      createElement(WorkspaceBreadcrumb, { current: page })));
    assert.equal((html.match(/aria-label="面包屑"/g) || []).length, 1);
    assert.match(html, /工作台/);
    assert.match(html, new RegExp(`aria-current="page"[^>]*>${page}`));
  }
});

test("research sidebar keeps mode controls and history within common navigation", () => {
  const callbacks = { onNew() {}, onOpen() {}, async onRename() {}, async onDelete() {},
    onCloseMobile() {}, onOpenSettings() {}, onLogout() {}, onModeChange() {},
    onMaxAgentsChange() {}, onMaxDepthChange() {} };
  const props = { conversations: [], busy: false, loading: false, mobileOpen: false,
    disabled: false, mode: "deep", maxAgents: 3, maxDepth: 1, email: "test@example.com", ...callbacks };
  const html = renderToStaticMarkup(createElement(MemoryRouter, { initialEntries: ["/research"] },
    createElement(ResearchSidebar, props)));
  assert.equal((html.match(/aria-label="工作区功能导航"/g) || []).length, 1);
  assert.match(html, /实验核验/);
  assert.match(html, /回答模式/);
  assert.match(html, /最近研究/);
  assert.match(html, /搜索历史记录/);
  assert.match(html, /账户菜单/);
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

test("UC08 page presents the upload and saved-results workflow", () => {
  const router = createMemoryRouter([{ path: "*", element: createElement(AuthProvider, null, createElement(ComparisonPage)) }]);
  const markup = renderToStaticMarkup(createElement(RouterProvider, { router }));
  assert.match(markup, /添加论文/);
  assert.match(markup, /本地实验结果/);
  assert.match(markup, /上传论文/);
  assert.match(markup, /上传实验摘要/);
  assert.match(markup, /没有文件？直接粘贴结果/);
  assert.doesNotMatch(markup, /<textarea/);
  assert.match(markup, /要核对的指标和实验/);
  assert.match(markup, /已保存的核验记录/);
  assert.match(markup, /我的资料/);
  assert.match(markup, /发送至所选模型/);
});

test("UC08 result upload displays saved documents and an example summary", () => {
  const doc = { id: 15, filename: "local-metrics.md", status: "ready", size_bytes: 180 };
  const props = {
    kind: "run", documents: [doc], selectedId: "15",
    onSelect() {}, async onUpload() {},
    uploading: false, disabled: false, error: "",
  };
  const markup = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(ComparisonSourceStep, props)));
  assert.match(markup, /local-metrics.md/);
  assert.match(markup, /已选择：/);
  assert.match(markup, /type="file"/);
  assert.match(markup, /\.csv/);
  assert.match(markup, /没有文件？直接粘贴结果/);
  assert.doesNotMatch(markup, /实验摘要文件名/);
});

test("UC08 evidence review presents both selected sources, a field table and original chunk access", () => {
  const comparison = {
    id: 8, metric: "top-1 accuracy", paper_name: "paper.pdf", run_name: "run.md",
    paper_document_id: 1, run_document_id: 2, status: "pending",
    fields: [
      { key: "dataset", label: "数据集", paper: { value: "ImageNet", excerpt: "Dataset ImageNet", chunk_id: 4 },
        run: { value: "ImageNet", excerpt: "Dataset ImageNet", chunk_id: 6 },
        status: "aligned", review_status: "pending", note: "" },
      { key: "split", label: "数据划分", paper: { value: "validation", excerpt: "split validation", chunk_id: 4 },
        run: { value: "test", excerpt: "split test", chunk_id: 6 },
        status: "mismatch", review_status: "unresolved", note: "不同划分" },
    ],
  };
  const markup = renderToStaticMarkup(createElement(MemoryRouter, null,
    createElement(ComparisonReview, { comparison, onBack() {}, onEdit() {}, onReview() {}, onConfirm() {}, busy: false })));
  assert.match(markup, /本次使用的资料/);
  assert.match(markup, /paper.pdf/);
  assert.match(markup, /run.md/);
  assert.match(markup, /核对实验条件和结果/);
  assert.match(markup, /数据划分/);
  assert.match(markup, /实验条件存在差异或尚未核实/);
  assert.match(markup, /查看原文/);
  assert.match(markup, /修改引用的原文/);
  assert.match(markup, /原文摘录/);
  assert.match(markup, /标记未解决/);
  assert.match(markup, /确认并保存摘要/);
  assert.match(markup, /disabled=""/);
});


test("research task entry connects question answering, research and experiment verification", () => {
  for (const task of ["quick", "deep", "comparison"]) {
    const markup = renderToStaticMarkup(createElement(MemoryRouter, null,
      createElement(ResearchTaskNavigation, { task })));
    assert.match(markup, /aria-label="选择研究任务"/);
    assert.match(markup, /快速问答/);
    assert.match(markup, /深度研究/);
    assert.match(markup, /实验核验/);
    assert.match(markup, /href="\/research\/comparisons"/);
    assert.match(markup, /href="\/research\?mode=quick"/);
    assert.match(markup, /href="\/research\?mode=deep"/);
    assert.equal((markup.match(/aria-current="page"/g) || []).length, 1);
  }
});

test("shared history preserves experiment and research records with distinct accessible icons", () => {
  const props = { conversations: [
    { id: 1, title: "研究历史", kind: "research" },
    { id: 2, title: "论文和实验", kind: "comparison", comparison_id: 7 },
  ], activeId: 2, busy: false, loading: false, onOpen() {}, async onRename() {}, async onDelete() {} };
  const markup = renderToStaticMarkup(createElement(WorkspaceHistory, props));
  assert.match(markup, /研究历史/);
  assert.match(markup, /论文和实验/);
  assert.match(markup, /aria-label="实验核验"/);
  assert.match(markup, /aria-current="page"/);
  assert.match(markup, /搜索历史记录/);
  assert.match(markup, /重命名 论文和实验/);
  assert.match(markup, /删除 论文和实验/);
});


test("unsaved experiment changes block shared history, query changes and browser back until confirmed", async (context) => {
  for (const destination of ["/research?conversation=5", "/research/comparisons?comparison=2", -1]) {
    let dirty = true;
    const router = createMemoryRouter([{ path: "*", element: null }], {
      initialEntries: ["/research", "/research/comparisons?comparison=1"],
      initialIndex: 1,
    });
    context.after(() => router.dispose());
    router.getBlocker("review", ({ currentLocation, nextLocation }) =>
      shouldBlockUnsavedChanges(dirty, currentLocation, nextLocation));
    await router.navigate(destination);
    assert.equal(router.state.blockers.get("review").state, "blocked");
    assert.equal(router.state.location.pathname, "/research/comparisons");
    assert.equal(router.state.location.search, "?comparison=1");
    router.state.blockers.get("review").reset();
    assert.equal(router.state.location.search, "?comparison=1");
    await router.navigate(destination);
    const changed = new Promise((resolve) => {
      const unsubscribe = router.subscribe((state) => {
        if (state.location.pathname + state.location.search !== "/research/comparisons?comparison=1") {
          unsubscribe();
          resolve();
        }
      });
    });
    router.state.blockers.get("review").proceed();
    await changed;
    assert.notEqual(router.state.location.pathname + router.state.location.search, "/research/comparisons?comparison=1");
    dirty = false;
    await router.navigate("/research/comparisons?comparison=3");
    assert.equal(router.state.location.search, "?comparison=3");
  }
});
