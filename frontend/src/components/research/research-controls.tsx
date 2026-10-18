import { BookOpen, Check, GitBranch, MessageSquareText, Settings2, Users } from "lucide-react";

import type { ResearchMode } from "@/lib/types";
import { cn } from "@/lib/utils";

export type ResearchControlsProps = {
  mode: ResearchMode;
  maxAgents: number;
  maxDepth: number;
  disabled: boolean;
  onModeChange: (mode: ResearchMode) => void;
  onMaxAgentsChange: (count: number) => void;
  onMaxDepthChange: (depth: number) => void;
};

export function ResearchControls(props: ResearchControlsProps) {
  return <section aria-label="研究模式与设置" className="mt-4 shrink-0 rounded-2xl border border-slate-200/80 bg-white p-2 shadow-xs">
    <p className="px-2 pb-2 pt-1 text-[10px] font-semibold tracking-wider text-slate-400">回答模式</p>
    <div className="space-y-1" role="group" aria-label="回答模式">
      {([
        { id: "deep", title: "深度研究", detail: "多智能体协作", icon: BookOpen },
        { id: "quick", title: "快速问答", detail: "单模型直接回答", icon: MessageSquareText },
      ] as const).map(({ id, title, detail, icon: Icon }) => <button
        key={id} type="button" aria-pressed={props.mode === id} disabled={props.disabled}
        onClick={() => props.onModeChange(id)}
        className={cn("flex w-full items-center gap-2.5 rounded-xl px-2.5 py-2 text-left transition disabled:opacity-50", props.mode === id ? "bg-blue-50 text-blue-700" : "text-slate-500 hover:bg-slate-50 hover:text-slate-800")}
      >
        <span className={cn("grid size-8 shrink-0 place-items-center rounded-lg", props.mode === id ? "bg-white text-blue-600 shadow-xs" : "bg-slate-50 text-slate-400")}><Icon className="size-4" /></span>
        <span className="min-w-0 flex-1"><span className="block text-xs font-semibold">{title}</span><span className="mt-0.5 block text-[10px] font-normal text-slate-400">{detail}</span></span>
        {props.mode === id && <Check className="size-3.5 shrink-0" />}
      </button>)}
    </div>
    {props.mode === "deep" ? <fieldset disabled={props.disabled} aria-label="深度研究设置" className="mx-1 mt-3 space-y-2 border-t border-slate-100 pb-1 pt-3">
      <legend className="sr-only">深度研究设置</legend>
      <p className="mb-2 flex items-center gap-1.5 px-1 text-[11px] font-semibold text-slate-600"><Settings2 className="size-3" />深度研究设置</p>
      <label className="flex items-center justify-between gap-2 px-1 text-[11px] text-slate-500"><span className="flex items-center gap-2"><Users className="size-3.5 text-slate-400" />协作智能体</span>
        <select aria-label="最大智能体数" value={props.maxAgents} onChange={(event) => props.onMaxAgentsChange(Number(event.target.value))} className="h-8 w-[84px] rounded-lg border border-slate-200 bg-slate-50/70 px-2 text-xs font-medium text-slate-700 outline-none focus:ring-2 focus:ring-blue-200 disabled:opacity-50">{[1, 2, 3, 4, 5, 6].map((count) => <option key={count} value={count}>{count} 个</option>)}</select>
      </label>
      <label className="flex items-center justify-between gap-2 px-1 text-[11px] text-slate-500"><span className="flex items-center gap-2"><GitBranch className="size-3.5 text-slate-400" />派生层级</span>
        <select aria-label="子智能体最大派生层级" value={props.maxDepth} onChange={(event) => props.onMaxDepthChange(Number(event.target.value))} className="h-8 w-[84px] rounded-lg border border-slate-200 bg-slate-50/70 px-2 text-xs font-medium text-slate-700 outline-none focus:ring-2 focus:ring-blue-200 disabled:opacity-50"><option value={0}>关闭派生</option><option value={1}>1 层</option><option value={2}>2 层</option></select>
      </label>
    </fieldset> : <p className="mx-2 mt-3 border-t border-slate-100 pb-1 pt-3 text-[10px] leading-5 text-slate-400">由所选模型直接回答，按需使用联网搜索和资料。</p>}
  </section>;
}
