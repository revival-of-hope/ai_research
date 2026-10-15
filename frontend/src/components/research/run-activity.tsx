import { Check, ChevronDown, Circle, CircleAlert, GitBranch, ListChecks, LoaderCircle, Search, Square } from "lucide-react";

import type { Message, PlanStep, ResearchAgent } from "@/lib/types";

export function RunActivity({ message, active }: { message: Message; active: boolean }) {
  const events = message.events ?? [];
  const planEvent = [...events].reverse().find((event) => event.type === "plan");
  const steps = (Array.isArray(planEvent?.data.steps) ? planEvent.data.steps : []) as PlanStep[];
  const agents = new Map<string, ResearchAgent>();
  for (const event of events) {
    if (event.type !== "agent" || !event.data.id) continue;
    const agent = event.data as unknown as ResearchAgent;
    agents.set(agent.id, { ...agents.get(agent.id), ...agent });
  }
  const progress = events.filter((event) => event.type === "progress" && event.data.message).slice(-4);
  const lastProgress = progress.at(-1);
  const searchEvent = [...events].reverse().find((event) => event.type === "search");
  const searching = active && ["searching", "started"].includes(String(searchEvent?.data.status));
  const completed = [...agents.values()].filter((agent) => agent.status === "completed").length;
  const stopped = message.status === "cancelled";
  const failed = message.status === "failed";
  if (!events.length && !active) return null;

  function renderAgent(agent: ResearchAgent, parents: string[] = []) {
    if (parents.includes(agent.id)) return null;
    const children = [...agents.values()].filter((child) => child.parent_id === agent.id && !parents.includes(child.id));
    const running = agent.status === "running" && active;
    const interrupted = agent.status === "running" && !active;
    const Icon = agent.status === "completed" ? Check : agent.status === "failed" ? CircleAlert : running ? LoaderCircle : stopped ? Square : Circle;
    const status = agent.status === "completed" ? "完成" : agent.status === "failed" ? "失败" : running ? "进行中" : stopped ? "已停止" : message.status === "running" ? "未连接" : interrupted ? "已结束" : "等待中";
    return <li key={agent.id} className="min-w-0">
      <div className="flex items-start gap-2.5 py-2">
        <span className={"mt-0.5 grid size-6 shrink-0 place-items-center rounded-lg " + (agent.status === "failed" ? "bg-red-50 text-red-500" : agent.status === "completed" ? "bg-emerald-50 text-emerald-600" : "bg-blue-50 text-blue-600")}><Icon className={"size-3.5 " + (running ? "animate-spin" : "")} /></span>
        <div className="min-w-0 flex-1"><div className="flex items-center gap-2"><p className="text-xs font-semibold text-slate-700">{agent.name || "研究智能体"}</p><span className="text-[10px] text-slate-400">{status}</span></div><p className="mt-0.5 break-words text-xs leading-5 text-slate-500">{agent.task}</p>{agent.detail && <p className="mt-1 break-words text-[11px] leading-5 text-slate-400">{agent.detail}</p>}</div>
      </div>
      {children.length > 0 && <ul className="ml-3 border-l border-slate-200 pl-4">{children.map((child) => renderAgent(child, [...parents, agent.id]))}</ul>}
    </li>;
  }

  const roots = [...agents.values()].filter((agent) => !agent.parent_id || !agents.has(agent.parent_id));
  return <details className="mb-5 overflow-hidden rounded-2xl border border-slate-200 bg-slate-50/60" open={active || undefined}>
    <summary className="flex cursor-pointer list-none items-center gap-2.5 px-4 py-3 text-xs text-slate-600 [&::-webkit-details-marker]:hidden">
      {active ? <LoaderCircle className="size-4 animate-spin text-blue-600" /> : stopped ? <Square className="size-3.5 text-slate-400" /> : failed ? <CircleAlert className="size-4 text-amber-600" /> : <ListChecks className="size-4 text-blue-600" />}
      <span className="font-medium">{active ? "研究进行中" : stopped ? "研究已停止" : failed ? "研究运行记录" : "查看研究过程"}</span>
      {agents.size > 0 && <span className="rounded-md bg-white px-1.5 py-0.5 text-[10px] text-slate-400">{completed}/{agents.size} 智能体完成</span>}
      <ChevronDown className="ml-auto size-3.5 shrink-0 text-slate-400" />
    </summary>
    <div className="space-y-4 border-t border-slate-200/70 px-4 pb-4 pt-3">
      {!!steps.length && <section aria-label="研究计划"><p className="mb-2 text-[11px] font-semibold text-slate-500">研究计划</p><ol className="grid gap-2 sm:grid-cols-2">{steps.map((step, index) => <li key={step.id || index} className="flex items-start gap-2 text-xs leading-5 text-slate-600"><span className="grid size-5 shrink-0 place-items-center rounded-md border border-slate-200 bg-white text-[10px] font-medium text-slate-400">{index + 1}</span><span>{step.title}</span></li>)}</ol></section>}
      {agents.size > 0 && <section aria-label="协作智能体树"><p className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-500"><GitBranch className="size-3" />协作智能体</p><ul>{(roots.length ? roots : [...agents.values()].slice(0, 1)).map((agent) => renderAgent(agent))}</ul></section>}
      {progress.length > 0 && <div className="space-y-1 border-t border-slate-200/70 pt-3" aria-live={active ? "polite" : "off"}>{progress.map((event, index) => <p key={index} className={"flex items-start gap-2 text-[11px] leading-5 " + (event === lastProgress ? "text-slate-600" : "text-slate-400")}><span className="mt-2 size-1 shrink-0 rounded-full bg-current" />{String(event.data.message)}</p>)}</div>}
      {searching && <p className="flex items-center gap-2 text-xs text-blue-600"><Search className="size-3.5" />正在检索联网资料…</p>}
      {!events.length && active && <p className="text-xs text-slate-500">正在连接模型并准备研究…</p>}
    </div>
  </details>;
}
