import { Check, MessageSquareText, Pencil, ScanLine, Search, Trash2, X } from "lucide-react";
import { useState } from "react";

import type { Conversation } from "@/lib/types";
import { cn } from "@/lib/utils";

export type WorkspaceHistoryProps = {
  conversations: Conversation[];
  activeId?: number;
  busy: boolean;
  loading: boolean;
  onOpen: (id: number) => void;
  onRename: (id: number, title: string) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
};

export function WorkspaceHistory(props: WorkspaceHistoryProps) {
  const [query, setQuery] = useState("");
  const [editingId, setEditingId] = useState<number>();
  const [title, setTitle] = useState("");
  const [deletingId, setDeletingId] = useState<number>();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const matches = props.conversations.filter((conversation) => conversation.title.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  async function saveTitle(id: number) {
    setSaving(true); setError("");
    try { await props.onRename(id, title); setEditingId(undefined); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "重命名失败"); }
    finally { setSaving(false); }
  }
  async function remove(id: number) {
    setSaving(true); setError("");
    try { await props.onDelete(id); setDeletingId(undefined); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "删除失败"); }
    finally { setSaving(false); }
  }

  return <>
    <div className="mt-5 flex shrink-0 items-center justify-between px-2"><h2 className="text-xs font-semibold text-slate-500">最近研究</h2><span className="text-[10px] text-slate-400">{props.conversations.length}</span></div>
    <label className="mt-2 flex shrink-0 items-center gap-2 rounded-lg border border-transparent px-2 py-2 text-slate-400 focus-within:border-blue-200 focus-within:bg-white"><Search className="size-3.5" /><input aria-label="搜索历史研究" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索历史记录" className="min-w-0 flex-1 bg-transparent text-xs text-slate-600 outline-none placeholder:text-slate-400" />{query && <button onClick={() => setQuery("")} aria-label="清除搜索"><X className="size-3" /></button>}</label>
    <nav aria-label="研究历史" className="mt-1 min-h-28 flex-1 space-y-1 overflow-y-auto overscroll-contain pb-4">
      {props.loading && !props.conversations.length && <div className="space-y-3 px-2 py-3" aria-label="正在加载历史">{[1, 2, 3].map((item) => <div key={item} className="h-5 animate-pulse rounded bg-slate-200/70" />)}</div>}
      {!props.loading && !matches.length && <p className="px-3 py-4 text-xs leading-6 text-slate-400">{query ? "没有找到匹配的研究" : "从一个问题开始，研究会保存在这里。"}</p>}
      {matches.map((conversation) => <div key={conversation.id} className={cn("group rounded-xl", props.activeId === conversation.id ? "bg-white shadow-xs" : "hover:bg-white/75")}>
        {editingId === conversation.id ? <form onSubmit={(event) => { event.preventDefault(); void saveTitle(conversation.id); }} className="flex items-center gap-1 p-2"><input autoFocus aria-label="新的研究标题" maxLength={160} value={title} onChange={(event) => setTitle(event.target.value)} onKeyDown={(event) => { if (event.key === "Escape") setEditingId(undefined); }} className="min-w-0 flex-1 rounded-lg border border-blue-200 bg-white px-2 py-1.5 text-xs outline-none" /><button disabled={saving || !title.trim()} aria-label="保存标题" className="rounded p-1.5 text-blue-600"><Check className="size-3.5" /></button><button type="button" aria-label="取消重命名" onClick={() => setEditingId(undefined)} className="rounded p-1.5 text-slate-400"><X className="size-3.5" /></button></form> : <div className="flex items-center">
          <button disabled={props.busy} aria-current={props.activeId === conversation.id ? "page" : undefined} title={conversation.title} onClick={() => { props.onOpen(conversation.id); }} className="flex min-w-0 flex-1 items-center gap-2 rounded-xl py-2.5 pl-3 pr-1 text-left text-xs text-slate-600 disabled:opacity-50">{conversation.kind === "comparison" ? <ScanLine aria-label="实验核验" className="size-3.5 shrink-0 text-blue-500" /> : <MessageSquareText className="size-3.5 shrink-0 text-slate-400" />}<span className="truncate">{conversation.title}</span></button>
          <div className="flex pr-1 opacity-100 transition lg:opacity-0 lg:group-hover:opacity-100 lg:group-focus-within:opacity-100">
            <button disabled={props.busy || saving} aria-label={`重命名 ${conversation.title}`} onClick={() => { setEditingId(conversation.id); setTitle(conversation.title); setDeletingId(undefined); setError(""); }} className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><Pencil className="size-3" /></button>
            <button disabled={props.busy || saving} aria-label={`删除 ${conversation.title}`} onClick={() => { setDeletingId(conversation.id); setEditingId(undefined); setError(""); }} className="rounded-md p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 className="size-3" /></button>
          </div>
        </div>}
        {deletingId === conversation.id && <div className="border-t border-slate-100 px-3 pb-3 pt-2"><p className="text-xs leading-5 text-slate-500">删除这条研究记录？关联的消息和实验核验结果也会删除，资料库文件保留。</p><div className="mt-2 flex gap-3 text-xs"><button disabled={saving} onClick={() => void remove(conversation.id)} className="font-medium text-red-600">{saving ? "删除中…" : "确认删除"}</button><button disabled={saving} onClick={() => setDeletingId(undefined)} className="text-slate-500">取消</button></div></div>}
      </div>)}
      {error && <p role="alert" className="px-3 py-2 text-xs text-red-600">{error}</p>}
    </nav>
  </>;
}
