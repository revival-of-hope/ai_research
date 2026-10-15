import { BarChart3, BookOpen, Check, ChevronUp, Database, KeyRound, LogOut, MessageSquareText, Pencil, Plus, Search, Settings, ShieldCheck, Sparkles, Trash2, X } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import type { SettingsSection } from "@/components/settings/settings-dialog";
import type { Conversation } from "@/lib/types";
import { useDialogFocus } from "@/lib/use-dialog-focus";
import { cn } from "@/lib/utils";

type Props = {
  conversations: Conversation[];
  activeId?: number;
  email?: string;
  isAdmin?: boolean;
  busy: boolean;
  loading: boolean;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  onNew: () => void;
  onOpen: (id: number) => void;
  onRename: (id: number, title: string) => Promise<void>;
  onDelete: (id: number) => Promise<void>;
  onOpenSettings: (section: SettingsSection) => void;
  onLogout: () => void;
};

function SidebarBody(props: Props & { mobile?: boolean }) {
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [query, setQuery] = useState("");
  const [editingId, setEditingId] = useState<number>();
  const [title, setTitle] = useState("");
  const [deletingId, setDeletingId] = useState<number>();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const matches = props.conversations.filter((conversation) => conversation.title.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  const closeMobile = () => { if (props.mobile) props.onCloseMobile(); };

  function openSettings(section: SettingsSection) { setShowUserMenu(false); closeMobile(); props.onOpenSettings(section); }
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
    <div className="flex h-12 shrink-0 items-center gap-2.5 px-2">
      <span className="grid size-8 place-items-center rounded-xl bg-blue-600 text-white"><Sparkles className="size-4" /></span>
      <span id={props.mobile ? "mobile-workspace-label" : undefined} className="text-lg font-semibold tracking-tight">Research AI</span>
      {props.mobile && <button aria-label="关闭侧栏" className="ml-auto rounded-lg p-2 text-slate-500 hover:bg-white" onClick={props.onCloseMobile}><X className="size-5" /></button>}
    </div>
    <button disabled={props.busy} onClick={() => { props.onNew(); closeMobile(); }} className="mt-5 flex h-11 shrink-0 items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-sm font-medium shadow-xs hover:border-blue-200 hover:text-blue-700 disabled:opacity-50"><Plus className="size-4" />新建研究<span className="ml-auto text-lg font-normal text-slate-300">+</span></button>
    <div className="mt-5 grid grid-cols-2 gap-1 border-b border-slate-200/80 pb-4">
      <button onClick={() => openSettings("sources")} className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-slate-600 hover:bg-white"><Database className="size-4" />我的资料</button>
      <button onClick={() => openSettings("providers")} className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-slate-600 hover:bg-white"><Settings className="size-4" />模型设置</button>
    </div>
    <div className="mt-5 flex items-center justify-between px-2"><h2 className="text-xs font-semibold text-slate-500">最近研究</h2><span className="text-[10px] text-slate-400">{props.conversations.length}</span></div>
    <label className="mt-2 flex shrink-0 items-center gap-2 rounded-lg border border-transparent px-2 py-2 text-slate-400 focus-within:border-blue-200 focus-within:bg-white"><Search className="size-3.5" /><input aria-label="搜索历史研究" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索历史记录" className="min-w-0 flex-1 bg-transparent text-xs text-slate-600 outline-none placeholder:text-slate-400" />{query && <button onClick={() => setQuery("")} aria-label="清除搜索"><X className="size-3" /></button>}</label>
    <nav aria-label="研究历史" className="mt-1 min-h-0 flex-1 space-y-1 overflow-y-auto overscroll-contain pb-4">
      {props.loading && !props.conversations.length && <div className="space-y-3 px-2 py-3" aria-label="正在加载历史">{[1, 2, 3].map((item) => <div key={item} className="h-5 animate-pulse rounded bg-slate-200/70" />)}</div>}
      {!props.loading && !matches.length && <p className="px-3 py-4 text-xs leading-6 text-slate-400">{query ? "没有找到匹配的研究" : "从一个问题开始，研究会保存在这里。"}</p>}
      {matches.map((conversation) => <div key={conversation.id} className={cn("group rounded-xl", props.activeId === conversation.id ? "bg-white shadow-xs" : "hover:bg-white/75")}>
        {editingId === conversation.id ? <form onSubmit={(event) => { event.preventDefault(); void saveTitle(conversation.id); }} className="flex items-center gap-1 p-2"><input autoFocus aria-label="新的研究标题" maxLength={160} value={title} onChange={(event) => setTitle(event.target.value)} onKeyDown={(event) => { if (event.key === "Escape") setEditingId(undefined); }} className="min-w-0 flex-1 rounded-lg border border-blue-200 bg-white px-2 py-1.5 text-xs outline-none" /><button disabled={saving || !title.trim()} aria-label="保存标题" className="rounded p-1.5 text-blue-600"><Check className="size-3.5" /></button><button type="button" aria-label="取消重命名" onClick={() => setEditingId(undefined)} className="rounded p-1.5 text-slate-400"><X className="size-3.5" /></button></form> : <div className="flex items-center">
          <button disabled={props.busy} aria-current={props.activeId === conversation.id ? "page" : undefined} title={conversation.title} onClick={() => { props.onOpen(conversation.id); closeMobile(); }} className="flex min-w-0 flex-1 items-center gap-2 rounded-xl py-2.5 pl-3 pr-1 text-left text-xs text-slate-600 disabled:opacity-50"><MessageSquareText className="size-3.5 shrink-0 text-slate-400" /><span className="truncate">{conversation.title}</span></button>
          <div className="flex pr-1 opacity-100 transition lg:opacity-0 lg:group-hover:opacity-100 lg:group-focus-within:opacity-100">
            <button disabled={props.busy || saving} aria-label={`重命名 ${conversation.title}`} onClick={() => { setEditingId(conversation.id); setTitle(conversation.title); setDeletingId(undefined); setError(""); }} className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><Pencil className="size-3" /></button>
            <button disabled={props.busy || saving} aria-label={`删除 ${conversation.title}`} onClick={() => { setDeletingId(conversation.id); setEditingId(undefined); setError(""); }} className="rounded-md p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 className="size-3" /></button>
          </div>
        </div>}
        {deletingId === conversation.id && <div className="border-t border-slate-100 px-3 pb-3 pt-2"><p className="text-xs leading-5 text-slate-500">删除这条研究及其所有消息？</p><div className="mt-2 flex gap-3 text-xs"><button disabled={saving} onClick={() => void remove(conversation.id)} className="font-medium text-red-600">{saving ? "删除中…" : "确认删除"}</button><button disabled={saving} onClick={() => setDeletingId(undefined)} className="text-slate-500">取消</button></div></div>}
      </div>)}
      {error && <p role="alert" className="px-3 py-2 text-xs text-red-600">{error}</p>}
    </nav>
    <div className="relative shrink-0 border-t border-slate-200/80 pt-3">
      {showUserMenu && <div className="absolute inset-x-0 bottom-[calc(100%+8px)] z-30 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl shadow-slate-200/70">
        <div className="mb-1 border-b border-slate-100 px-3 py-2"><p className="truncate text-xs font-medium">{props.email}</p><p className="mt-1 text-[10px] text-slate-400">个人工作区</p></div>
        {([
          ["providers", "模型预设", KeyRound], ["usage", "Token 用量", BarChart3], ["sources", "资料库", Database], ["guide", "使用说明", BookOpen],
        ] as const).map(([id, label, Icon]) => <button key={id} onClick={() => openSettings(id)} className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-xs text-slate-600 hover:bg-slate-50"><Icon className="size-4" />{label}</button>)}
        {props.isAdmin && <Link to="/admin" onClick={closeMobile} className="flex items-center gap-3 rounded-lg px-3 py-2 text-xs text-slate-600 hover:bg-slate-50"><ShieldCheck className="size-4" />用户管理</Link>}
        <button disabled={props.busy} onClick={props.onLogout} className="mt-1 flex w-full items-center gap-3 border-t border-slate-100 px-3 py-2.5 text-xs text-red-600 disabled:opacity-40"><LogOut className="size-4" />退出登录</button>
      </div>}
      <button aria-expanded={showUserMenu} onClick={() => setShowUserMenu((value) => !value)} className="flex w-full items-center gap-2.5 rounded-xl px-2 py-2 text-left hover:bg-white"><span className="grid size-8 shrink-0 place-items-center rounded-full bg-slate-800 text-xs font-medium text-white">{props.email?.slice(0, 1).toUpperCase() || "U"}</span><span className="min-w-0 flex-1"><span className="block truncate text-xs font-medium text-slate-700">{props.email?.split("@")[0] || "个人账户"}</span><span className="mt-0.5 block truncate text-[10px] text-slate-400">{props.email}</span></span><ChevronUp className={cn("size-3.5 text-slate-400", showUserMenu && "rotate-180")} /></button>
    </div>
  </>;
}

function MobileSidebar(props: Props) {
  const root = useRef<HTMLDivElement>(null);
  useDialogFocus(root, props.onCloseMobile);
  return <div className="fixed inset-0 z-40 lg:hidden"><div className="absolute inset-0 bg-slate-950/25 backdrop-blur-[2px]" onClick={props.onCloseMobile} /><div ref={root} role="dialog" aria-modal="true" aria-labelledby="mobile-workspace-label" className="relative flex h-dvh w-[min(300px,88vw)] flex-col border-r border-slate-200 bg-[#f7f8fa] p-4 shadow-xl"><SidebarBody {...props} mobile /></div></div>;
}

export function ResearchSidebar(props: Props) {
  return <><aside aria-label="工作区导航" className="hidden h-dvh w-[272px] shrink-0 flex-col border-r border-slate-200/70 bg-[#f7f8fa] p-4 lg:flex"><SidebarBody {...props} /></aside>{props.mobileOpen && <MobileSidebar {...props} />}</>;
}
