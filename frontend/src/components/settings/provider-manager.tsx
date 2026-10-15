import { CheckCircle2, Eye, EyeOff, KeyRound, ListRestart, LoaderCircle, Plus, ShieldCheck, TestTube2, Trash2 } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { providerEndpoint, providerForm, providerModelsRequest, providerSaveRequest, selectProviderTemplate } from "@/lib/provider-form";
import type { Provider, ProviderCatalogEntry, ProviderModels } from "@/lib/types";
import { cn } from "@/lib/utils";

type Props = { providers: Provider[]; onChanged: (preferredId?: number) => Promise<void> };

export function ProviderManager({ providers, onChanged }: Props) {
  const [editingId, setEditingId] = useState<number>();
  const [form, setForm] = useState(providerForm);
  const [catalog, setCatalog] = useState<ProviderCatalogEntry[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState("");
  const [catalogAttempt, setCatalogAttempt] = useState(0);
  const [discoveredModels, setDiscoveredModels] = useState<ProviderModels>();
  const [modelsError, setModelsError] = useState("");
  const [modelsLoading, setModelsLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const keyInput = useRef<HTMLInputElement>(null);
  const locked = busy || modelsLoading;
  const savedProvider = providers.find((provider) => provider.id === editingId);
  const addressChanged = Boolean(savedProvider && form.baseUrl.trim().replace(/\/+$/, "") !== savedProvider.base_url.replace(/\/+$/, ""));
  const selectedTemplate = catalog.find((entry) => entry.id === form.providerType);
  const modelChoices = discoveredModels?.models ?? selectedTemplate?.models ?? [];

  useEffect(() => {
    const controller = new AbortController();
    setCatalogLoading(true); setCatalogError("");
    api<ProviderCatalogEntry[]>("/account/provider-catalog", { signal: controller.signal }).then((entries) => {
      setCatalog(entries);
      const initial = entries.find((entry) => entry.id === "openai");
      if (initial) setForm((current) => !current.name && !current.model && !current.baseUrl ? selectProviderTemplate(current, initial, entries) : current);
    }).catch((reason) => {
      if (!controller.signal.aborted) setCatalogError(reason instanceof Error ? reason.message : "提供方列表加载失败");
    }).finally(() => { if (!controller.signal.aborted) setCatalogLoading(false); });
    return () => controller.abort();
  }, [catalogAttempt]);

  function clearModelDiscovery() {
    setDiscoveredModels(undefined); setModelsError("");
  }

  function clearKey() {
    if (keyInput.current) keyInput.current.value = "";
    setShowKey(false);
  }

  function choose(provider?: Provider) {
    setEditingId(provider?.id);
    const initial = catalog.find((entry) => entry.id === "openai");
    setForm(provider ? providerForm(provider) : initial ? selectProviderTemplate(providerForm(), initial, catalog) : providerForm());
    setError(""); setMessage(""); setConfirmDelete(false);
    clearModelDiscovery(); clearKey();
  }

  function selectTemplate(entry: ProviderCatalogEntry) {
    setForm((current) => selectProviderTemplate(current, entry, catalog));
    setError(""); setMessage("");
    clearModelDiscovery(); clearKey();
  }

  async function loadModels() {
    if (addressChanged && !keyInput.current?.value.trim()) { setModelsError("请求地址已改变，请重新填写对应服务商的 API Key。"); return; }
    if (!keyInput.current?.value.trim() && !editingId) { setModelsError("请先填写 API Key，再获取该密钥可见的模型。"); return; }
    if (!form.baseUrl.trim()) { setModelsError("请先填写 Base URL。"); return; }
    setModelsLoading(true); setModelsError("");
    try {
      setDiscoveredModels(await api<ProviderModels>("/account/provider-models", {
        method: "POST", body: JSON.stringify(providerModelsRequest(form, keyInput.current?.value ?? "", editingId)),
      }));
    } catch (reason) {
      setDiscoveredModels(undefined);
      setModelsError(reason instanceof Error ? reason.message : "获取模型列表失败");
    } finally { setModelsLoading(false); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setMessage("");
    try {
      const saved = await api<Provider>(editingId ? `/account/providers/${editingId}` : "/account/providers", {
        method: editingId ? "PUT" : "POST",
        body: JSON.stringify(providerSaveRequest(form, keyInput.current?.value ?? "")),
      });
      setEditingId(saved.id);
      setForm(providerForm(saved));
      clearKey();
      await onChanged(saved.id);
      setMessage("预设已保存，可在研究输入框中选择使用。");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "保存失败"); }
    finally { setBusy(false); }
  }

  async function test() {
    if (!editingId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const result = await api<{ message: string }>(`/account/providers/${editingId}/test`, { method: "POST" });
      setMessage(result.message);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "连接测试失败"); }
    finally { setBusy(false); }
  }

  async function remove() {
    if (!editingId) return;
    setBusy(true); setError(""); setMessage("");
    try {
      await api<void>(`/account/providers/${editingId}`, { method: "DELETE" });
      await onChanged(); choose(); setMessage("预设已删除，历史报告和用量记录仍可查看。");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "删除失败"); }
    finally { setBusy(false); }
  }

  return <div className="space-y-6">
    <div><h2 className="text-lg font-semibold">模型预设</h2><p className="mt-1 text-xs leading-6 text-slate-500">选择提供方，自动填入请求地址和推荐模型。每个预设独立统计用量。</p></div>
    <div className="grid gap-5 lg:grid-cols-[180px_minmax(0,1fr)]">
      <aside className="flex gap-2 overflow-x-auto border-b border-slate-100 pb-4 lg:block lg:space-y-2 lg:overflow-visible lg:border-b-0 lg:border-r lg:pb-0 lg:pr-4">
        <button type="button" disabled={locked} onClick={() => choose()} className={cn("flex shrink-0 items-center gap-2 rounded-xl border border-dashed px-3 py-3 text-xs font-medium lg:w-full", !editingId ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-500 hover:bg-slate-50")}><Plus className="size-3.5" />新建预设</button>
        {providers.map((provider) => <button type="button" key={provider.id} disabled={locked} onClick={() => choose(provider)} className={cn("w-40 shrink-0 rounded-xl px-3 py-3 text-left lg:w-full", editingId === provider.id ? "bg-blue-50 text-blue-700" : "bg-slate-50/50 hover:bg-slate-50")}><span className="block truncate text-xs font-semibold">{provider.name}</span><span className="mt-1 block truncate text-[10px] text-slate-400">{provider.model}</span>{!provider.compatible && <span className="mt-1 block text-[10px] text-amber-600">请检查模型配置</span>}</button>)}
      </aside>
      <form onSubmit={submit} className="min-w-0 space-y-4">
        <div className="flex items-center justify-between gap-2"><h3 className="text-sm font-semibold">{editingId ? "编辑预设" : "创建一个模型预设"}</h3><span className="rounded-md bg-slate-100 px-2 py-1 text-[10px] text-slate-500">Responses API</span></div>
        <fieldset disabled={locked} className="space-y-2"><legend className="mb-2 text-xs font-medium text-slate-600">模型提供方</legend>
          {catalogLoading && <p role="status" className="text-xs text-slate-400">正在读取提供方…</p>}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">{catalog.map((entry) => <label key={entry.id} className={cn("flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-3 transition", entry.id === form.providerType ? "border-blue-200 bg-blue-50/80 text-blue-700" : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50", locked && "cursor-not-allowed opacity-50")}><input type="radio" name="provider_type" value={entry.id} checked={entry.id === form.providerType} onChange={() => selectTemplate(entry)} className="size-3.5 shrink-0 accent-blue-600" /><span className="min-w-0"><span className="block text-xs font-semibold">{entry.name}</span>{entry.id === "anthropic" && <span className="mt-0.5 block text-[9px] font-normal text-slate-400">需配置 Responses 网关</span>}</span></label>)}</div>
          {catalogError && <p role="alert" className="rounded-lg bg-amber-50 p-3 text-xs leading-5 text-amber-700">{catalogError}<button type="button" disabled={locked} onClick={() => setCatalogAttempt((value) => value + 1)} className="ml-2 underline">重新加载提供方</button><span className="block">仍可在下方手动配置地址与模型。</span></p>}
        </fieldset>
        <label className="block text-xs font-medium text-slate-600">预设名称<Input disabled={locked} className="mt-1.5" maxLength={80} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="例如：我的研究模型" required /></label>
        <label className="block min-w-0 text-xs font-medium text-slate-600">Base URL<Input disabled={locked} className="mt-1.5 font-mono text-xs" type="url" value={form.baseUrl} onChange={(event) => { setForm({ ...form, baseUrl: event.target.value }); clearModelDiscovery(); }} placeholder={form.providerType === "anthropic" ? "填写支持 Responses API 的 Claude 网关地址" : "https://api.example.com/v1"} required /></label>
        <p className="break-all text-[10px] leading-5 text-slate-400">请求网址：{form.baseUrl ? providerEndpoint(form) : "填写 Base URL 后显示"}。可按服务商或代理要求修改。</p>
        {form.providerType === "anthropic" && <p className="rounded-lg bg-blue-50 p-3 text-[11px] leading-5 text-blue-700">Claude 需要你自己的支持 Responses API 的网关。填写网关地址和对应密钥后，再获取模型或保存预设。</p>}
        <label className="block text-xs font-medium text-slate-600">API Key<div className="relative mt-1.5"><input ref={keyInput} disabled={locked} name="api_key" maxLength={2000} type={showKey ? "text" : "password"} autoComplete="new-password" required={!editingId || addressChanged} onChange={clearModelDiscovery} placeholder={addressChanged ? "地址已改变，请重新填写对应密钥" : editingId ? "留空保留已保存的密钥" : "填写该服务的 API Key"} className="flex h-10 w-full rounded-lg border border-slate-200 bg-white px-3 pr-10 text-sm outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50 disabled:opacity-50" /><button type="button" disabled={locked} onClick={() => setShowKey((value) => !value)} aria-label={showKey ? "隐藏输入的密钥" : "显示输入的密钥"} className="absolute right-2 top-2 rounded p-1 text-slate-400 hover:text-slate-600">{showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button></div></label>
        <p className="flex items-center gap-1.5 text-[10px] text-slate-400"><ShieldCheck className="size-3.5" />密钥在服务端加密保存，已保存的密钥不会回显。</p>
        <div className="space-y-3 rounded-xl border border-slate-100 bg-slate-50/60 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-xs font-medium text-slate-600">{discoveredModels ? "该密钥可见的模型" : "推荐模型"}</span><Button type="button" disabled={locked} variant="outline" size="sm" onClick={() => void loadModels()}>{modelsLoading ? <LoaderCircle className="size-3.5 animate-spin" /> : <ListRestart className="size-3.5" />}获取可用模型</Button></div>
          {modelChoices.length > 0 && <select disabled={locked} aria-label={discoveredModels ? "选择接口返回的模型" : "选择推荐模型"} value={modelChoices.includes(form.model) ? form.model : ""} onChange={(event) => { if (event.target.value) setForm({ ...form, model: event.target.value }); }} className="h-10 w-full min-w-0 rounded-lg border border-slate-200 bg-white px-2 font-mono text-xs text-slate-600"><option value="">选择模型并填入 ID</option>{modelChoices.map((model) => <option key={model} value={model}>{model}</option>)}</select>}
          <p className="text-[10px] leading-5 text-slate-400">{discoveredModels ? discoveredModels.message || (modelChoices.length ? "列表来自服务商 Models API；实际调用权限与额度以服务商为准。" : "接口未返回模型，可在下方手动填写模型 ID。") : modelChoices.length ? "推荐列表尚未验证你的账号权限。填写密钥后可获取接口返回的模型，也可手动填写。" : "可填写模型 ID，或使用密钥获取接口返回的模型。"} 获取列表不会发送模型生成请求。</p>
          {modelsError && <p role="alert" className="break-words text-xs leading-6 text-amber-700">获取模型失败：{modelsError} 你仍可选择推荐模型或手动填写模型 ID。</p>}
        </div>
        <label className="block text-xs font-medium text-slate-600">模型 ID<Input disabled={locked} className="mt-1.5 font-mono text-xs" maxLength={120} value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value })} placeholder="填写服务商提供的实际模型 ID" required /><span className="mt-1.5 block text-[10px] font-normal leading-5 text-slate-400">可直接修改为自定义模型 ID。</span></label>
        <div className="flex flex-wrap items-center gap-2 pt-1"><Button disabled={locked}>{busy ? <LoaderCircle className="size-3.5 animate-spin" /> : <KeyRound className="size-3.5" />}保存预设</Button>{editingId && <><Button type="button" disabled={locked} variant="outline" onClick={() => void test()}><TestTube2 className="size-3.5" />测试连接</Button><button type="button" disabled={locked} onClick={() => setConfirmDelete((value) => !value)} className="ml-auto rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600" aria-label="删除当前模型预设"><Trash2 className="size-4" /></button></>}</div>
        {editingId && <p className="text-[10px] leading-5 text-slate-400">测试连接会使用已保存的设置发送一次小型模型请求，并计入用量。</p>}
        {confirmDelete && <div className="rounded-xl border border-red-100 bg-red-50 p-3"><p className="text-xs text-red-700">删除此模型预设？历史报告和用量记录会保留。</p><div className="mt-2 flex gap-3 text-xs"><button type="button" disabled={locked} className="font-semibold text-red-600" onClick={() => void remove()}>确认删除</button><button type="button" disabled={locked} className="text-slate-500" onClick={() => setConfirmDelete(false)}>取消</button></div></div>}
        {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-xs leading-6 text-red-700">{error}</p>}
        {message && <p role="status" className="flex items-start gap-2 rounded-xl bg-blue-50 p-3 text-xs leading-6 text-blue-700"><CheckCircle2 className="mt-1 size-3.5 shrink-0" />{message}</p>}
      </form>
    </div>
  </div>;
}
