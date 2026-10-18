import { ArrowDown, ArrowUpRight, BookOpen, ChartNoAxesCombined, ChevronDown, ChevronRight, Database, FileSearch, LoaderCircle, Menu, RefreshCw, Settings2, Sparkles, X } from "lucide-react";
import { lazy, Suspense, useEffect, useRef, useState, type ReactNode } from "react";

import type { Message, ResearchMode } from "@/lib/types";

const MessageList = lazy(() => import("@/components/research/message-list").then((module) => ({ default: module.MessageList })));

const suggestions = [
  { title: "做一次深入调研", detail: "梳理现状、机会与关键争议", icon: FileSearch, prompt: "请调研 AI 研究智能体的主流产品与开源方案，比较它们的研究流程、来源可信度和适用场景，并提供带出处的选型建议。" },
  { title: "比较方案，辅助决策", detail: "有依据地比较不同选择", icon: ChartNoAxesCombined, prompt: "请比较模块化单体与微服务架构在一个 5 人团队、日活 1 万的 SaaS 产品中的适用性。按复杂度、运维成本、扩展性和迁移路径整理对比表，并给出建议。" },
  { title: "读懂资料，提炼观点", detail: "从你的文档中获得清晰结论", icon: BookOpen, prompt: "请基于我选择的资料，提炼核心观点、关键证据与尚未解决的问题。区分资料明确支持的结论和需要进一步验证的推断，并标出引用。" },
];

type Props = {
  composer: ReactNode;
  messages: Message[];
  busy: boolean;
  loading: boolean;
  historyLoading: boolean;
  title?: string;
  mode: ResearchMode;
  error: string;
  canRecover: boolean;
  onSuggestion: (question: string) => void;
  onOpenMenu: () => void;
  onOpenSources: () => void;
  onOpenProviders: () => void;
  onRetryLoad: () => void;
  onRecover: () => void;
  onEditQuestion: (question: string) => void;
  onDismissError: () => void;
};

export function ResearchWorkspace(props: Props) {
  const scroll = useRef<HTMLDivElement>(null);
  const autoFollow = useRef(true);
  const [atBottom, setAtBottom] = useState(true);
  const empty = props.messages.length === 0;

  useEffect(() => { autoFollow.current = true; setAtBottom(true); scroll.current?.scrollTo({ top: scroll.current.scrollHeight }); }, [props.messages.length]);
  useEffect(() => { if (autoFollow.current) scroll.current?.scrollTo({ top: scroll.current.scrollHeight }); }, [props.messages]);

  const error = props.error && <div role="alert" className="research-content flex items-start gap-3 rounded-xl border border-red-100 bg-red-50/70 px-4 py-3 text-xs text-red-700">
    <div className="min-w-0 flex-1"><p className="break-words leading-6">{props.error}</p><div className="mt-1 flex flex-wrap gap-4">{props.canRecover && <button disabled={props.busy} onClick={props.onRecover} className="font-medium underline underline-offset-4 disabled:opacity-50">编辑问题后重试</button>}<button disabled={props.busy} onClick={props.onRetryLoad} className="inline-flex items-center gap-1 font-medium underline underline-offset-4 disabled:opacity-50"><RefreshCw className="size-3" />重新加载工作区</button><button onClick={props.onOpenProviders} className="font-medium underline underline-offset-4">检查模型设置</button></div></div><button onClick={props.onDismissError} aria-label="关闭错误提示" className="mt-0.5 rounded p-1 text-red-400 hover:bg-red-100"><X className="size-3.5" /></button>
  </div>;

  return <main className="relative flex min-w-0 flex-1 flex-col bg-white">
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-slate-100 px-4 sm:px-7">
      <button onClick={props.onOpenMenu} aria-label="打开导航、研究设置和历史记录" className="-ml-1 rounded-lg p-2 text-slate-500 hover:bg-slate-100 lg:hidden"><Menu className="size-5" /></button>
      <div className="flex min-w-0 items-center gap-2 text-xs"><span className="hidden text-slate-400 sm:inline">工作区</span><ChevronRight className="hidden size-3 text-slate-300 sm:inline" /><h1 className="truncate font-medium text-slate-700">{props.title || (props.mode === "deep" ? "新的研究" : "新的问答")}</h1><span className="hidden shrink-0 rounded-md border border-slate-100 px-1.5 py-0.5 text-[10px] text-slate-400 lg:inline">{props.mode === "deep" ? "深度研究" : "快速问答"}</span></div>
      <button onClick={props.onOpenMenu} aria-label="打开研究模式与设置" className="flex shrink-0 items-center gap-1 rounded-lg bg-blue-50 px-2 py-1.5 text-[10px] font-medium text-blue-700 lg:hidden">{props.mode === "deep" ? "深度研究" : "快速问答"}<ChevronDown className="size-3" /></button>
      <div className="ml-auto flex shrink-0 items-center gap-1"><button onClick={props.onOpenSources} title="我的资料" aria-label="打开资料库" className="flex items-center gap-1.5 rounded-lg px-2 py-2 text-slate-500 hover:bg-slate-50"><Database className="size-4" /><span className="hidden text-xs sm:inline">资料库</span></button><button onClick={props.onOpenProviders} title="模型设置" aria-label="打开模型设置" className="rounded-lg p-2 text-slate-500 hover:bg-slate-50"><Settings2 className="size-4" /></button></div>
    </header>

    {props.historyLoading ? <div role="status" className="grid min-h-0 flex-1 place-items-center"><div className="flex items-center gap-2 text-sm text-slate-400"><LoaderCircle className="size-4 animate-spin" />正在读取对话记录…</div></div> : empty ? <div className="min-h-0 flex-1 overflow-y-auto px-4 py-8 sm:px-8 sm:py-14">
      <div className="research-content flex min-h-full flex-col justify-center pb-2 lg:pb-8">
        <div className="mb-8 text-center sm:mb-10"><div className="mb-5 inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50/60 px-3 py-1.5 text-[11px] font-medium text-blue-600"><Sparkles className="size-3" />{props.mode === "deep" ? "你的研究工作台" : "快速问答"}</div><h2 className="text-[27px] font-semibold tracking-tight text-slate-900 sm:text-[34px]">{props.mode === "deep" ? "把好问题，研究透。" : "有问题，直接聊。"}</h2><p className="mt-3 text-sm leading-6 text-slate-400">{props.mode === "deep" ? "让智能体协作探索，从联网信息和你的资料中整理有据可依的答案。" : "由你选择的模型直接回答，按需结合联网搜索与资料。"}</p></div>
        {props.composer}
        {props.loading && <p role="status" className="mt-4 flex items-center justify-center gap-2 text-xs text-slate-400"><LoaderCircle className="size-3 animate-spin" />正在载入模型和资料…</p>}
        {props.error && <div className="mt-5">{error}</div>}
        {props.mode === "deep" && <div className="mt-9 grid gap-3 sm:grid-cols-3">
          {suggestions.map(({ title, detail, prompt, icon: Icon }) => <button key={title} disabled={props.loading} onClick={() => props.onSuggestion(prompt)} className="group rounded-2xl border border-slate-200/80 bg-white p-4 text-left transition hover:border-blue-200 hover:bg-blue-50/20 disabled:opacity-50"><div className="flex items-center justify-between"><span className="grid size-8 place-items-center rounded-xl bg-slate-50 text-slate-500 transition group-hover:bg-blue-50 group-hover:text-blue-600"><Icon className="size-4" /></span><ArrowUpRight className="size-3.5 text-slate-300 group-hover:text-blue-500" /></div><p className="mt-3 text-xs font-semibold text-slate-700">{title}</p><p className="mt-1.5 text-[11px] leading-5 text-slate-400">{detail}</p></button>)}
        </div>}
        {props.mode === "deep" && <p className="mt-7 text-center text-[10px] tracking-wide text-slate-300">清晰计划<span className="px-2.5">·</span>智能体协作<span className="px-2.5">·</span>逐条来源引用</p>}
      </div>
    </div> : <>
      <div ref={scroll} aria-label="对话内容" onScroll={() => { const node = scroll.current; if (!node) return; const near = node.scrollHeight - node.scrollTop - node.clientHeight < 100; autoFollow.current = near; setAtBottom(near); }} className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <Suspense fallback={<p role="status" className="p-10 text-center text-xs text-slate-400">正在准备对话视图…</p>}><MessageList messages={props.messages} busy={props.busy} onEditQuestion={props.onEditQuestion} /></Suspense>
        {props.error && <div className="px-4 pb-7 sm:px-8">{error}</div>}
      </div>
      <div className="relative shrink-0 border-t border-slate-100 bg-white px-4 pb-4 pt-3 sm:px-8 sm:pb-5">
        {!atBottom && <button onClick={() => { autoFollow.current = true; setAtBottom(true); scroll.current?.scrollTo({ top: scroll.current.scrollHeight, behavior: "smooth" }); }} className="absolute -top-12 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 shadow-sm"><ArrowDown className="size-3.5" />回到最新</button>}
        <div className="research-content">{props.composer}</div>
      </div>
    </>}
  </main>;
}
