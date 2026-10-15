import { CheckCircle2, Eye, EyeOff, KeyRound, LoaderCircle, Plus, ShieldCheck, TestTube2, Trash2 } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import type { Provider } from "@/lib/types";
import { cn } from "@/lib/utils";

type Props = { providers: Provider[]; onChanged: (preferredId?: number) => Promise<void> };
const emptyForm = { name: "", model: "", baseUrl: "https://api.openai.com/v1" };

export function ProviderManager({ providers, onChanged }: Props) {
  const [editingId, setEditingId] = useState<number>();
  const [form, setForm] = useState(emptyForm);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const keyInput = useRef<HTMLInputElement>(null);

  function choose(provider?: Provider) {
    setEditingId(provider?.id);
    setForm(provider ? { name: provider.name, model: provider.model, baseUrl: provider.base_url } : emptyForm);
    setError(""); setMessage(""); setConfirmDelete(false); setShowKey(false);
    if (keyInput.current) keyInput.current.value = "";
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setMessage("");
    try {
      const saved = await api<Provider>(editingId ? `/account/providers/${editingId}` : "/account/providers", {
        method: editingId ? "PUT" : "POST",
        body: JSON.stringify({ name: form.name.trim(), model: form.model.trim(), base_url: form.baseUrl.trim(), api_key: keyInput.current?.value.trim() || null }),
      });
      setEditingId(saved.id);
      if (keyInput.current) keyInput.current.value = "";
      setShowKey(false);
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
    <div><h2 className="text-lg font-semibold">模型预设</h2><p className="mt-1 text-xs leading-6 text-slate-500">连接你使用的模型服务，按预设独立统计用量。</p></div>
    <div className="grid gap-5 lg:grid-cols-[180px_minmax(0,1fr)]">
      <aside className="flex gap-2 overflow-x-auto border-b border-slate-100 pb-4 lg:block lg:space-y-2 lg:overflow-visible lg:border-b-0 lg:border-r lg:pb-0 lg:pr-4">
        <button disabled={busy} onClick={() => choose()} className={cn("flex shrink-0 items-center gap-2 rounded-xl border border-dashed px-3 py-3 text-xs font-medium lg:w-full", !editingId ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-500 hover:bg-slate-50")}><Plus className="size-3.5" />新建预设</button>
        {providers.map((provider) => <button key={provider.id} disabled={busy} onClick={() => choose(provider)} className={cn("w-40 shrink-0 rounded-xl px-3 py-3 text-left lg:w-full", editingId === provider.id ? "bg-blue-50 text-blue-700" : "bg-slate-50/50 hover:bg-slate-50")}><span className="block truncate text-xs font-semibold">{provider.name}</span><span className="mt-1 block truncate text-[10px] text-slate-400">{provider.model}</span>{!provider.compatible && <span className="mt-1 block text-[10px] text-amber-600">请检查模型配置</span>}</button>)}
      </aside>
      <form onSubmit={submit} className="min-w-0 space-y-4">
        <div className="flex items-center justify-between gap-2"><h3 className="text-sm font-semibold">{editingId ? "编辑预设" : "创建一个模型预设"}</h3><span className="rounded-md bg-slate-100 px-2 py-1 text-[10px] text-slate-500">Responses API</span></div>
        <label className="block text-xs font-medium text-slate-600">预设名称<Input disabled={busy} className="mt-1.5" maxLength={80} value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="例如：我的研究模型" required /></label>
        <label className="block text-xs font-medium text-slate-600">模型 ID<Input disabled={busy} className="mt-1.5 font-mono text-xs" maxLength={120} value={form.model} onChange={(event) => setForm({ ...form, model: event.target.value })} placeholder="填写服务商提供的实际模型 ID" required /><span className="mt-1.5 block text-[10px] font-normal leading-5 text-slate-400">支持自定义模型 ID；模型和端点需要支持 Responses API。</span></label>
        <label className="block text-xs font-medium text-slate-600">Base URL<Input disabled={busy} className="mt-1.5 font-mono text-xs" type="url" value={form.baseUrl} onChange={(event) => setForm({ ...form, baseUrl: event.target.value })} placeholder="https://api.example.com/v1" required /><span className="mt-1.5 block text-[10px] font-normal text-slate-400">填写服务根地址，后端会使用 /responses 端点。</span></label>
        <label className="block text-xs font-medium text-slate-600">API Key<div className="relative mt-1.5"><input ref={keyInput} disabled={busy} name="api_key" maxLength={2000} type={showKey ? "text" : "password"} autoComplete="new-password" required={!editingId} placeholder={editingId ? "留空保留已保存的密钥" : "填写该服务的 API Key"} className="flex h-10 w-full rounded-lg border border-slate-200 bg-white px-3 pr-10 text-sm outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-50 disabled:opacity-50" /><button type="button" onClick={() => setShowKey((value) => !value)} aria-label={showKey ? "隐藏输入的密钥" : "显示输入的密钥"} className="absolute right-2 top-2 rounded p-1 text-slate-400 hover:text-slate-600">{showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}</button></div></label>
        <p className="flex items-center gap-1.5 text-[10px] text-slate-400"><ShieldCheck className="size-3.5" />密钥在服务端加密保存，已保存的密钥不会回显。</p>
        <div className="flex flex-wrap items-center gap-2 pt-1"><Button disabled={busy}>{busy ? <LoaderCircle className="size-3.5 animate-spin" /> : <KeyRound className="size-3.5" />}保存预设</Button>{editingId && <><Button type="button" disabled={busy} variant="outline" onClick={() => void test()}><TestTube2 className="size-3.5" />测试连接</Button><button type="button" disabled={busy} onClick={() => setConfirmDelete((value) => !value)} className="ml-auto rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600" aria-label="删除当前模型预设"><Trash2 className="size-4" /></button></>}</div>
        {editingId && <p className="text-[10px] leading-5 text-slate-400">测试连接会使用已保存的设置发送一次小型模型请求，并计入用量。</p>}
        {confirmDelete && <div className="rounded-xl border border-red-100 bg-red-50 p-3"><p className="text-xs text-red-700">删除此模型预设？历史报告和用量记录会保留。</p><div className="mt-2 flex gap-3 text-xs"><button type="button" disabled={busy} className="font-semibold text-red-600" onClick={() => void remove()}>确认删除</button><button type="button" disabled={busy} className="text-slate-500" onClick={() => setConfirmDelete(false)}>取消</button></div></div>}
        {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-xs leading-6 text-red-700">{error}</p>}
        {message && <p role="status" className="flex items-start gap-2 rounded-xl bg-blue-50 p-3 text-xs leading-6 text-blue-700"><CheckCircle2 className="mt-1 size-3.5 shrink-0" />{message}</p>}
      </form>
    </div>
  </div>;
}
