import { Check, Copy, Download, ExternalLink, FileText, List, RotateCcw, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { RunActivity } from "@/components/research/run-activity";
import type { Message, ResearchSource } from "@/lib/types";

function httpUrl(value?: string | null) {
  try { const url = new URL(value || ""); return ["http:", "https:"].includes(url.protocol) ? url.href : undefined; }
  catch { return undefined; }
}

function sourceId(prefix: string, label: string) { return `${prefix}-${label.replace(/[^\p{L}\p{N}_-]/gu, "")}`; }

function linkCitations(content: string, sources: ResearchSource[], prefix: string) {
  // Leave fenced code and inline code untouched when making source labels navigable.
  return content.split(/(```[\s\S]*?```|`[^`]*`)/g).map((chunk, index) => {
    if (index % 2) return chunk;
    let next = chunk;
    for (const source of sources) {
      const label = source.label.replace(/^\[|\]$/g, "");
      const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      next = next.replace(new RegExp(`\\[${escaped}\\](?!\\()`, "g"), `[${label}](#${sourceId(prefix, source.label)})`);
    }
    return next;
  }).join("");
}

function AssistantMessage({ message, index, active, busy, onRetry }: { message: Message; index: number; active: boolean; busy: boolean; onRetry?: () => void }) {
  const [copied, setCopied] = useState(false);
  const [actionError, setActionError] = useState("");
  const report = useRef<HTMLDivElement>(null);
  const [headings, setHeadings] = useState<{ id: string; title: string; level: string }[]>([]);
  const sources = message.sources ?? [];
  const prefix = `sources-${index}`;
  useEffect(() => {
    const next = [...(report.current?.querySelectorAll<HTMLHeadingElement>("h1,h2,h3") ?? [])].map((heading, headingIndex) => {
      heading.id = `report-${index}-heading-${headingIndex}`;
      heading.style.scrollMarginTop = "20px";
      return { id: heading.id, title: heading.textContent || "", level: heading.tagName };
    });
    setHeadings((current) => JSON.stringify(current) === JSON.stringify(next) ? current : next);
  }, [index, message.content]);
  const exportText = message.content + (sources.length ? "\n\n## 来源\n\n" + sources.map((source) => `${source.label} ${source.title}${httpUrl(source.url) ? ` — ${httpUrl(source.url)}` : "（本地资料）"}`).join("\n\n") : "");

  async function copy() {
    try { await navigator.clipboard.writeText(exportText); setCopied(true); setActionError(""); window.setTimeout(() => setCopied(false), 2000); }
    catch { setActionError("复制失败，请选中报告文字复制，或下载 Markdown。"); }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([exportText], { type: "text/markdown;charset=utf-8" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `research-${new Date().toISOString().slice(0, 10)}-${index + 1}.md`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return <article className="flex gap-3 sm:gap-4" aria-label="研究回答">
    <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-xl bg-blue-600 text-white sm:size-8"><Sparkles className="size-3.5 sm:size-4" /></span>
    <div className="min-w-0 flex-1">
      <div className="mb-3 flex items-center gap-2"><span className="text-xs font-semibold text-slate-700">Research AI</span>{message.model && <span className="truncate text-[10px] text-slate-400">{message.provider_name || message.model}</span>}</div>
      <RunActivity message={message} active={active} />
      {headings.length >= 4 && <details className="mb-4 rounded-xl border border-slate-100 px-3 py-2"><summary className="flex cursor-pointer list-none items-center gap-2 text-xs text-slate-500"><List className="size-3.5" />报告目录<span className="ml-auto text-[10px] text-slate-400">{headings.length} 个章节</span></summary><nav aria-label="报告目录" className="mt-2 max-h-48 space-y-1 overflow-y-auto border-t border-slate-100 pt-2">{headings.map((heading) => <a key={heading.id} href={`#${heading.id}`} className={"block py-1 text-xs leading-5 text-slate-500 hover:text-blue-600 " + (heading.level === "H3" ? "pl-4" : "")}>{heading.title}</a>)}</nav></details>}
      {message.thinking && <details className="mb-4 rounded-xl border border-slate-100 px-3 py-2 text-xs text-slate-400"><summary className="cursor-pointer">历史版本的思考记录</summary><p className="mt-2 whitespace-pre-wrap leading-6">{message.thinking}</p></details>}
      {message.content ? <div ref={report} className="research-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{
        a: ({ href, children }) => href?.startsWith("#") ? <a href={href} className="citation-link">{children}</a> : <a href={httpUrl(href)} target="_blank" rel="noopener noreferrer">{children}</a>,
        table: ({ children }) => <div className="markdown-table"><table>{children}</table></div>,
      }}>{linkCitations(message.content, sources, prefix)}</ReactMarkdown></div> : active ? <p className="text-sm text-slate-400"><span className="inline-flex gap-1"><span className="size-1 animate-pulse rounded-full bg-blue-500" /><span className="size-1 animate-pulse rounded-full bg-blue-400 [animation-delay:150ms]" /><span className="size-1 animate-pulse rounded-full bg-blue-300 [animation-delay:300ms]" /></span><span className="ml-2">正在收集资料并整理回答</span></p> : null}
      {message.status === "cancelled" && <p className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-xs leading-6 text-slate-500">已停止研究{message.content ? "，以上为停止前收到的内容。" : "。你可以编辑问题后重新发送。"}</p>}
      {message.status === "failed" && <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs leading-6 text-amber-800">这次研究未能完整完成。{message.content ? "你仍可复制或导出已有内容。" : "请检查下方错误，编辑问题后重试。"}</p>}
      {message.status === "running" && !active && <p className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-xs leading-6 text-slate-500">这次研究记录仍标记为运行中，当前页面未连接到该执行。可重新加载会话查看状态，或重新发起研究。</p>}
      {message.error && <p className="mt-2 break-words text-xs leading-6 text-amber-700">{message.error}</p>}
      {!active && ["failed", "cancelled", "running"].includes(message.status || "") && onRetry && <button disabled={busy} onClick={onRetry} className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:border-blue-200 hover:text-blue-600 disabled:opacity-40"><RotateCcw className="size-3" />编辑问题后重试</button>}
      {sources.length > 0 && <section className="mt-6 border-t border-slate-100 pt-4" aria-label="本条回答的来源"><h3 className="mb-3 flex items-center gap-2 text-xs font-semibold text-slate-600"><FileText className="size-3.5" />来源<span className="font-normal text-slate-400">{sources.length}</span></h3><div className="grid gap-2 sm:grid-cols-2">{sources.map((source, sourceIndex) => {
        const url = httpUrl(source.url);
        const body = <><div className="mb-1 flex items-center justify-between gap-2"><span className="text-[10px] font-semibold text-blue-600">{source.label}</span>{url ? <ExternalLink className="size-3 text-slate-300" /> : <FileText className="size-3 text-slate-300" />}</div><p className="line-clamp-2 text-xs font-medium leading-5 text-slate-600">{source.title}</p><p className="mt-1 truncate text-[10px] text-slate-400">{url ? new URL(url).hostname : "本地资料"}</p></>;
        const className = "block min-w-0 scroll-mt-5 rounded-xl border border-slate-200 bg-white px-3 py-2.5 transition hover:border-blue-200 hover:bg-blue-50/30";
        return url ? <a key={sourceIndex} id={sourceId(prefix, source.label)} href={url} target="_blank" rel="noopener noreferrer" className={className}>{body}</a> : <div key={sourceIndex} id={sourceId(prefix, source.label)} className={className}>{body}</div>;
      })}</div></section>}
      {message.content && <div className="mt-4 flex flex-wrap items-center gap-1 text-slate-400"><button type="button" aria-label={copied ? "已复制报告" : "复制报告和来源"} title="复制报告和来源" onClick={() => void copy()} className="report-action">{copied ? <Check className="size-3.5 text-emerald-600" /> : <Copy className="size-3.5" />}<span>{copied ? "已复制" : "复制"}</span></button><button type="button" title="导出 Markdown" onClick={download} className="report-action"><Download className="size-3.5" /><span>导出</span></button>{!!message.total_tokens && <span className="ml-2 text-[10px]">{message.total_tokens.toLocaleString()} tokens</span>}{active && <span className="ml-2 text-[10px] text-blue-500">正在生成…</span>}</div>}
      {actionError && <p role="status" className="mt-2 text-xs text-amber-700">{actionError}</p>}
    </div>
  </article>;
}

export function MessageList({ messages, busy, onEditQuestion }: { messages: Message[]; busy: boolean; onEditQuestion: (question: string) => void }) {
  return <div className="mx-auto w-full max-w-[980px] space-y-8 px-4 py-8 sm:space-y-10 sm:px-8 sm:py-10">{messages.map((message, index) => message.role === "user" ? <div key={message.id ?? `user-${index}`} className="ml-auto w-fit max-w-[90%] whitespace-pre-wrap break-words rounded-2xl rounded-tr-sm bg-slate-100 px-4 py-3 text-sm leading-7 text-slate-700 sm:max-w-[82%] sm:px-5">{message.content}</div> : <AssistantMessage key={message.id ?? `assistant-${index}`} message={message} index={index} active={busy && index === messages.length - 1} busy={busy} onRetry={() => onEditQuestion([...messages.slice(0, index)].reverse().find((item) => item.role === "user")?.content || "")} />)}</div>;
}
