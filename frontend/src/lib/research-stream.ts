import { streamSse } from "@/lib/api";
import type { ResearchEvent, ResearchMode, ResearchSource, TokenUsage } from "@/lib/types";

export type ResearchStreamPayload = {
  question: string;
  provider_id: number;
  conversation_id: number | null;
  document_ids: number[];
  web_search: boolean;
  mode: ResearchMode;
  max_agents?: number;
  max_depth?: number;
};

export type ResearchCompletion = {
  conversation_id: number;
  provider_id?: number;
  saved: boolean;
  usage: TokenUsage;
  sources: ResearchSource[];
  run_id?: string;
  mode?: ResearchMode;
};

type Callbacks = {
  onMeta: (conversationId: number, mode?: ResearchMode) => void;
  onDelta: (delta: string) => void;
  onEvent: (event: ResearchEvent) => void;
  onDone: (completion: ResearchCompletion) => void;
};

export async function runResearchStream(payload: ResearchStreamPayload, callbacks: Callbacks, signal: AbortSignal): Promise<void> {
  let completed = false;
  let mode = payload.mode;
  await streamSse("/research/ask/stream", payload, (event) => {
    if (event.type === "meta") {
      if (event.data.mode === "quick" || event.data.mode === "deep") mode = event.data.mode;
      const id = Number(event.data.conversation_id);
      if (Number.isFinite(id)) callbacks.onMeta(id, mode);
    } else if (event.type === "content") {
      callbacks.onDelta(String(event.data.delta ?? ""));
    } else if (event.type === "done") {
      callbacks.onDone({
        conversation_id: Number(event.data.conversation_id),
        provider_id: event.data.provider_id ? Number(event.data.provider_id) : undefined,
        saved: event.data.saved !== false,
        usage: (event.data.usage || { input_tokens: 0, output_tokens: 0, total_tokens: 0 }) as TokenUsage,
        sources: Array.isArray(event.data.sources) ? event.data.sources as ResearchSource[] : [],
        run_id: event.data.run_id ? String(event.data.run_id) : undefined,
        mode: event.data.mode === "quick" || event.data.mode === "deep" ? event.data.mode : mode,
      });
      completed = true;
      return false;
    } else if (event.type === "error") {
      throw new Error(String(event.data.message || "回答请求失败，请检查模型设置后重试"));
    } else if (["plan", "agent", "progress", "search"].includes(event.type)) {
      if (mode !== "quick" || event.type === "search") callbacks.onEvent(event);
    }
    // Private reasoning is never rendered. Legacy thinking is read only from saved history.
  }, signal);
  if (!completed) {
    if (signal.aborted) throw new DOMException("回答已停止", "AbortError");
    throw new Error("连接已中断，当前结果尚未保存。请先复制已有内容，检查网络或服务状态后重新发送。");
  }
}
