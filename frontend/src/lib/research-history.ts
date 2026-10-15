import type { Message, ResearchRun } from "@/lib/types";

/** Restore interrupted runs without treating them as a completed assistant answer. */
export function restoreResearchHistory(history: Message[], runs: ResearchRun[]): Message[] {
  const byId = new Map(runs.map((run) => [run.id, run]));
  const answered = new Set(history.filter((message) => message.role === "assistant" && message.run_id).map((message) => message.run_id));
  const restored: Message[] = [];
  for (const message of history) {
    restored.push({ ...message, sources: message.sources ?? [], events: message.events ?? [] });
    const run = message.role === "user" && message.run_id ? byId.get(message.run_id) : undefined;
    if (!run || answered.has(run.id)) continue;
    restored.push({
      id: -(restored.length + 1), role: "assistant", content: "", run_id: run.id,
      provider_id: run.provider_id, provider_name: run.provider_name, model: run.model,
      sources: run.sources ?? [], events: run.events ?? [], usage: run.usage,
      total_tokens: run.usage?.total_tokens ?? 0,
      status: run.status === "completed" ? "failed" : run.status,
      error: run.status === "completed" ? "研究已结束，但本次读取未找到对应报告，请重新加载历史。" : run.error,
      created_at: run.finished_at || run.created_at,
    });
    answered.add(run.id);
  }
  return restored;
}
