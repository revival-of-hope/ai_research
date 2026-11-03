import { BarChart3, BookOpen, ChevronUp, Database, KeyRound, LogOut, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import type { SettingsSection } from "@/components/settings/settings-dialog";
import { cn } from "@/lib/utils";

type Props = {
  email?: string;
  isAdmin?: boolean;
  busy?: boolean;
  onLogout: () => void;
  onOpenSettings?: (section: SettingsSection) => void;
  onNavigate?: () => void;
};

export function WorkspaceAccount({ email, isAdmin, busy, onLogout, onOpenSettings, onNavigate }: Props) {
  const [expanded, setExpanded] = useState(false);
  const close = () => { setExpanded(false); onNavigate?.(); };
  const openSection = (section: SettingsSection) => {
    setExpanded(false);
    onNavigate?.();
    onOpenSettings?.(section);
  };
  const itemClass = "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-xs text-slate-600 hover:bg-slate-50";
  return <div className="relative shrink-0 border-t border-slate-200/80 pt-3">
    {expanded && <div className="absolute inset-x-0 bottom-[calc(100%+8px)] z-30 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl shadow-slate-200/70">
      <div className="mb-1 border-b border-slate-100 px-3 py-2"><p className="truncate text-xs font-medium">{email}</p><p className="mt-1 text-[10px] text-slate-400">个人工作区</p></div>
      {onOpenSettings
        ? <>
          <button className={itemClass} onClick={() => openSection("providers")}><KeyRound className="size-4" />模型预设</button>
          <button className={itemClass} onClick={() => openSection("usage")}><BarChart3 className="size-4" />Token 用量</button>
          <button className={itemClass} onClick={() => openSection("sources")}><Database className="size-4" />资料库</button>
          <button className={itemClass} onClick={() => openSection("guide")}><BookOpen className="size-4" />使用说明</button>
        </>
        : <>
          <Link className={itemClass} onClick={close} to="/settings"><KeyRound className="size-4" />模型预设</Link>
          <Link className={itemClass} onClick={close} to="/usage"><BarChart3 className="size-4" />Token 用量</Link>
          <Link className={itemClass} onClick={close} to="/sources"><Database className="size-4" />资料库</Link>
          <Link className={itemClass} onClick={close} to="/guide"><BookOpen className="size-4" />使用说明</Link>
        </>}
      {isAdmin && <Link to="/admin" onClick={close} className={itemClass}><ShieldCheck className="size-4" />用户管理</Link>}
      <button type="button" disabled={busy} onClick={() => { setExpanded(false); onLogout(); }} className="mt-1 flex w-full items-center gap-2.5 border-t border-slate-100 px-3 py-2.5 text-xs text-red-600 disabled:opacity-40"><LogOut className="size-4" />退出登录</button>
    </div>}
    <button type="button" aria-expanded={expanded} aria-label="账户菜单" onClick={() => setExpanded((v) => !v)} className="flex w-full items-center gap-2.5 rounded-xl px-2 py-2 text-left hover:bg-white">
      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-slate-800 text-xs font-medium text-white">{email?.slice(0, 1).toUpperCase() || "U"}</span>
      <span className="min-w-0 flex-1"><span className="block truncate text-xs font-medium text-slate-700">{email?.split("@")[0] || "个人账户"}</span><span className="mt-0.5 block truncate text-[10px] text-slate-400">{email}</span></span>
      <ChevronUp className={cn("size-3.5 text-slate-400", expanded && "rotate-180")} />
    </button>
  </div>;
}
