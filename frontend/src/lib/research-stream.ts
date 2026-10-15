import { streamSse } from "@/lib/api";
import type { ReasoningEffort, ResearchEvent, ResearchMode, ResearchSource, TokenUsage } from "@/lib/types";

export type ResearchStreamPayload = {
  question: string;
  provider_id: number;
  conversation_id: number | null;
  document_ids: number[];
  web_search: boolean;
  deep_thinking: boolean;
  reasoning_effort: ReasoningEffort;
  mode: ResearchMode;
  max_agents: number;
  max_depth: number;
};

export type ResearchCompletion = {
  conversation_id: number;
  provider_id?: number;
  saved: boolean;
  usage: TokenUsage;
  sources: ResearchSource[];
  run_id?: string;
};

type Callbacks = {
  onMeta: (conversationId: number) => void;
  onDelta: (delta: string) => void;
  onEvent: (event: ResearchEvent) => void;
  onDone: (completion: ResearchCompletion) => void;
};

export async function runResearchStream(payload: ResearchStreamPayload, callbacks: Callbacks, signal: AbortSignal): Promise<void> {
  let completed = false;
  await streamSse("/research/ask/stream", payload, (event) => {
    if (event.type === "meta") {
      const id = Number(event.data.conversation_id);
      if (Number.isFinite(id)) callbacks.onMeta(id);
    } else if (event.type === "content") {
      callbacks.onDelta(String(event.data.delta ?? ""));
    } else if (event.type === "done") {
      completed = true;
      callbacks.onDone({
        conversation_id: Number(event.data.conversation_id),
        provider_id: event.data.provider_id ? Number(event.data.provider_id) : undefined,
        saved: event.data.saved !== false,
        usage: (event.data.usage || { input_tokens: 0, output_tokens: 0, total_tokens: 0 }) as TokenUsage,
        sources: Array.isArray(event.data.sources) ? event.data.sources as ResearchSource[] : [],
        run_id: event.data.run_id ? String(event.data.run_id) : undefined,
      });
    } else if (event.type === "error") {
      throw new Error(String(event.data.message || "研究请求失败，请检查模型设置后重试"));
    } else if (["plan", "agent", "progress", "search"].includes(event.type)) {
      callbacks.onEvent(event);
    }
    // Private reasoning is never rendered. Legacy thinking is read only from saved history.
  }, signal);
  if (!completed) {
    if (signal.aborted) throw new DOMException("研究已停止", "AbortError");
    throw new Error("连接已中断，当前结果尚未保存。可复制已有内容并重新研究。");
  }
}
