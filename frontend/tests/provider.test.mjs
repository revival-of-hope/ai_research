import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/lib/provider-form.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } });
const { providerForm, selectProviderTemplate, providerModelsRequest, providerSaveRequest, providerEndpoint } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
const catalog = [
  { id: "openai", name: "OpenAI", base_url: "https://api.openai.com/v1", models: ["openai-recommended"] },
  { id: "deepseek", name: "DeepSeek", base_url: "https://deepseek.example/v1", models: ["deepseek-chat"] },
  { id: "qwen", name: "Qwen", base_url: "https://qwen.example/api/v2", models: ["qwen-recommended"] },
  { id: "anthropic", name: "Claude", base_url: "", models: ["claude-recommended"] },
  { id: "custom", name: "自定义", base_url: "", models: [] },
];

test("each provider selection applies its catalog URL and recommended model", () => {
  let form = providerForm();
  for (const entry of catalog) {
    form = selectProviderTemplate(form, entry, catalog);
    assert.equal(form.providerType, entry.id);
    assert.equal(form.baseUrl, entry.base_url);
    assert.equal(form.model, entry.models[0] ?? "");
    assert.equal(form.name, entry.id === "custom" ? "" : entry.name);
  }
});

test("provider selection preserves a user-written preset name", () => {
  const form = { ...providerForm(), name: "Research team" };
  assert.equal(selectProviderTemplate(form, catalog[1], catalog).name, "Research team");
});

test("editing saved and legacy presets preserves custom URLs and model IDs without reading secrets", () => {
  const saved = { id: 42, name: "Private gateway", base_url: "https://gateway.example/v8", model: "custom-deployment", provider_type: "qwen", has_api_key: true };
  assert.deepEqual(providerForm(saved), { name: "Private gateway", baseUrl: "https://gateway.example/v8", model: "custom-deployment", providerType: "qwen" });
  const legacy = providerForm({ name: "Legacy", base_url: "https://legacy.example/v1", model: "legacy-model", api_key: "MUST_NOT_APPEAR" });
  assert.equal(legacy.providerType, "custom");
  assert.equal(legacy.baseUrl, "https://legacy.example/v1");
  assert.equal(legacy.model, "legacy-model");
  assert.equal(JSON.stringify(legacy).includes("MUST_NOT_APPEAR"), false);
});

test("model discovery can use a new key or server-owned saved credential and sends current custom endpoint", () => {
  const form = { ...selectProviderTemplate(providerForm(), catalog[3], catalog), baseUrl: " https://proxy.example/v1 " };
  assert.deepEqual(providerModelsRequest(form, " new-key "), { provider_type: "anthropic", base_url: "https://proxy.example/v1", api_key: "new-key", provider_id: null });
  assert.deepEqual(providerModelsRequest(form, " ", 42), { provider_type: "anthropic", base_url: "https://proxy.example/v1", api_key: null, provider_id: 42 });
});

test("saving trims custom model settings and leaves an existing key unchanged when empty", () => {
  const form = { ...providerForm(), name: " My model ", model: " my-deployment ", baseUrl: " https://proxy.example/v1 ", providerType: "deepseek" };
  assert.deepEqual(providerSaveRequest(form, ""), { name: "My model", model: "my-deployment", base_url: "https://proxy.example/v1", provider_type: "deepseek", api_key: null });
  assert.equal(providerSaveRequest(form, " new-key ").api_key, "new-key");
});

test("every provider request preview uses Responses and removes trailing URL slashes", () => {
  for (const entry of catalog) {
    assert.equal(providerEndpoint({ ...selectProviderTemplate(providerForm(), entry, catalog), baseUrl: " https://gateway.example/v1/// " }), "https://gateway.example/v1/responses");
  }
});
