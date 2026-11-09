import { Menu } from "lucide-react";
import { useRef, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { WorkspaceAccount } from "@/components/shell/workspace-account";
import { WorkspaceBreadcrumb } from "@/components/shell/workspace-breadcrumb";
import { WorkspaceNavigation } from "@/components/shell/workspace-navigation";
import { WorkspaceHistoryPanel } from "@/components/shell/workspace-history-panel";
import { useAuth } from "@/lib/auth";
import { useDialogFocus } from "@/lib/use-dialog-focus";

function MobileNavigation({
  isAdmin, email, onLogout, onClose, busy,
}: {
  isAdmin?: boolean;
  email?: string;
  onLogout: () => void;
  onClose: () => void;
  busy: boolean;
}) {
  const root = useRef<HTMLDivElement>(null);
  useDialogFocus(root, onClose);
  return <div className="fixed inset-0 z-40 lg:hidden">
    <div className="absolute inset-0 bg-slate-950/25 backdrop-blur-[2px]" onClick={onClose} />
    <div ref={root} role="dialog" aria-modal="true" aria-labelledby="mobile-workspace-label"
      className="relative flex h-dvh w-[min(300px,88vw)] flex-col border-r border-slate-200 bg-[#f7f8fa] p-4 shadow-xl">
      <WorkspaceNavigation mobile isAdmin={isAdmin} onCloseMobile={onClose} />
      <WorkspaceHistoryPanel onNavigate={onClose} busy={busy} />
      <WorkspaceAccount email={email} isAdmin={isAdmin} onLogout={onLogout} onNavigate={onClose} />
    </div>
  </div>;
}

export function AppShell() {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [error, setError] = useState("");
  const [workspaceBusy, setWorkspaceBusy] = useState(false);
  const currentPage: Record<string, string> = {
    "/research/comparisons": "实验核验",
    "/sources": "资料库",
    "/settings": "模型预设",
    "/usage": "Token 用量",
    "/guide": "使用说明",
    "/admin": "用户管理",
  };

  // The research page owns its conversations and model controls, but shares
  // WorkspaceNavigation and WorkspaceAccount with every other workspace page.
  if (pathname === "/research") return <Outlet />;

  const handleLogout = () => {
    void logout().catch((reason) => setError(reason instanceof Error ? reason.message : "退出登录失败"));
  };

  return <div className="min-h-dvh bg-white text-slate-950">
    <aside aria-label="工作区导航" className="fixed inset-y-0 left-0 hidden w-[272px] flex-col border-r border-slate-200/70 bg-[#f7f8fa] p-4 lg:flex">
      <WorkspaceNavigation isAdmin={user?.is_admin} />
      <WorkspaceHistoryPanel busy={workspaceBusy} />
      <WorkspaceAccount email={user?.email} isAdmin={user?.is_admin} onLogout={handleLogout} />
    </aside>
    <div className="min-h-dvh lg:pl-[272px]">
      <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b border-slate-100 bg-white px-4 sm:px-7">
        <button type="button" onClick={() => setMobileOpen(true)} aria-label="打开工作区导航"
          className="-ml-1 rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"><Menu className="size-5" /></button>
        <WorkspaceBreadcrumb current={currentPage[pathname] || "工作台"} />
      </header>
      <main className="w-full px-4 py-6 sm:px-7 sm:py-8">
        {error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-xs text-red-600">{error}</p>}
        <Outlet context={{ setWorkspaceBusy }} />
      </main>
    </div>
    {mobileOpen && <MobileNavigation
      isAdmin={user?.is_admin} email={user?.email}
      onLogout={handleLogout} onClose={() => setMobileOpen(false)} busy={workspaceBusy}
    />}
  </div>;
}
