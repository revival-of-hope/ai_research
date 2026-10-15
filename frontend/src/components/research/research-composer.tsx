import { ArrowUp, BookOpen, Check, ChevronDown, FileText, Globe2, MessageSquareText, Plus, Settings2, Square, X } from "lucide-react";
import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import type { Provider, ReasoningEffort, ResearchMode, SourceDocument } from "@/lib/types";
import { cn } from "@/lib/utils";

type Props = {
  value: string;
  documents: SourceDocument[];
  providers: Provider[];
  selectedProviderId?: number;
  selectedDocs: number[];
  webSearch: boolean;
  mode: ResearchMode;
  deepThinking: boolean;
  reasoningEffort: ReasoningEffort;
  maxAgents: number;
  maxDepth: number;
  busy: boolean;
  disabled?: boolean;
  spacious?: boolean;
  onChange: (value: string) => void;
  onToggleDocument: (id: number) => void;
  onToggleWeb: () => void;
  onModeChange: (mode: ResearchMode) => void;
  onToggleThinking: () => void;
  onReasoningEffortChange: (effort: ReasoningEffort) => void;
  onMaxAgentsChange: (count: number) => void;
  onMaxDepthChange: (depth: number) => void;
  onSelectProvider: (id: number) => void;
  onConfigureProviders: () => void;
  onOpenSources: () => void;
  onSubmit: () => void;
  onStop: () => void;
};

export function ResearchComposer(props: Props) {
  const [showDocuments, setShowDocuments] = useState(false);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const available = props.documents.filter((item) => item.status === "ready");
  const locked = props.busy || props.disabled;

  function submit(event: FormEvent) { event.preventDefault(); props.onSubmit(); }
  function keyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (!locked) props.onSubmit();
    }
  }

  return (
    <form onSubmit={submit} className="relative w-full">
      <div className="mb-4 flex items-center gap-1 rounded-2xl bg-slate-100/80 p-1 sm:w-fit" aria-label="回答模式">
        {([
          { id: "deep", title: "深度研究", detail: "多智能体协作", icon: BookOpen },
          { id: "quick", title: "快速问答", detail: "直接获取答案", icon: MessageSquareText },
        ] as const).map(({ id, title, detail, icon: Icon }) => (
          <button key={id} type="button" aria-pressed={props.mode === id} disabled={locked} onClick={() => props.onModeChange(id)} className={cn("flex flex-1 items-center gap-2.5 rounded-xl px-3 py-2 text-left transition disabled:opacity-60 sm:flex-none sm:px-4", props.mode === id ? "bg-white text-blue-700 shadow-sm" : "text-slate-500 hover:text-slate-800")}>
            <Icon className="size-4 shrink-0" />
            <span><span className="block text-sm font-semibold">{title}</span><span className="hidden text-[11px] font-normal text-slate-400 sm:block">{detail}</span></span>
          </button>
        ))}
      </div>

      <div className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-[0_8px_32px_rgba(15,23,42,0.06)] transition focus-within:border-blue-300 focus-within:shadow-[0_8px_32px_rgba(37,99,235,0.08)] sm:p-5">
        <label htmlFor="research-question" className="sr-only">研究问题</label>
        <textarea ref={textarea} id="research-question" value={props.value} disabled={locked} onChange={(event) => props.onChange(event.target.value)} onKeyDown={keyDown} rows={props.spacious ? 3 : 2} maxLength={20000} placeholder={props.mode === "deep" ? "你想深入研究什么？描述目标、范围和你期待的成果…" : "有什么想了解的？"} className="max-h-56 w-full resize-y border-0 bg-transparent px-1 text-[15px] leading-7 text-slate-900 outline-none placeholder:text-slate-400 disabled:opacity-60 sm:text-base" />

        {props.selectedDocs.length > 0 && <div className="mb-3 flex flex-wrap gap-1.5">
          {available.filter((doc) => props.selectedDocs.includes(doc.id)).map((doc) => <button key={doc.id} type="button" disabled={locked} onClick={() => props.onToggleDocument(doc.id)} title="移除资料" className="inline-flex max-w-48 items-center gap-1.5 rounded-lg bg-blue-50 px-2 py-1 text-xs text-blue-700"><FileText className="size-3 shrink-0" /><span className="truncate">{doc.filename}</span><X className="size-3 shrink-0" /></button>)}
        </div>}

        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
          <button type="button" disabled={locked} aria-pressed={props.webSearch} onClick={props.onToggleWeb} className={cn("control-chip", props.webSearch ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-500")}><Globe2 className="size-4" />联网搜索{props.webSearch && <Check className="size-3" />}</button>
          <button type="button" disabled={locked} aria-expanded={showDocuments} onClick={() => setShowDocuments((value) => !value)} className={cn("control-chip", props.selectedDocs.length ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-500")}><FileText className="size-4" />资料{props.selectedDocs.length ? ` · ${props.selectedDocs.length}` : ""}<ChevronDown className="size-3" /></button>
          <div className="ml-auto flex min-w-0 items-center gap-2">
            {props.providers.length ? <select disabled={locked} aria-label="选择模型预设" value={props.selectedProviderId ?? ""} onChange={(event) => props.onSelectProvider(Number(event.target.value))} className="h-9 max-w-[145px] truncate rounded-lg border-0 bg-slate-50 px-2 text-xs font-medium text-slate-600 outline-none focus:ring-2 focus:ring-blue-300 sm:max-w-[250px]">
              <option value="" disabled>选择模型预设</option>
              {props.providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name} · {provider.model}</option>)}
            </select> : <button type="button" onClick={props.onConfigureProviders} className="control-chip border-amber-200 bg-amber-50 text-amber-800"><Plus className="size-4" />添加模型</button>}
            {props.busy ? <button type="button" onClick={props.onStop} className="grid size-10 shrink-0 place-items-center rounded-xl bg-slate-900 text-white hover:bg-slate-700" aria-label="停止研究" title="停止研究"><Square className="size-4 fill-current" /></button> : <button type="submit" disabled={props.disabled || !props.value.trim() || !props.selectedProviderId} className="grid size-10 shrink-0 place-items-center rounded-xl bg-blue-600 text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400" aria-label={props.mode === "deep" ? "开始研究" : "发送问题"}><ArrowUp className="size-5" /></button>}
          </div>
        </div>

        {showDocuments && <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3">
          <div className="mb-2 flex items-center justify-between"><p className="text-xs font-semibold text-slate-600">本次使用的资料</p><button type="button" aria-label="关闭资料选择" onClick={() => setShowDocuments(false)} className="rounded p-1 text-slate-400 hover:bg-white"><X className="size-4" /></button></div>
          <div className="max-h-40 space-y-1 overflow-y-auto">
            {available.map((doc) => <label key={doc.id} className="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-2 text-sm hover:bg-white"><input type="checkbox" disabled={locked} checked={props.selectedDocs.includes(doc.id)} onChange={() => props.onToggleDocument(doc.id)} className="size-4 accent-blue-600" /><span className="truncate">{doc.filename}</span></label>)}
            {!available.length && <p className="py-2 text-xs leading-5 text-slate-500">暂无可用资料。上传文件后可基于自己的文档研究。</p>}
          </div>
          <button type="button" onClick={props.onOpenSources} className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-blue-700 hover:underline"><Plus className="size-3" />上传和管理资料</button>
        </div>}
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-1 text-xs text-slate-500">
        {props.mode === "deep" ? <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="inline-flex items-center gap-1.5 font-medium"><Settings2 className="size-3.5" />研究设置</span>
          <label className="flex items-center gap-1">协作智能体<select disabled={locked} aria-label="最大智能体数" value={props.maxAgents} onChange={(event) => props.onMaxAgentsChange(Number(event.target.value))} className="compact-select">{[1, 2, 3, 4, 5, 6].map((count) => <option key={count} value={count}>{count}</option>)}</select></label>
          <label className="flex items-center gap-1">派生层级<select disabled={locked} aria-label="子智能体最大派生层级" value={props.maxDepth} onChange={(event) => props.onMaxDepthChange(Number(event.target.value))} className="compact-select"><option value={0}>关闭</option><option value={1}>1 层</option><option value={2}>2 层</option></select></label>
        </div> : <span>快速回答，可结合联网搜索和本地资料。</span>}
        <div className="flex items-center gap-2" title="独立于多智能体协作，启用模型支持的推理强度参数"><label className="inline-flex items-center gap-1.5"><input type="checkbox" disabled={locked} checked={props.deepThinking} onChange={props.onToggleThinking} className="size-3 accent-blue-600" />模型推理</label><select disabled={locked || !props.deepThinking} aria-label="推理强度" value={props.reasoningEffort} onChange={(event) => props.onReasoningEffortChange(event.target.value as ReasoningEffort)} className="compact-select disabled:opacity-40"><option value="low">低强度</option><option value="medium">中强度</option><option value="high">高强度</option></select></div>
        <span className="hidden shrink-0 text-[11px] text-slate-400 sm:inline">Enter 发送 · Shift + Enter 换行</span>
      </div>
    </form>
  );
}
