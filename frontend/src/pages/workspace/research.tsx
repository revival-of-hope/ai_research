import { useCallback, useState } from "react";

import { ResearchComposer } from "@/components/research/research-composer";
import { ResearchSidebar } from "@/components/research/research-sidebar";
import { ResearchWorkspace } from "@/components/research/research-workspace";
import { SettingsDialog, type SettingsSection } from "@/components/settings/settings-dialog";
import { useAuth } from "@/lib/auth";
import { useResearch } from "@/lib/use-research";

export function ResearchPage() {
  const { user, logout } = useAuth();
  const research = useResearch(user?.id);
  const [settingsSection, setSettingsSection] = useState<SettingsSection>();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dismissedError, setDismissedError] = useState("");
  const [pageError, setPageError] = useState("");
  const closeSettings = useCallback(() => setSettingsSection(undefined), []);
  const closeMobile = useCallback(() => setMobileOpen(false), []);
  const error = pageError || research.error;
  const title = research.conversations.find((item) => item.id === research.conversationId)?.title;

  function fillQuestion(value: string) {
    research.setQuestion(value);
    requestAnimationFrame(() => document.getElementById("research-question")?.focus());
  }

  const composer = <ResearchComposer value={research.question} documents={research.documents} providers={research.providers.filter((item) => item.compatible)} selectedProviderId={research.selectedProviderId} selectedDocs={research.selectedDocs} webSearch={research.webSearch} mode={research.mode} maxAgents={research.maxAgents} maxDepth={research.maxDepth} busy={research.busy} disabled={research.loading || research.historyLoading} spacious={!research.messages.length} onChange={research.setQuestion} onToggleDocument={research.toggleDocument} onToggleWeb={() => research.setWebSearch((value) => !value)} onModeChange={research.setMode} onMaxAgentsChange={research.setMaxAgents} onMaxDepthChange={research.setMaxDepth} onSelectProvider={research.selectProvider} onConfigureProviders={() => setSettingsSection("providers")} onOpenSources={() => setSettingsSection("sources")} onSubmit={() => { setPageError(""); setDismissedError(""); void research.submit(); }} onStop={research.stop} />;

  return <div className="flex h-dvh overflow-hidden bg-white text-slate-950">
    <ResearchSidebar conversations={research.conversations} activeId={research.conversationId} email={user?.email} isAdmin={user?.is_admin} busy={research.busy} loading={research.loading} mobileOpen={mobileOpen} onCloseMobile={closeMobile} onNew={research.newConversation} onOpen={(id) => void research.openConversation(id)} onRename={research.renameConversation} onDelete={research.deleteConversation} onOpenSettings={setSettingsSection} onLogout={() => { void logout().catch((reason) => setPageError(reason instanceof Error ? reason.message : "退出登录失败")); }} />
    <ResearchWorkspace composer={composer} messages={research.messages} busy={research.busy} loading={research.loading} historyLoading={research.historyLoading} title={title} mode={research.mode} error={error === dismissedError ? "" : error} canRecover={!!research.lastQuestion} onSuggestion={(value) => { research.setMode("deep"); fillQuestion(value); }} onOpenMenu={() => setMobileOpen(true)} onOpenSources={() => setSettingsSection("sources")} onOpenProviders={() => setSettingsSection("providers")} onRetryLoad={() => { setDismissedError(""); setPageError(""); void research.loadWorkspace(); }} onRecover={() => fillQuestion(research.lastQuestion)} onEditQuestion={fillQuestion} onDismissError={() => setDismissedError(error)} />
    {settingsSection && <SettingsDialog section={settingsSection} providers={research.providers} onSectionChange={setSettingsSection} onProvidersChanged={research.loadProviders} onDocumentsChanged={() => { void research.loadDocuments().catch((reason) => setPageError(reason instanceof Error ? reason.message : "资料加载失败")); }} onClose={closeSettings} />}
  </div>;
}
