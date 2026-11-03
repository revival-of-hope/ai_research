import { ArrowLeft, Check, CheckCircle2, ChevronRight, FileText, LoaderCircle, Search, ShieldAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "@/lib/api";
import type { Comparison, ComparisonField, ComparisonFieldKey, ComparisonSourceChunk, ReviewStatus } from "@/lib/comparison";

type EvidenceSide = "paper" | "run";
type SourceContext = {
  filename: string; chunk_id: number; ordinal: number; content: string;
  page_number: number | null;
};

const comparisonLabels: Record<ComparisonField["status"], string> = {
  aligned: "一致", mismatch: "存在差异", unknown: "证据不足",
};
const colors: Record<ComparisonField["status"], string> = {
  aligned: "bg-emerald-50 text-emerald-700",
  mismatch: "bg-amber-50 text-amber-800",
  unknown: "bg-slate-100 text-slate-600",
};
const reviewLabels: Record<ComparisonField["review_status"], string> = {
  pending: "待复核", confirmed: "已核实", unresolved: "未解决",
};
const coreKeys: ComparisonFieldKey[] = [
  "dataset", "version", "split", "model", "training", "preprocessing", "metric", "unit",
];

type Props = {
  comparison: Comparison;
  onBack: () => void;
  onEdit: (key: ComparisonFieldKey, change: Partial<ComparisonField>) => void;
  onReview: (row: ComparisonField, status: Exclude<ReviewStatus, "pending">) => void;
  onConfirm: () => void;
  busy: boolean;
  savingField?: ComparisonFieldKey;
};

export function ComparisonReview({ comparison, onBack, onEdit, onReview, onConfirm, busy, savingField }: Props) {
  const [activeKey, setActiveKey] = useState<ComparisonFieldKey>("dataset");
  const [context, setContext] = useState<{ side: EvidenceSide; data: SourceContext }>();
  const [contextLoading, setContextLoading] = useState(false);
  const [contextError, setContextError] = useState("");
  const [referenceSide, setReferenceSide] = useState<EvidenceSide>();
  const [sourceChunks, setSourceChunks] = useState<ComparisonSourceChunk[]>([]);
  const [sourceQuery, setSourceQuery] = useState("");
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceError, setSourceError] = useState("");
  const requestIndex = useRef(0);
  useEffect(() => {
    requestIndex.current += 1;
    setActiveKey("dataset");
    setContext(undefined);
    setContextError("");
    setReferenceSide(undefined);
    setSourceChunks([]);
    setSourceQuery("");
    setSourceLoading(false);
    setSourceError("");
  }, [comparison.id]);

  const active = comparison.fields.find((field) => field.key === activeKey) ?? comparison.fields[0];
  const confirmed = comparison.fields.filter((field) => field.review_status === "confirmed").length;
  const unresolved = comparison.fields.filter((field) => field.review_status === "unresolved").length;
  const pending = comparison.fields.length - confirmed - unresolved;
  const coreBlocked = coreKeys.some((key) => {
    const field = comparison.fields.find((item) => item.key === key);
    return !field || field.status !== "aligned";
  });
  const value = comparison.fields.find((field) => field.key === "value");
  const final = comparison.status === "confirmed";

  async function openEvidence(side: EvidenceSide) {
    if (!active?.[side].chunk_id) return;
    const requestId = ++requestIndex.current;
    setContext(undefined);
    setContextError("");
    setContextLoading(true);
    try {
      const data = await api<SourceContext>(`/comparisons/${comparison.id}/evidence/${side}/${active.key}`);
      if (requestId === requestIndex.current) setContext({ side, data });
    } catch (reason) {
      if (requestId === requestIndex.current) {
        setContextError(reason instanceof Error ? reason.message : "原文片段读取失败");
      }
    } finally {
      if (requestId === requestIndex.current) setContextLoading(false);
    }
  }

  async function loadSourceChunks(side: EvidenceSide, query = "") {
    const requestId = ++requestIndex.current;
    const cleanQuery = query.trim();
    const suffix = cleanQuery ? "?q=" + encodeURIComponent(cleanQuery) : "";
    setSourceLoading(true);
    setSourceError("");
    setSourceChunks([]);
    try {
      const chunks = await api<ComparisonSourceChunk[]>(
        "/comparisons/" + comparison.id + "/source-chunks/" + side + suffix,
      );
      if (requestId === requestIndex.current) setSourceChunks(chunks);
    } catch (reason) {
      if (requestId === requestIndex.current) {
        setSourceError(reason instanceof Error ? reason.message : "读取所选来源文本片段失败");
      }
    } finally {
      if (requestId === requestIndex.current) setSourceLoading(false);
    }
  }

  function openSourceEditor(side: EvidenceSide) {
    if (referenceSide === side) {
      requestIndex.current += 1;
      setReferenceSide(undefined);
      setSourceChunks([]);
      setSourceLoading(false);
      setSourceError("");
      return;
    }
    setReferenceSide(side);
    setSourceQuery("");
    void loadSourceChunks(side);
  }

  function selectSourceChunk(side: EvidenceSide, chunk: ComparisonSourceChunk) {
    if (!active) return;
    const currentExcerpt = active[side].excerpt;
    onEdit(active.key, {
      [side]: {
        ...active[side],
        chunk_id: chunk.chunk_id,
        excerpt: currentExcerpt && chunk.content.includes(currentExcerpt) ? currentExcerpt : null,
      },
    });
  }

  const switchField = (key: ComparisonFieldKey) => {
    requestIndex.current += 1;
    setActiveKey(key);
    setContextLoading(false);
    setContext(undefined);
    setContextError("");
    setReferenceSide(undefined);
    setSourceChunks([]);
    setSourceLoading(false);
    setSourceError("");
  };

  return <section aria-label="论文与实验结果复核工作台" className="space-y-4">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <button type="button" onClick={onBack} disabled={busy || savingField !== undefined} className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-blue-700 disabled:opacity-40"><ArrowLeft className="size-3.5" />返回列表</button>
        <h2 className="mt-2 text-lg font-semibold tracking-tight text-slate-900">对照 #{comparison.id} · {comparison.metric}</h2>
      </div>
      <span className={`rounded-full px-3 py-1.5 text-xs font-medium ${final ? "bg-emerald-50 text-emerald-700" : "bg-blue-50 text-blue-700"}`}>{final ? "已人工确认" : "等待人工复核"}</span>
    </div>

    <div className="flex flex-wrap gap-x-6 gap-y-2 px-1 text-xs text-slate-500" aria-label="复核进度">
      <span>已核实 <strong className="tabular-nums text-slate-800">{confirmed}</strong></span>
      <span>未解决 <strong className="tabular-nums text-amber-700">{unresolved}</strong></span>
      <span>待复核 <strong className="tabular-nums text-blue-700">{pending}</strong></span>
    </div>

    <div role="status" className={`flex gap-3 rounded-xl border p-4 text-sm leading-6 ${coreBlocked ? "border-amber-200 bg-amber-50 text-amber-900" : "border-blue-100 bg-blue-50/60 text-blue-900"}`}>
      <ShieldAlert className="mt-0.5 size-5 shrink-0" />
      <div><strong className="font-semibold">{coreBlocked ? "当前不能判定为同条件实验" : "关键条件候选值一致，仍需人工核实"}</strong>
        <p className="mt-1 text-xs leading-5 opacity-90">{coreBlocked
          ? "关键条件存在差异或证据不足，不能直接比较。"
          : "请核对原文是否来自同一实验行。"}
          {value && ` 目标指标的数值比较：${comparisonLabels[value.status]}。`}
        </p>
      </div>
    </div>

    <div className="grid items-start gap-4 lg:grid-cols-[minmax(230px,0.37fr)_minmax(0,1fr)]">
      <aside aria-label="本次对照的两份来源" className="space-y-3 lg:sticky lg:top-6">
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs">
          <h3 className="text-sm font-semibold text-slate-900">本次使用的证据</h3>
          {([
            ["paper", "论文来源", comparison.paper_name],
            ["run", "本地运行摘要", comparison.run_name],
          ] as const).map(([side, label, filename]) => <div key={side} className="mt-3 rounded-xl border border-slate-100 bg-slate-50/70 p-3">
            <p className="flex items-center gap-2 text-xs font-medium text-slate-600"><FileText className="size-4 text-blue-500" />{label}</p>
            <p className="mt-2 break-all text-sm font-medium leading-6 text-slate-900">{filename}</p>
          </div>)}
          <Link to="/sources" className="mt-4 inline-flex items-center gap-1 text-xs font-medium text-blue-700 hover:underline">资料库<ChevronRight className="size-3.5" /></Link>
        </div>
      </aside>

      <div className="min-w-0 space-y-4">
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xs">
          <div className="border-b border-slate-100 px-4 py-4 sm:px-5">
            <h3 className="text-sm font-semibold text-slate-900">实验条件与指标对照</h3>
            <p className="mt-1 text-xs text-slate-500">选择字段，查看两侧证据并复核。</p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[550px] border-collapse text-left text-sm">
              <thead><tr className="bg-slate-50 text-xs text-slate-500">
                <th scope="col" className="w-[20%] px-4 py-3 font-medium">字段</th>
                <th scope="col" className="w-[27%] px-3 py-3 font-medium">论文报告</th>
                <th scope="col" className="w-[27%] px-3 py-3 font-medium">本地运行</th>
                <th scope="col" className="px-3 py-3 font-medium">状态</th>
              </tr></thead>
              <tbody>{comparison.fields.map((field) => <tr key={field.key} className={`border-t border-slate-100 ${field.key === active.key ? "bg-blue-50/70" : "hover:bg-slate-50"}`}>
                <th scope="row" className="px-4 py-3 text-left font-medium">
                  <button type="button" aria-pressed={field.key === active.key} onClick={() => switchField(field.key)} className="flex items-center gap-1.5 text-left text-slate-800 hover:text-blue-700">{field.label}<ChevronRight className="size-3.5 shrink-0 text-slate-400" /></button>
                </th>
                <td className="max-w-0 truncate px-3 py-3 text-xs text-slate-700" title={field.paper.value ?? "未提取"}>{field.paper.value ?? "—"}</td>
                <td className="max-w-0 truncate px-3 py-3 text-xs text-slate-700" title={field.run.value ?? "未提取"}>{field.run.value ?? "—"}</td>
                <td className="px-3 py-3"><span className={`inline-flex whitespace-nowrap rounded-full px-2 py-1 text-[11px] font-medium ${colors[field.status]}`}>{comparisonLabels[field.status]}</span><span className="mt-1 block text-[10px] text-slate-400">{reviewLabels[field.review_status]}</span></td>
              </tr>)}</tbody>
            </table>
          </div>
        </div>

        {active && <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs sm:p-5" aria-label="当前字段的原文与人工复核">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-base font-semibold text-slate-900">{active.label} · 查看来源与复核</h3>
            <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${colors[active.status]}`}>{comparisonLabels[active.status]}</span>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {(["paper", "run"] as const).map((side) => <div key={side} className="min-w-0 rounded-xl border border-slate-200 p-3">
              <label className="text-xs font-semibold text-slate-700">{side === "paper" ? "论文报告值" : "本地运行值"}
                <input
                  value={active[side].value ?? ""}
                  onChange={(event) => onEdit(active.key, { [side]: { ...active[side], value: event.target.value || null } })}
                  disabled={final || savingField !== undefined}
                  aria-label={`${active.label} · ${side === "paper" ? "论文" : "本地运行"}候选值`}
                  className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-normal outline-none focus:border-blue-400 disabled:bg-slate-50"
                  placeholder="证据不足或未提取"
                />
              </label>
              <p className="mt-3 text-[11px] font-semibold text-slate-500">原文摘录</p>
              <blockquote className="mt-1 min-h-16 break-words rounded-lg bg-slate-50 p-3 text-xs leading-6 text-slate-700">{active[side].excerpt ?? "未找到可核实的原文摘录。"}</blockquote>
              {active[side].chunk_id !== null ? <button type="button" disabled={contextLoading} onClick={() => { void openEvidence(side); }} className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-blue-700 hover:underline disabled:opacity-50"><Search className="size-3.5" />查看完整文本片段 #{active[side].chunk_id}</button>
                : <p className="mt-2 text-xs text-slate-400">来源位置未知</p>}
              {!final && <button type="button" onClick={() => openSourceEditor(side)} className="mt-2 block text-xs font-medium text-blue-700 hover:underline">
                {referenceSide === side ? "收起引用修订" : "修订引用摘录或位置"}
              </button>}
              {referenceSide === side && !final && <div className="mt-3 space-y-3 rounded-lg border border-blue-100 bg-blue-50/40 p-3">
                <label className="block text-xs font-semibold text-slate-700">
                  人工核对的原文摘录
                  <textarea
                    value={active[side].excerpt ?? ""}
                    rows={3}
                    maxLength={500}
                    onChange={(event) => onEdit(active.key, {
                      [side]: { ...active[side], excerpt: event.target.value || null },
                    })}
                    disabled={savingField !== undefined}
                    className="mt-2 w-full resize-y rounded-lg border border-slate-200 bg-white p-3 text-xs font-normal leading-5 outline-none focus:border-blue-400 disabled:bg-slate-50"
                    placeholder="从下方展开的已选来源文本片段中复制一段原文"
                  />
                </label>
                <p className="text-xs leading-5 text-slate-500">保存时会检查摘录是否出现在所选来源的文本片段中。更换片段后，请重新选择摘录。</p>
                <div className="flex flex-wrap gap-2">
                  <input
                    value={sourceQuery}
                    onChange={(event) => setSourceQuery(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" && sourceQuery.trim().length >= 2) {
                        event.preventDefault();
                        void loadSourceChunks(side, sourceQuery);
                      }
                    }}
                    disabled={sourceLoading || savingField !== undefined}
                    maxLength={120}
                    aria-label={"搜索" + (side === "paper" ? "论文" : "运行摘要") + "文本片段"}
                    placeholder="搜索当前来源，例如 ImageNet-1K"
                    className="min-w-40 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-blue-400 disabled:bg-slate-50"
                  />
                  <button type="button" disabled={sourceQuery.trim().length < 2 || sourceLoading || savingField !== undefined} onClick={() => void loadSourceChunks(side, sourceQuery)} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 disabled:opacity-40">搜索</button>
                  <button type="button" disabled={sourceLoading || savingField !== undefined} onClick={() => { setSourceQuery(""); void loadSourceChunks(side); }} className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 disabled:opacity-40">查看候选片段</button>
                  {(active[side].excerpt || active[side].chunk_id !== null) && <button type="button" disabled={savingField !== undefined} onClick={() => onEdit(active.key, { [side]: { ...active[side], excerpt: null, chunk_id: null } })} className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 disabled:opacity-40">清除引用</button>}
                </div>
                {sourceLoading && <p role="status" className="text-xs text-slate-500">正在查找所选来源…</p>}
                {sourceError && <p role="alert" className="rounded-lg bg-amber-50 p-2 text-xs text-amber-800">{sourceError}</p>}
                {!sourceLoading && !sourceError && sourceChunks.length === 0 && <p className="text-xs text-slate-500">没有匹配的文本片段。</p>}
                <div className="max-h-80 space-y-2 overflow-y-auto">
                  {sourceChunks.map((chunk) => <details key={chunk.chunk_id} className="rounded-lg border border-slate-200 bg-white p-2">
                    <summary className="cursor-pointer text-xs font-medium text-slate-700">文本片段 #{chunk.chunk_id} · 顺序 {chunk.ordinal + 1}</summary>
                    <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-md bg-slate-50 p-2 text-xs leading-5 text-slate-700">{chunk.content}</pre>
                    <button type="button" disabled={savingField !== undefined} onClick={() => selectSourceChunk(side, chunk)} className="mt-2 rounded-lg bg-blue-600 px-3 py-2 text-xs font-medium text-white disabled:opacity-40">选择此片段</button>
                  </details>)}
                </div>
              </div>}
            </div>)}
          </div>
          {contextLoading && <p role="status" className="mt-3 flex items-center gap-2 text-xs text-slate-500"><LoaderCircle className="size-4 animate-spin" />正在读取原文片段…</p>}
          {contextError && <p role="alert" className="mt-3 rounded-lg bg-amber-50 p-3 text-xs text-amber-800">{contextError}</p>}
          {context && <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50/40 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-xs font-semibold text-slate-800">{context.side === "paper" ? "论文" : "运行摘要"} · {context.data.filename}{context.data.page_number ? ` · PDF 第 ${context.data.page_number} 页（已定位）` : ""} · 文本片段 #{context.data.chunk_id}（顺序 {context.data.ordinal + 1}）</p><button type="button" onClick={() => setContext(undefined)} className="text-xs font-medium text-blue-700">收起</button></div>
            <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-white p-3 text-xs leading-6 text-slate-700">{context.data.content}</pre>
            <p className="mt-2 text-xs text-slate-500">{context.data.page_number ? "页码由摘录与 PDF 文本逐字匹配得到；表格行列仍需人工核实。" : "未能唯一定位 PDF 页码；文本片段不能作为页码或表格坐标。"}</p>
          </div>}
          <div className="mt-4 border-t border-slate-100 pt-4">
            <label className="block text-xs font-semibold text-slate-700">人工复核备注（可选）</label>
            <textarea
              value={active.note}
              rows={2}
              maxLength={1000}
              onChange={(event) => onEdit(active.key, { note: event.target.value })}
              disabled={final || savingField !== undefined}
              placeholder="例如：论文是 test split，本地结果为 validation；暂不能直接比较"
              className="mt-2 w-full resize-y rounded-lg border border-slate-200 p-3 text-sm outline-none focus:border-blue-400 disabled:bg-slate-50"
            />
            {!final && <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" disabled={busy || savingField !== undefined} onClick={() => onReview(active, "confirmed")} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"><Check className="size-4" />确认此字段</button>
              <button type="button" disabled={busy || savingField !== undefined} onClick={() => onReview(active, "unresolved")} className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-40">标记未解决</button>
            </div>}
            {final && <p className="mt-2 inline-flex items-center gap-2 text-xs text-emerald-700"><CheckCircle2 className="size-4" />此记录已确认，字段内容为只读。</p>}
          </div>
        </div>}
      </div>
    </div>

    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:p-5">
      <div><p className="text-sm font-semibold text-slate-900">{final ? "对照摘要已人工确认" : pending ? `还有 ${pending} 个字段待复核` : "所有字段均已复核"}</p><p className="mt-1 text-xs leading-6 text-slate-500">对照记录和复核操作保存在你的账号下。未解决字段可保留，但不会当作实验条件一致。{final ? "记录现已只读。" : "最终确认后记录将只读。"}</p></div>
      {!final && <button type="button" disabled={pending > 0 || busy || savingField !== undefined} onClick={onConfirm} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-40"><CheckCircle2 className="size-4" />确认并保存摘要</button>}
    </div>
  </section>;
}
