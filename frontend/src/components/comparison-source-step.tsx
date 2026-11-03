import { CheckCircle2, ChevronDown, LoaderCircle, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

import type { SourceDocument } from "@/lib/types";

type Kind = "paper" | "run";

type Props = {
  kind: Kind;
  documents: SourceDocument[];
  selectedId: string;
  onSelect: (id: string) => void;
  onUpload: (kind: Kind, file: File) => Promise<void>;
  uploading: boolean;
  disabled: boolean;
  error: string;
};

const sample = `模型：ResNet-50
数据集：ImageNet
数据划分：validation
评估方式：10-crop
指标：top-1 error
结果：24.10%
随机种子：42`;

export function ComparisonSourceStep({
  kind, documents, selectedId, onSelect, onUpload, uploading, disabled, error,
}: Props) {
  const isPaper = kind === "paper";
  const fileInput = useRef<HTMLInputElement>(null);
  const [showPaste, setShowPaste] = useState(false);
  const [runText, setRunText] = useState("");
  const [filename, setFilename] = useState("我的实验结果.md");
  const [localError, setLocalError] = useState("");
  const ready = documents.filter((doc) => doc.status === "ready");
  const selected = ready.find((doc) => String(doc.id) === selectedId);

  async function upload(file?: File) {
    if (!file || disabled) return;
    setLocalError("");
    try {
      await onUpload(kind, file);
    } finally {
      if (fileInput.current) fileInput.current.value = "";
    }
  }

  async function saveText() {
    if (!runText.trim()) {
      setLocalError("请填写实验结果。");
      return;
    }
    if (!filename.trim()) {
      setLocalError("请填写文件名。");
      return;
    }
    const cleanName = filename.trim().replace(/[\\/:*?"<>|]/g, "-");
    const name = /\.md$/i.test(cleanName) ? cleanName : `${cleanName}.md`;
    setLocalError("");
    await onUpload("run", new File([runText.trim()], name, { type: "text/markdown" }));
  }

  return <section aria-label={isPaper ? "第一步：添加论文" : "第二步：添加实验结果"} className="min-w-0 rounded-2xl border border-slate-200 bg-white p-5 shadow-xs sm:p-6">
    <div className="flex items-center gap-3">
      <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-blue-50 text-xs font-semibold text-blue-700">{isPaper ? "01" : "02"}</span>
      <h2 className="text-sm font-semibold text-slate-900">{isPaper ? "论文" : "本地实验结果"}</h2>
    </div>

    <label htmlFor={`comparison-${kind}-source`} className="mt-5 block text-xs font-medium text-slate-600">选择已有文件</label>
    <select id={`comparison-${kind}-source`} value={selectedId} disabled={disabled}
      onChange={(event) => onSelect(event.target.value)}
      className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-800 outline-none focus:border-blue-400 disabled:bg-slate-50">
      <option value="">{isPaper ? "选择论文" : "选择实验摘要"}</option>
      {ready.map((doc) => <option key={doc.id} value={doc.id}>{doc.filename}</option>)}
    </select>

    <input ref={fileInput} type="file"
      accept={isPaper ? ".pdf,.docx,.txt,.md,.markdown" : ".txt,.md,.markdown,.csv,.docx,.pdf"}
      className="sr-only"
      aria-label={isPaper ? "选择要上传的论文文件" : "选择要上传的实验结果文件"}
      disabled={disabled}
      onChange={(event) => { void upload(event.target.files?.[0]); }}
    />
    <button type="button" disabled={disabled} onClick={() => fileInput.current?.click()}
      className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-slate-300 px-4 py-3 text-sm font-medium text-blue-700 transition hover:border-blue-300 hover:bg-blue-50/60 disabled:opacity-50">
      {uploading ? <LoaderCircle className="size-4 animate-spin" /> : <UploadCloud className="size-4" />}
      {uploading ? "正在上传…" : isPaper ? "上传论文" : "上传实验摘要"}
    </button>
    {selected && <p className="mt-3 flex items-center gap-1.5 break-all text-xs text-emerald-700"><CheckCircle2 className="size-3.5 shrink-0" />已选择：{selected.filename}</p>}
    {!isPaper && <div className="mt-3">
      <button type="button" aria-expanded={showPaste} onClick={() => setShowPaste((value) => !value)}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-blue-700 hover:underline">
        <ChevronDown className={`size-3.5 transition-transform ${showPaste ? "rotate-180" : ""}`} />
        没有文件？直接粘贴结果
      </button>
      {showPaste && <div className="mt-4 space-y-3 border-t border-slate-100 pt-4">
        <label htmlFor="comparison-run-text" className="block text-xs font-medium text-slate-700">实验摘要</label>
        <textarea id="comparison-run-text" rows={6} maxLength={30000} value={runText}
          disabled={disabled} onChange={(event) => setRunText(event.target.value)}
          placeholder="模型：ResNet-50\n数据集：ImageNet\n指标：top-1 error\n结果：24.10%"
          className="w-full resize-y rounded-xl border border-slate-200 p-3 text-sm leading-6 outline-none focus:border-blue-400 disabled:bg-slate-50" />
        <details className="text-xs text-slate-500">
          <summary className="cursor-pointer text-blue-700">填写示例（虚构数据）</summary>
          <pre className="mt-2 whitespace-pre-wrap rounded-lg bg-slate-50 p-3 leading-6 text-slate-700">{sample}</pre>
        </details>
        <div className="flex flex-wrap gap-2">
          <input aria-label="实验摘要文件名" value={filename} disabled={disabled} maxLength={100}
            onChange={(event) => setFilename(event.target.value)}
            className="min-w-0 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-400 disabled:bg-slate-50" />
          <button type="button" disabled={disabled || !runText.trim()} onClick={() => { void saveText(); }}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-40">保存并选中</button>
        </div>
      </div>}
    </div>}
    {(localError || error) && <p role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-xs text-red-700">{localError || error}</p>}
  </section>;
}
