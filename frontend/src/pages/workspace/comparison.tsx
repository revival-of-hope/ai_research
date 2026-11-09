import { FileSearch, LoaderCircle, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useOutletContext, useSearchParams } from "react-router-dom";

import { ComparisonReview } from "@/components/comparison-review";
import { ComparisonSourceStep } from "@/components/comparison-source-step";
import { ResearchTaskNavigation } from "@/components/research/research-task-navigation";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Comparison, ComparisonField, ComparisonFieldKey, ComparisonListItem, ReviewStatus } from "@/lib/comparison";
import type { Provider, SourceDocument } from "@/lib/types";
import { useUnsavedChanges } from "@/lib/use-unsaved-changes";

export function ComparisonPage() {
  const { user } = useAuth();
  const workspace = useOutletContext<{ setWorkspaceBusy: (busy: boolean) => void } | null>();
  const [params, setParams] = useSearchParams();
  const requestedId = Number(params.get("comparison"));
  const providerStorageKey = `research-provider-${user?.id ?? "current"}`;
  const [documents, setDocuments] = useState<SourceDocument[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [history, setHistory] = useState<ComparisonListItem[]>([]);
  const [paperId, setPaperId] = useState("");
  const [runId, setRunId] = useState("");
  const [providerId, setProviderId] = useState("");
  const [metric, setMetric] = useState("");
  const [current, setCurrent] = useState<Comparison>();
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [uploading, setUploading] = useState<"paper" | "run">();
  const [uploadErrors, setUploadErrors] = useState({ paper: "", run: "" });
  const createController = useRef<AbortController | null>(null);
  const [savingField, setSavingField] = useState<ComparisonFieldKey>();
  const [draftChanged, setDraftChanged] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const discardUnsavedChanges = useUnsavedChanges(draftChanged);

  useEffect(() => {
    const deleted = (event: Event) => {
      const detail = (event as CustomEvent<{ conversationId: number }>).detail;
      if (!current || detail?.conversationId !== current.conversation_id) return;
      discardUnsavedChanges();
      setDraftChanged(false);
      setCurrent(undefined);
      setError("");
      setNotice("该核验记录已删除。");
    };
    window.addEventListener("research-record-deleted", deleted);
    return () => window.removeEventListener("research-record-deleted", deleted);
  }, [current?.conversation_id, discardUnsavedChanges]);

  useEffect(() => {
    workspace?.setWorkspaceBusy(busy || !!uploading || savingField !== undefined);
    return () => workspace?.setWorkspaceBusy(false);
  }, [workspace?.setWorkspaceBusy, busy, uploading, savingField]);

  const refresh = useCallback(async () => {
    const [docs, presets, records] = await Promise.all([
      api<SourceDocument[]>("/documents"),
      api<Provider[]>("/account/providers"),
      api<ComparisonListItem[]>("/research/comparisons"),
    ]);
    setDocuments(docs);
    setProviders(presets);
    setHistory(records);
    setProviderId((currentId) => {
      const preferred = currentId || localStorage.getItem(providerStorageKey);
      return String(presets.find((preset) => preset.compatible && String(preset.id) === preferred)?.id ?? presets.find((preset) => preset.compatible)?.id ?? "");
    });
  }, [providerStorageKey]);

  useEffect(() => {
    void refresh().catch((reason) => setError(reason instanceof Error ? reason.message : "加载失败"))
      .finally(() => setLoading(false));
    return () => createController.current?.abort();
  }, [refresh]);

  useEffect(() => {
    if (loading || creating || current?.id === requestedId) return;
    if (!Number.isSafeInteger(requestedId) || requestedId <= 0) {
      setCurrent(undefined);
      setDraftChanged(false);
      setBusy(false);
      return;
    }
    const controller = new AbortController();
    setCurrent(undefined);
    setDraftChanged(false);
    setBusy(true);
    setError("");
    void api<Comparison>(`/research/comparisons/${requestedId}`, { signal: controller.signal })
      .then((record) => { setCurrent(record); setDraftChanged(false); })
      .catch((reason) => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "核验记录加载失败"); })
      .finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [requestedId, loading, creating]);

  useEffect(() => {
    const controller = new AbortController();
    const reload = () => {
      void api<ComparisonListItem[]>("/research/comparisons", { signal: controller.signal })
        .then(setHistory).catch(() => undefined);
    };
    window.addEventListener("research-history-changed", reload);
    return () => { controller.abort(); window.removeEventListener("research-history-changed", reload); };
  }, []);

  useEffect(() => {
    if (current?.id) window.scrollTo({ top: 0, behavior: "smooth" });
  }, [current?.id]);

  const ready = documents.filter((document) => document.status === "ready");
  const compatible = providers.filter((provider) => provider.compatible);
  const canStart = ready.some((doc) => String(doc.id) === paperId)
    && ready.some((doc) => String(doc.id) === runId)
    && paperId !== runId && !!providerId && !!metric.trim()
    && metric.trim().length <= 120 && !busy && !uploading;

  function backToSetup() {
    setParams({});
    setError("");
    setNotice("");
  }

  async function refreshWorkspace() {
    if (draftChanged && !window.confirm("刷新会放弃尚未保存的修改，确定继续吗？")) return;
    try {
      await refresh();
      if (current) setCurrent(await api<Comparison>(`/research/comparisons/${current.id}`));
      setDraftChanged(false);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "刷新失败");
    }
  }

  async function uploadSource(kind: "paper" | "run", file: File) {
    if (busy || uploading) return;
    setUploading(kind);
    setUploadErrors((previous) => ({ ...previous, [kind]: "" }));
    setNotice("");
    try {
      const form = new FormData();
      form.append("upload", file);
      const saved = await api<SourceDocument>("/documents", { method: "POST", body: form });
      setDocuments((previous) => [saved, ...previous.filter((doc) => doc.id !== saved.id)]);
      if (saved.status === "failed") {
        setUploadErrors((previous) => ({ ...previous, [kind]: saved.error_message || "文件解析失败，请换成可提取文字的文件。" }));
        return;
      }
      if (saved.status !== "ready") {
        setUploadErrors((previous) => ({ ...previous, [kind]: "文件仍在解析中，完成后请刷新资料并选择。" }));
        return;
      }
      if (kind === "paper") setPaperId(String(saved.id));
      else setRunId(String(saved.id));
      setNotice(`${kind === "paper" ? "论文" : "实验结果"}“${saved.filename}”已保存到资料库，并自动选中。`);
    } catch (reason) {
      setUploadErrors((previous) => ({ ...previous, [kind]: reason instanceof Error ? reason.message : "上传失败" }));
    } finally {
      setUploading(undefined);
    }
  }

  async function createComparison() {
    if (!canStart) return;
    const controller = new AbortController();
    createController.current = controller;
    setBusy(true);
    setCreating(true);
    setError("");
    setNotice("");
    try {
      const result = await api<Comparison>("/research/comparisons", {
        method: "POST",
        body: JSON.stringify({
          paper_document_id: Number(paperId),
          run_document_id: Number(runId),
          provider_id: Number(providerId),
          metric: metric.trim(),
        }),
        signal: controller.signal,
      });
      setCurrent(result);
      setParams({ comparison: String(result.id) }, { replace: true });
      window.dispatchEvent(new Event("research-history-changed"));
      setDraftChanged(false);
      setNotice("核验结果已生成。请检查原文，再逐项确认。");
      try {
        setHistory(await api<ComparisonListItem[]>("/research/comparisons"));
      } catch {
        setError("核验结果已保存，但历史列表刷新失败。可稍后重新打开页面查看。");
      }
    } catch (reason) {
      if (reason instanceof Error && reason.name === "AbortError") {
        try {
          await refresh();
          setNotice("生成已取消，历史列表已刷新。");
        } catch {
          setError("生成已取消，但历史列表刷新失败。");
        }
      } else {
        setError(reason instanceof Error ? reason.message : "核验结果生成失败");
      }
    } finally {
      if (createController.current === controller) createController.current = null;
      setCreating(false);
      setBusy(false);
    }
  }

  function openComparison(id: number) {
    setNotice("");
    setParams({ comparison: String(id) });
  }

  function editField(key: ComparisonFieldKey, change: Partial<ComparisonField>) {
    setDraftChanged(true);
    setCurrent((record) => record && record.status === "pending" ? {
      ...record,
      fields: record.fields.map((row) => row.key === key ? {
        ...row,
        ...change,
        paper: change.paper ? { ...row.paper, ...change.paper } : row.paper,
        run: change.run ? { ...row.run, ...change.run } : row.run,
        review_status: "pending",
      } : row),
    } : record);
  }

  async function reviewField(row: ComparisonField, state: Exclude<ReviewStatus, "pending">) {
    if (!current || current.status === "confirmed") return;
    setSavingField(row.key);
    setError("");
    setNotice("");
    try {
      const result = await api<Comparison>(`/research/comparisons/${current.id}`, {
        method: "PATCH",
        body: JSON.stringify({
          updates: [{
            key: row.key,
            paper_value: row.paper.value,
            run_value: row.run.value,
            paper_source: { excerpt: row.paper.excerpt, chunk_id: row.paper.chunk_id },
            run_source: { excerpt: row.run.excerpt, chunk_id: row.run.chunk_id },
            review_status: state,
            note: row.note,
          }],
        }),
      });
      setCurrent(result);
      setDraftChanged(false);
      window.dispatchEvent(new Event("research-history-changed"));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "这一项的确认未能保存");
    } finally {
      setSavingField(undefined);
    }
  }

  async function confirmComparison() {
    if (!current) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const saved = await api<Comparison>(`/research/comparisons/${current.id}`, {
        method: "PATCH",
        body: JSON.stringify({ confirm: true }),
      });
      setCurrent(saved);
      window.dispatchEvent(new Event("research-history-changed"));
      setNotice("核验结果已确认。尚未解决的问题会保留在记录中。");
      try {
        setHistory(await api<ComparisonListItem[]>("/research/comparisons"));
      } catch {
        setError("核验结果已确认，但历史列表刷新失败。可稍后重新打开页面查看。");
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "确认失败");
    } finally {
      setBusy(false);
    }
  }

  return <div className="mx-auto max-w-6xl space-y-5 pb-10">
    <div className="flex flex-wrap items-start justify-between gap-4 py-1">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">实验核验</h1>
        <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-500">论文中的结论，与你的实验是否一致？核对实验条件和结果，回到原文确认每一处差异。</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {current && <button type="button" onClick={backToSetup} disabled={busy || savingField !== undefined} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"><FileSearch className="size-4" />新建实验核验</button>}
        <button type="button" onClick={() => { void refreshWorkspace(); }} disabled={busy || loading || !!uploading || savingField !== undefined} className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-600 disabled:opacity-40"><RefreshCw className="size-4" />刷新</button>
      </div>
    </div>

    {!current && <ResearchTaskNavigation task="comparison" disabled={busy || !!uploading} />}
    {!current && <ol aria-label="实验核验步骤" className="flex flex-wrap gap-x-6 gap-y-2 py-1 text-xs text-slate-500"><li>准备论文和实验结果</li><li>选择要核对的指标</li><li>检查原文，保存结论</li></ol>}

    {!current && <div className="grid items-start gap-4 lg:grid-cols-2">
      <ComparisonSourceStep kind="paper" documents={documents} selectedId={paperId} onSelect={setPaperId} onUpload={uploadSource} uploading={uploading === "paper"} disabled={busy || !!uploading || loading} error={uploadErrors.paper} />
      <ComparisonSourceStep kind="run" documents={documents} selectedId={runId} onSelect={setRunId} onUpload={uploadSource} uploading={uploading === "run"} disabled={busy || !!uploading || loading} error={uploadErrors.run} />
    </div>}
    {!current && <p className="-mt-2 text-xs text-slate-500">支持文本 PDF、DOCX、TXT、Markdown，结果也可使用 CSV。上传的文件保存在<Link to="/sources" className="ml-1 text-blue-700 hover:underline">我的资料</Link>中。</p>}

    {!current && <section aria-label="第三步：生成核验结果" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs sm:p-6">
      <div className="flex items-start gap-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-blue-50 text-xs font-semibold text-blue-700">03</span>
        <div>
          <h2 className="text-sm font-semibold">核验设置</h2>
        </div>
      </div>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <label className="block text-xs font-medium text-slate-600">要核对的指标和实验
          <input value={metric} onChange={(event) => setMetric(event.target.value)} disabled={busy || !!uploading} placeholder="例如 top-1 error（ResNet-50，Table 3）" className="mt-2 w-full rounded-xl border border-slate-200 px-3 py-3 text-sm font-normal outline-none focus:border-blue-400 disabled:bg-slate-50" />
          {metric.trim().length > 120 && <span role="alert" className="mt-1 block text-xs font-normal text-amber-700">当前 {metric.trim().length} 字，最多 120 字。请精简目标描述，系统不会截断输入。</span>}
        </label>
        <label className="block text-xs font-medium text-slate-600">使用的模型
          <select value={providerId} onChange={(event) => { setProviderId(event.target.value); localStorage.setItem(providerStorageKey, event.target.value); }} disabled={busy || !!uploading || loading} className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm font-normal outline-none focus:border-blue-400 disabled:bg-slate-50">
            <option value="">请选择模型</option>
            {compatible.map((provider) => <option value={provider.id} key={provider.id}>{provider.name} · {provider.model}</option>)}
          </select>
        </label>
      </div>
      {!compatible.length && !loading && <p className="mt-3 text-sm text-amber-700">当前没有可用的模型预设，请先去<Link to="/settings" className="font-medium underline">模型设置</Link>配置模型。</p>}
      {paperId && runId && paperId === runId && <p role="alert" className="mt-3 text-sm text-amber-700">论文和实验结果必须是两份不同的资料，请重新选择。</p>}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button disabled={!canStart} onClick={() => void createComparison()} className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white disabled:opacity-40">
          {busy ? <LoaderCircle className="size-4 animate-spin" /> : <FileSearch className="size-4" />}{busy ? "正在整理实验结果…" : "生成核验结果"}
        </button>
        {creating && <button type="button" onClick={() => createController.current?.abort()} className="rounded-lg border border-slate-200 px-4 py-2.5 text-sm text-slate-600 hover:bg-slate-50">取消生成</button>}
      </div>
      <p className="mt-3 text-xs text-slate-400">将选中资料发送至所选模型。模型整理的内容需要你查看原文并确认。</p>
    </section>}

    {error && <p role="alert" className="rounded-xl bg-red-50 p-3 text-xs text-red-700">{error}</p>}
    {notice && <p role="status" className="rounded-xl bg-blue-50 p-3 text-xs text-blue-800">{notice}</p>}

    {current && <ComparisonReview comparison={current}
      onBack={backToSetup}
      onEdit={editField}
      onReview={(field, status) => { void reviewField(field, status); }}
      onConfirm={() => { void confirmComparison(); }}
      busy={busy} savingField={savingField} />}


    {!current && <section aria-label="历史核验" className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6">
      <h2 className="text-base font-semibold">已保存的核验记录</h2>
      {loading ? <p role="status" className="mt-3 text-xs text-slate-500">正在加载…</p> : !history.length ? <p className="mt-3 text-sm text-slate-500">还没有核验记录。添加两份资料，开始第一次实验核验。</p> : <div className="mt-4 space-y-2">
        {history.map((row) => <button key={row.id} disabled={busy} onClick={() => void openComparison(row.id)} className="flex w-full flex-wrap items-start justify-between gap-3 rounded-xl border border-slate-200 px-4 py-3 text-left hover:border-blue-200 hover:bg-blue-50/30 disabled:opacity-50">
          <span className="min-w-0 flex-1"><span className="block break-words text-sm font-medium text-slate-800">#{row.id} · {row.metric}</span><span className="mt-1 block break-words text-xs leading-5 text-slate-500">论文：{row.paper_name}<span className="mx-1">·</span>结果：{row.run_name}</span></span>
          <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${row.status === "confirmed" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>{row.status === "confirmed" ? "已确认" : "待复核"}</span>
        </button>)}
      </div>}
    </section>}
  </div>;
}
