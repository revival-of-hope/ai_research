import { AlertCircle, CheckCircle2, FileText, LoaderCircle, RefreshCw, Trash2, Upload } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { SourceDocument } from "@/lib/types";

export function SourcesPanel({ onChanged }: { onChanged?: () => void }) {
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [deleting, setDeleting] = useState<number>();
  const [confirmDelete, setConfirmDelete] = useState<number>();
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const changed = useRef(onChanged);
  changed.current = onChanged;
  const busy = uploading || deleting !== undefined;
  const processing = documents.some((doc) => doc.status === "processing");
  const load = useCallback(async () => { setDocuments(await api<SourceDocument[]>("/documents")); }, []);
  const refresh = useCallback(async () => {
    setLoading(true); setError("");
    try { await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "资料加载失败"); }
    finally { setLoading(false); }
  }, [load]);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => {
    if (!processing) return;
    const timer = window.setInterval(() => { void load().then(() => changed.current?.()).catch(() => undefined); }, 2500);
    return () => window.clearInterval(timer);
  }, [processing, load]);

  async function upload(file?: File) {
    if (!file || busy) return;
    setUploading(true); setError("");
    const body = new FormData(); body.append("upload", file);
    try {
      const saved = await api<SourceDocument>("/documents", { method: "POST", body });
      await load(); onChanged?.();
      if (saved.status === "failed") setError(saved.error_message || "文档解析失败，请检查文件后重新上传。");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "上传失败"); }
    finally { setUploading(false); if (input.current) input.current.value = ""; }
  }
  async function remove(id: number) {
    setDeleting(id); setError("");
    try { await api<void>(`/documents/${id}`, { method: "DELETE" }); await load(); onChanged?.(); setConfirmDelete(undefined); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "删除失败"); }
    finally { setDeleting(undefined); }
  }

  return <div className="space-y-5">
    <div className="flex items-start justify-between gap-3"><div><h2 className="text-lg font-semibold">我的资料</h2><p className="mt-1 text-xs leading-6 text-slate-500">上传资料后，在研究输入框中勾选本轮需要使用的文件。</p></div><button disabled={loading || busy} onClick={() => void refresh()} className="rounded-lg p-2 text-slate-400 hover:bg-slate-50" aria-label="刷新资料列表"><RefreshCw className={"size-4 " + (loading ? "animate-spin" : "")} /></button></div>
    <div onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false); }} onDrop={(event) => { event.preventDefault(); setDragging(false); void upload(event.dataTransfer.files[0]); }} className={"rounded-2xl border border-dashed p-5 text-center transition " + (dragging ? "border-blue-400 bg-blue-50" : "border-slate-300 bg-slate-50/40")}>
      <input ref={input} className="hidden" type="file" accept=".txt,.md,.markdown,.csv,.docx,.pdf" onChange={(event) => void upload(event.target.files?.[0])} />
      <span className="mx-auto grid size-10 place-items-center rounded-xl border border-slate-200 bg-white text-slate-400">{uploading ? <LoaderCircle className="size-5 animate-spin text-blue-500" /> : <Upload className="size-5" />}</span>
      <p className="mt-3 text-xs font-medium text-slate-600">{uploading ? "正在上传并解析资料…" : "将文件拖到这里，或选择上传"}</p>
      <button type="button" disabled={busy} onClick={() => input.current?.click()} className="mt-3 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 hover:border-blue-200 hover:text-blue-600 disabled:opacity-50">选择文件</button>
      <p className="mt-3 text-[10px] leading-5 text-slate-400">TXT、Markdown、CSV、DOCX、带文字层的 PDF</p>
    </div>
    {error && <p role="alert" className="flex items-start gap-2 rounded-xl bg-red-50 p-3 text-xs leading-6 text-red-700"><AlertCircle className="mt-1 size-3.5 shrink-0" />{error}</p>}
    <div className="flex items-center justify-between"><h3 className="text-xs font-semibold text-slate-600">资料列表</h3><span className="text-[10px] text-slate-400">{documents.length} 份资料</span></div>
    {loading && !documents.length ? <div role="status" className="py-6 text-center text-xs text-slate-400">正在读取资料…</div> : !documents.length ? <div className="rounded-xl border border-slate-100 p-6 text-center"><FileText className="mx-auto mb-2 size-5 text-slate-300" /><p className="text-xs text-slate-400">还没有资料，上传你的第一份文档。</p></div> : <div className="space-y-2">{documents.map((doc) => <div key={doc.id} className="rounded-xl border border-slate-200 p-3"><div className="flex items-start gap-3"><FileText className="mt-1 size-5 shrink-0 text-blue-500" /><div className="min-w-0 flex-1"><p className="truncate text-xs font-medium text-slate-700" title={doc.filename}>{doc.filename}</p><div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slate-400"><span>{doc.size_bytes >= 1048576 ? `${(doc.size_bytes / 1048576).toFixed(1)} MB` : `${(doc.size_bytes / 1024).toFixed(1)} KB`}</span><span className={"inline-flex items-center gap-1 " + (doc.status === "ready" ? "text-emerald-600" : doc.status === "failed" ? "text-red-500" : "text-blue-500")}>{doc.status === "ready" ? <CheckCircle2 className="size-3" /> : doc.status === "processing" ? <LoaderCircle className="size-3 animate-spin" /> : <AlertCircle className="size-3" />}{doc.status === "ready" ? "可用" : doc.status === "processing" ? "解析中" : "解析失败"}</span></div>{doc.error_message && <p className="mt-2 break-words text-[11px] leading-5 text-red-500">{doc.error_message}</p>}</div><button disabled={busy} type="button" aria-label={`删除资料 ${doc.filename}`} onClick={() => setConfirmDelete(doc.id)} className="rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-500 disabled:opacity-30"><Trash2 className="size-3.5" /></button></div>{confirmDelete === doc.id && <div className="mt-3 border-t border-slate-100 pt-3"><p className="text-xs text-slate-500">删除该文件及其检索内容？</p><div className="mt-2 flex gap-3 text-xs"><button type="button" disabled={busy} onClick={() => void remove(doc.id)} className="font-medium text-red-600">{deleting === doc.id ? "删除中…" : "确认删除"}</button><button type="button" disabled={busy} onClick={() => setConfirmDelete(undefined)} className="text-slate-400">取消</button></div></div>}</div>)}</div>}
  </div>;
}
