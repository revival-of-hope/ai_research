import { BarChart3, BookOpen, Database, FileSearch, KeyRound, Plus, ShieldCheck, Sparkles, X } from "lucide-react";
import { NavLink } from "react-router-dom";

import { cn } from "@/lib/utils";

type Props = {
  isAdmin?: boolean;
  mobile?: boolean;
  onCloseMobile?: () => void;
  onNewResearch?: () => void;
  disabled?: boolean;
};

const actionClass = "flex h-11 w-full items-center gap-2.5 rounded-xl border px-3.5 text-left text-sm font-medium transition disabled:opacity-50";
const actionActive = "border-blue-200 bg-blue-50 text-blue-700";
const actionIdle = "border-slate-200 bg-white text-slate-700 shadow-xs hover:border-blue-200 hover:text-blue-700";
const sectionLink = "flex h-10 w-full items-center gap-2.5 rounded-lg px-3.5 text-sm transition-colors";

export function WorkspaceNavigation({
  isAdmin, mobile, onCloseMobile, onNewResearch, disabled,
}: Props) {
  const closeMobile = () => { if (mobile) onCloseMobile?.(); };
  return <>
    <div className="flex h-12 shrink-0 items-center gap-2.5 px-2">
      <span className="grid size-8 place-items-center rounded-xl bg-blue-600 text-white"><Sparkles className="size-4" /></span>
      <span id={mobile ? "mobile-workspace-label" : undefined} className="text-lg font-semibold tracking-tight">Research AI</span>
      {mobile && <button type="button" aria-label="关闭侧栏" className="ml-auto rounded-lg p-2 text-slate-500 hover:bg-white" onClick={onCloseMobile}><X className="size-5" /></button>}
    </div>
    <nav aria-label="工作区功能导航" className="mt-5 shrink-0 space-y-2">
      <NavLink to="/research" onClick={onNewResearch ? (event) => {
        event.preventDefault(); if (disabled) return; onNewResearch(); closeMobile();
      } : closeMobile} aria-disabled={disabled && !!onNewResearch}
        className={({ isActive }) => cn(actionClass, isActive ? actionActive : actionIdle, disabled && onNewResearch && "pointer-events-none opacity-50")}>
        <Plus className="size-4 shrink-0" />新建研究
      </NavLink>
      <NavLink to="/comparison" onClick={closeMobile}
        className={({ isActive }) => cn(actionClass, isActive ? actionActive : actionIdle)}>
        <FileSearch className="size-4 shrink-0" />实验结果对照
      </NavLink>
    </nav>
    <nav aria-label="工作区常用功能" className="mt-4 shrink-0 space-y-1 border-t border-slate-200/70 pt-3">
      {[
        { path: "/sources", label: "资料库", icon: Database },
        { path: "/settings", label: "模型预设", icon: KeyRound },
        { path: "/usage", label: "Token 用量", icon: BarChart3 },
        { path: "/guide", label: "使用说明", icon: BookOpen },
        ...(isAdmin ? [{ path: "/admin", label: "用户管理", icon: ShieldCheck }] : []),
      ].map(({ path, label, icon: Icon }) => <NavLink
        key={path} to={path} onClick={closeMobile}
        className={({ isActive }) => cn(sectionLink, isActive
          ? "bg-blue-50 font-medium text-blue-700"
          : "text-slate-600 hover:bg-white hover:text-slate-900")}
      ><Icon className="size-4 shrink-0" />{label}</NavLink>)}
    </nav>
  </>;
}
