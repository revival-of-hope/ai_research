import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { WorkspaceHistory } from "@/components/shell/workspace-history";
import { api } from "@/lib/api";
import type { Conversation } from "@/lib/types";

export function WorkspaceHistoryPanel({ onNavigate, busy = false }: { onNavigate?: () => void; busy?: boolean }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const active = conversations.find((item) => item.kind === "comparison" && item.comparison_id === Number(params.get("comparison")));
  const load = useCallback(async () => {
    try { setConversations(await api<Conversation[]>("/research/conversations")); setError(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "研究历史加载失败"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    void load();
    const refresh = () => { void load(); };
    window.addEventListener("research-history-changed", refresh);
    return () => window.removeEventListener("research-history-changed", refresh);
  }, [load]);

  return <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
    <WorkspaceHistory conversations={conversations} activeId={active?.id} loading={loading} busy={busy}
      onOpen={(id) => {
        const item = conversations.find((conversation) => conversation.id === id);
        navigate(item?.kind === "comparison" && item.comparison_id
          ? `/research/comparisons?comparison=${item.comparison_id}`
          : `/research?conversation=${id}`);
        onNavigate?.();
      }}
      onRename={async (id, title) => {
        await api(`/research/conversations/${id}`, { method: "PATCH", body: JSON.stringify({ title }) });
        await load();
      }}
      onDelete={async (id) => {
        await api(`/research/conversations/${id}`, { method: "DELETE" });
        const deleted = conversations.find((item) => item.id === id);
        window.dispatchEvent(new CustomEvent("research-record-deleted", {
          detail: { conversationId: id, comparisonId: deleted?.comparison_id ?? null },
        }));
        if (active?.id === id) {
          navigate("/research/comparisons", { replace: true });
          onNavigate?.();
        }
        window.dispatchEvent(new Event("research-history-changed"));
      }} />
    {error && <div role="alert" className="px-2 pb-3 text-xs leading-5 text-red-700">{error}<button className="ml-2 underline" onClick={() => void load()}>重试</button></div>}
  </div>;
}
