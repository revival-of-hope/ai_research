import { Layers3, MessageSquareText, ScanLine } from "lucide-react";
import { Link } from "react-router-dom";

import type { ResearchMode } from "@/lib/types";
import { cn } from "@/lib/utils";

type Props = {
  task: ResearchMode | "comparison";
  onModeChange?: (mode: ResearchMode) => void;
  disabled?: boolean;
};

const tasks = [
  { id: "quick", title: "快速问答", detail: "直接解答，随时追问", icon: MessageSquareText, href: "/research?mode=quick" },
  { id: "deep", title: "深度研究", detail: "协作探索，追溯来源", icon: Layers3, href: "/research?mode=deep" },
  { id: "comparison", title: "实验核验", detail: "对照论文，逐项复核", icon: ScanLine, href: "/research/comparisons" },
] as const;

export function ResearchTaskNavigation({ task, onModeChange, disabled }: Props) {
  return <nav aria-label="选择研究任务" className="grid grid-cols-3 gap-1 rounded-2xl border border-slate-200 bg-slate-50/80 p-1.5">
    {tasks.map(({ id, title, detail, icon: Icon, href }) => {
      const active = task === id;
      const className = cn("flex min-w-0 items-center justify-center gap-2 rounded-xl px-2 py-3 text-left text-slate-500 transition-colors sm:justify-start sm:px-4", active ? "bg-white text-blue-700 shadow-xs ring-1 ring-slate-200/70" : "hover:bg-white hover:text-slate-800", disabled && "pointer-events-none opacity-50");
      const content = <><Icon className="size-4 shrink-0 sm:size-5" /><span><span className="block text-xs font-semibold sm:text-sm">{title}</span><span className="mt-1 hidden text-[11px] font-normal text-slate-500 sm:block">{detail}</span></span></>;
      return id !== "comparison" && onModeChange
        ? <button key={id} type="button" disabled={disabled} aria-pressed={active} onClick={() => onModeChange(id)} className={className}>{content}</button>
        : <Link key={id} to={href} aria-current={active ? "page" : undefined} aria-disabled={disabled} tabIndex={disabled ? -1 : undefined} className={className}>{content}</Link>;
    })}
  </nav>;
}
