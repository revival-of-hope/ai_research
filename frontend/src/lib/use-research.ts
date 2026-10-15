import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { runResearchStream } from "@/lib/research-stream";
import { restoreResearchHistory } from "@/lib/research-history";
import type { Conversation, Message, Provider, ReasoningEffort, ResearchMode, ResearchRun, SourceDocument } from "@/lib/types";

export function useResearch(userId?: number) {
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selectedProviderId, setSelectedProviderId] = useState<number>();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<number>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<number[]>([]);
  const [webSearch, setWebSearch] = useState(true);
  const [mode, setMode] = useState<ResearchMode>("deep");
  const [deepThinking, setDeepThinking] = useState(false);
  const [reasoningEffort, setReasoningEffort] = useState<ReasoningEffort>("medium");
  const [maxAgents, setMaxAgents] = useState(3);
  const [maxDepth, setMaxDepth] = useState(1);
  const [question, setQuestion] = useState("");
  const [lastQuestion, setLastQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  const historyVersion = useRef(0);
  const providerStorageKey = `research-provider-${userId ?? "current"}`;

  const loadProviders = useCallback(async (preferredId?: number) => {
    const saved = await api<Provider[]>("/account/providers");
    setProviders(saved);
    setSelectedProviderId((current) => {
      const available = saved.filter((item) => item.compatible);
      const candidate = preferredId || current || Number(localStorage.getItem(providerStorageKey));
      const next = available.some((item) => item.id === candidate) ? candidate : available[0]?.id;
      if (next) localStorage.setItem(providerStorageKey, String(next));
      return next;
    });
  }, [providerStorageKey]);

  const loadDocuments = useCallback(async () => {
    const saved = await api<SourceDocument[]>("/documents");
    setDocuments(saved);
    setSelectedDocs((current) => current.filter((id) => saved.some((doc) => doc.id === id && doc.status === "ready")));
  }, []);

  const loadConversations = useCallback(async () => {
    setConversations(await api<Conversation[]>("/research/conversations"));
  }, []);

  const loadWorkspace = useCallback(async () => {
    setLoading(true);
    setError("");
    const results = await Promise.allSettled([loadConversations(), loadDocuments(), loadProviders()]);
    const failed = results.find((result) => result.status === "rejected");
    if (failed?.status === "rejected") setError(failed.reason instanceof Error ? failed.reason.message : "工作区未能完整加载，请重试。");
    setLoading(false);
  }, [loadConversations, loadDocuments, loadProviders]);

  useEffect(() => { void loadWorkspace(); }, [loadWorkspace]);
  useEffect(() => () => { controller.current?.abort(); historyVersion.current += 1; }, []);

  async function openConversation(id: number) {
    if (controller.current) return;
    const version = ++historyVersion.current;
    setHistoryLoading(true);
    setError("");
    try {
      const [history, runs] = await Promise.all([
        api<Message[]>(`/research/conversations/${id}`),
        api<ResearchRun[]>(`/research/conversations/${id}/runs`),
      ]);
      if (version !== historyVersion.current) return;
      setConversationId(id);
      setMessages(restoreResearchHistory(history, runs));
      setQuestion("");
      setLastQuestion([...history].reverse().find((message) => message.role === "user")?.content || "");
    } catch (reason) {
      if (version === historyVersion.current) setError(reason instanceof Error ? reason.message : "会话加载失败");
    } finally {
      if (version === historyVersion.current) setHistoryLoading(false);
    }
  }

  function newConversation() {
    if (controller.current) return;
    historyVersion.current += 1;
    setHistoryLoading(false);
    setConversationId(undefined);
    setMessages([]);
    setError("");
    setQuestion("");
    setLastQuestion("");
  }

  async function renameConversation(id: number, title: string) {
    const clean = title.trim();
    if (!clean) throw new Error("请输入对话名称");
    const saved = await api<Conversation>(`/research/conversations/${id}`, { method: "PATCH", body: JSON.stringify({ title: clean }) });
    setConversations((current) => current.map((item) => item.id === id ? { ...item, title: saved?.title || clean } : item));
  }

  async function deleteConversation(id: number) {
    await api<void>(`/research/conversations/${id}`, { method: "DELETE" });
    setConversations((current) => current.filter((item) => item.id !== id));
    if (conversationId === id) newConversation();
  }

  function selectProvider(id: number) {
    setSelectedProviderId(id);
    localStorage.setItem(providerStorageKey, String(id));
  }

  async function submit(): Promise<void> {
    const content = question.trim();
    if (controller.current || historyLoading || !selectedProviderId) return;
    if (content.length < 2) { setError("请至少输入 2 个字符来描述你的问题。"); return; }
    const abort = new AbortController();
    controller.current = abort;
    const assistantId = -Date.now();
    let finalReceived = false;
    const provider = providers.find((item) => item.id === selectedProviderId);
    const updateAssistant = (update: (current: Message) => Message) => {
      setMessages((items) => items.map((item) => item.id === assistantId ? update(item) : item));
    };
    setBusy(true);
    setError("");
    setLastQuestion(content);
    setQuestion("");
    setMessages((items) => [...items,
      { role: "user", content },
      { id: assistantId, role: "assistant", content: "", sources: [], events: [], status: "running", provider_id: provider?.id, provider_name: provider?.name, model: provider?.model },
    ]);
    try {
      await runResearchStream({
        question: content,
        provider_id: selectedProviderId,
        conversation_id: conversationId ?? null,
        document_ids: selectedDocs,
        web_search: webSearch,
        deep_thinking: deepThinking,
        reasoning_effort: reasoningEffort,
        mode,
        max_agents: maxAgents,
        max_depth: maxDepth,
      }, {
        onMeta: setConversationId,
        onDelta: (delta) => updateAssistant((current) => ({ ...current, content: current.content + delta })),
        onEvent: (event) => updateAssistant((current) => {
          const sources = [...(current.sources ?? [])];
          if (event.type === "search" && Array.isArray(event.data.results)) {
            for (const source of event.data.results as NonNullable<Message["sources"]>) {
              if (!sources.some((item) => item.label === source.label)) sources.push(source);
            }
          }
          return { ...current, sources, events: [...(current.events ?? []), event] };
        }),
        onDone: (completion) => {
          finalReceived = true;
          setConversationId(completion.conversation_id);
          updateAssistant((current) => ({ ...current, total_tokens: completion.usage.total_tokens, usage: completion.usage, sources: completion.sources, run_id: completion.run_id, status: completion.saved ? "completed" : "failed" }));
          if (!completion.saved) setError("报告已生成，但保存失败。请先复制或导出报告，再重新加载对话。");
        },
      }, abort.signal);
    } catch (reason) {
      if (finalReceived) {
        // A terminal event has already recorded the final state; a later disconnect cannot undo it.
      } else if (abort.signal.aborted) {
        updateAssistant((current) => ({ ...current, status: "cancelled" }));
      } else {
        const message = reason instanceof Error ? reason.message : "研究请求失败";
        updateAssistant((current) => ({ ...current, status: "failed", error: message }));
        setError(message);
      }
    } finally {
      controller.current = null;
      setBusy(false);
      void loadConversations().catch(() => setError((current) => current || "历史列表刷新失败。请重新加载工作区。"));
    }
  }

  function stop() {
    controller.current?.abort();
  }

  return {
    documents, providers, selectedProviderId, conversations, conversationId, messages,
    selectedDocs, webSearch, mode, deepThinking, reasoningEffort, maxAgents, maxDepth, question,
    busy, loading, historyLoading, error, lastQuestion,
    setQuestion, setMode, setWebSearch, setDeepThinking, setReasoningEffort, setMaxAgents, setMaxDepth,
    toggleDocument: (id: number) => {
      if (selectedDocs.includes(id)) setSelectedDocs((current) => current.filter((item) => item !== id));
      else if (selectedDocs.length >= 30) setError("单次研究最多选择 30 份资料。");
      else setSelectedDocs((current) => [...current, id]);
    },
    selectProvider, submit, stop, newConversation, openConversation, renameConversation, deleteConversation,
    loadWorkspace, loadDocuments, loadProviders,
  };
}
