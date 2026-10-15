import { BookOpen, CircleHelp, Database, LogOut, Settings, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";


const baseItems = [
  { to: "/research", label: "研究助手", icon: BookOpen },
  { to: "/sources", label: "资料库", icon: Database },
  { to: "/settings", label: "设置", icon: Settings },
  { to: "/guide", label: "使用说明", icon: CircleHelp },
];

export function AppShell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [error, setError] = useState("");
  if (location.pathname === "/research") return <Outlet />;
  const items = user?.is_admin
    ? [...baseItems, { to: "/admin", label: "用户管理", icon: ShieldCheck }]
    : baseItems;
  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-slate-200 bg-[#f7f8fa] p-5 lg:block">
        <div className="mb-8">
          <div className="flex items-center gap-2.5 text-lg font-semibold tracking-tight"><span className="grid size-8 place-items-center rounded-xl bg-blue-600 text-white"><Sparkles className="size-4" /></span>Research AI</div>
          <div className="mt-3 px-1 text-xs text-slate-400">研究工作台</div>
        </div>
        <nav className="space-y-1">
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) => cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium",
                isActive ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-100",
              )}
            >
              <Icon className="size-4" />{label}
            </NavLink>
          ))}
        </nav>
        <div className="absolute inset-x-5 bottom-5 border-t border-slate-100 pt-4">
          <div className="truncate text-xs text-slate-500">{user?.email}</div>
          <Button variant="ghost" className="mt-2 w-full justify-start" onClick={() => { void logout().catch((reason) => setError(reason instanceof Error ? reason.message : "退出失败")); }}>
            <LogOut className="size-4" />退出登录
          </Button>
        </div>
      </aside>
      <header className="sticky top-0 z-10 flex flex-col gap-2 border-b border-slate-200 bg-white px-4 py-3 lg:hidden">
        <div className="flex w-full items-center justify-between"><span className="flex items-center gap-2 text-sm font-semibold"><Sparkles className="size-4 text-blue-600" />Research AI</span><button onClick={() => { void logout().catch((reason) => setError(reason instanceof Error ? reason.message : "退出失败")); }} className="rounded-lg p-1.5 text-slate-400" aria-label="退出登录"><LogOut className="size-4" /></button></div>
        <nav className="flex w-full gap-1 overflow-x-auto">
          {items.map(({ to, label }) => <NavLink key={to} to={to} className="px-2 py-1 text-xs text-slate-600">{label}</NavLink>)}
        </nav>
      </header>
      <main className="mx-auto max-w-7xl p-4 sm:p-8 lg:ml-64">
        {error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-xs text-red-600">{error}</p>}
        <Outlet />
      </main>
    </div>
  );
}
