import { ArrowUp, Check, ChevronDown, FileText, Globe2, Plus, Square, X } from "lucide-react";
import { useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import type { Provider, ResearchMode, SourceDocument } from "@/lib/types";
import { cn } from "@/lib/utils";

type Props = {
  value: string;
  documents: SourceDocument[];
  providers: Provider[];
  selectedProviderId?: number;
  selectedDocs: number[];
  webSearch: boolean;
  mode: ResearchMode;
  busy: boolean;
  disabled?: boolean;
  spacious?: boolean;
  onChange: (value: string) => void;
  onToggleDocument: (id: number) => void;
  onToggleWeb: () => void;
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
      <div className="rounded-[20px] border border-slate-200 bg-white p-4 shadow-[0_4px_24px_rgba(15,23,42,0.04)] transition focus-within:border-blue-300 focus-within:shadow-[0_4px_24px_rgba(37,99,235,0.06)] sm:px-5">
        <label htmlFor="research-question" className="sr-only">{props.mode === "deep" ? "研究问题" : "问答问题"}</label>
        <textarea ref={textarea} id="research-question" value={props.value} disabled={locked} onChange={(event) => props.onChange(event.target.value)} onKeyDown={keyDown} rows={props.spacious ? 4 : 2} maxLength={20000} placeholder={props.mode === "deep" ? "你想深入研究什么？描述目标、范围和你期待的成果…" : "有什么想了解的？"} className="max-h-[min(28dvh,240px)] w-full resize-y border-0 bg-transparent px-1 text-[15px] leading-7 text-slate-900 outline-none placeholder:text-slate-400 disabled:opacity-60 sm:text-base" />

        {props.selectedDocs.length > 0 && <div className="mb-3 flex flex-wrap gap-1.5">
          {available.filter((doc) => props.selectedDocs.includes(doc.id)).map((doc) => <button key={doc.id} type="button" disabled={locked} onClick={() => props.onToggleDocument(doc.id)} title="移除资料" className="inline-flex max-w-48 items-center gap-1.5 rounded-lg bg-blue-50 px-2 py-1 text-xs text-blue-700"><FileText className="size-3 shrink-0" /><span className="truncate">{doc.filename}</span><X className="size-3 shrink-0" /></button>)}
        </div>}

        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-3">
          <button type="button" disabled={locked} aria-pressed={props.webSearch} title="使用所选模型提供方的官方联网搜索" onClick={props.onToggleWeb} className={cn("control-chip", props.webSearch ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-500")}><Globe2 className="size-4" />联网搜索{props.webSearch && <Check className="size-3" />}</button>
          <button type="button" disabled={locked} aria-expanded={showDocuments} onClick={() => setShowDocuments((value) => !value)} className={cn("control-chip", props.selectedDocs.length ? "border-blue-200 bg-blue-50 text-blue-700" : "border-slate-200 text-slate-500")}><FileText className="size-4" />资料{props.selectedDocs.length ? ` · ${props.selectedDocs.length}` : ""}<ChevronDown className="size-3" /></button>
          <div className="ml-auto flex min-w-0 items-center gap-2">
            {props.providers.length ? <select disabled={locked} aria-label="选择模型预设" value={props.selectedProviderId ?? ""} onChange={(event) => props.onSelectProvider(Number(event.target.value))} className="h-9 max-w-[145px] truncate rounded-lg border-0 bg-slate-50 px-2 text-xs font-medium text-slate-600 outline-none focus:ring-2 focus:ring-blue-300 sm:max-w-[250px]">
              <option value="" disabled>选择模型预设</option>
              {props.providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name} · {provider.model}</option>)}
            </select> : <button type="button" onClick={props.onConfigureProviders} className="control-chip border-amber-200 bg-amber-50 text-amber-800"><Plus className="size-4" />添加模型</button>}
            {props.busy ? <button type="button" onClick={props.onStop} className="grid size-10 shrink-0 place-items-center rounded-xl bg-slate-900 text-white hover:bg-slate-700" aria-label={props.mode === "deep" ? "停止研究" : "停止回答"} title={props.mode === "deep" ? "停止研究" : "停止回答"}><Square className="size-4 fill-current" /></button> : <button type="submit" disabled={props.disabled || !props.value.trim() || !props.selectedProviderId} className="grid size-10 shrink-0 place-items-center rounded-xl bg-blue-600 text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400" aria-label={props.mode === "deep" ? "开始研究" : "发送问题"}><ArrowUp className="size-5" /></button>}
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

      <div className="mt-2 flex justify-end px-1">
        <span className="hidden shrink-0 text-[11px] text-slate-400 sm:inline">Enter 发送 · Shift + Enter 换行</span>
      </div>
    </form>
  );
}
