import { useRef } from "react";

import { ResearchControls, type ResearchControlsProps } from "@/components/research/research-controls";
import { WorkspaceAccount } from "@/components/shell/workspace-account";
import { WorkspaceNavigation } from "@/components/shell/workspace-navigation";
import type { SettingsSection } from "@/components/settings/settings-dialog";
import type { Conversation } from "@/lib/types";
import { useDialogFocus } from "@/lib/use-dialog-focus";
import { WorkspaceHistory } from "@/components/shell/workspace-history";

type Props = ResearchControlsProps & {
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
  const closeMobile = () => { if (props.mobile) props.onCloseMobile(); };
  function openSettings(section: SettingsSection) { closeMobile(); props.onOpenSettings(section); }

  return <>
    <WorkspaceNavigation
      isAdmin={props.isAdmin}
      mobile={props.mobile}
      onCloseMobile={props.onCloseMobile}
      onNewResearch={props.onNew}
      disabled={props.busy}
    />
    <div className="flex min-h-0 flex-1 flex-col overflow-y-auto overscroll-contain">
    <ResearchControls mode={props.mode} maxAgents={props.maxAgents} maxDepth={props.maxDepth} disabled={props.disabled} onModeChange={props.onModeChange} onMaxAgentsChange={props.onMaxAgentsChange} onMaxDepthChange={props.onMaxDepthChange} />
    <WorkspaceHistory conversations={props.conversations} activeId={props.activeId} busy={props.busy} loading={props.loading}
      onOpen={(id) => { props.onOpen(id); closeMobile(); }} onRename={props.onRename} onDelete={props.onDelete} />
    </div>
    <WorkspaceAccount
      email={props.email}
      isAdmin={props.isAdmin}
      busy={props.busy}
      onLogout={props.onLogout}
      onOpenSettings={openSettings}
      onNavigate={closeMobile}
    />
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
