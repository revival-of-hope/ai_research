import { BarChart3, BookOpen, Database, KeyRound, X } from "lucide-react";
import { useRef } from "react";

import { ProviderManager } from "@/components/settings/provider-manager";
import { SourcesPanel } from "@/components/settings/sources-panel";
import { UsagePanel } from "@/components/settings/usage-panel";
import type { Provider } from "@/lib/types";
import { useDialogFocus } from "@/lib/use-dialog-focus";
import { cn } from "@/lib/utils";

export type SettingsSection = "providers" | "usage" | "sources" | "guide";
type Props = {
  section: SettingsSection;
  providers: Provider[];
  onSectionChange: (section: SettingsSection) => void;
  onProvidersChanged: (preferredId?: number) => Promise<void>;
  onDocumentsChanged: () => void;
  onClose: () => void;
};
const sections = [
  { id: "providers", label: "模型预设", icon: KeyRound },
  { id: "sources", label: "资料库", icon: Database },
  { id: "usage", label: "Token 用量", icon: BarChart3 },
  { id: "guide", label: "使用说明", icon: BookOpen },
] as const;

export function GuidePanel() {
  return <div className="space-y-5">
    <div><h2 className="text-lg font-semibold">从问题到研究报告</h2><p className="mt-1 text-xs leading-6 text-slate-500">准备好模型与资料，就可以开始研究。</p></div>
    {[
      ["01", "连接模型", "在模型预设中选择 OpenAI、DeepSeek、Qwen、Claude 或自定义提供方，自动填入地址与推荐模型。全部使用 Responses API；Claude 需填写自己的兼容网关地址。填写 API Key 后可获取接口返回的模型列表，保存后在输入框选择预设。"],
      ["02", "确定研究范围", "选择深度研究或快速问答。联网搜索使用 DDGS；上传的资料只有在输入框中明确勾选后才会参与本轮检索。"],
      ["03", "设置研究预算", "深度研究可设置协作智能体数量和子智能体派生层级。更高的预算允许探索更多子问题，也可能增加耗时与模型用量。推理强度是模型参数，与协作智能体数量分开设置。"],
      ["04", "跟踪过程，阅读结果", "研究计划和智能体任务会在回答中实时更新。可以停止正在执行的研究；完成后查看逐条来源，复制或导出 Markdown 报告。"],
    ].map(([number, title, text]) => <div key={number} className="flex gap-3 rounded-2xl border border-slate-200 p-4"><span className="text-xs font-semibold text-blue-500">{number}</span><div><h3 className="text-sm font-semibold text-slate-700">{title}</h3><p className="mt-1.5 text-xs leading-6 text-slate-500">{text}</p></div></div>)}
    <div className="rounded-2xl bg-slate-50 p-4"><h3 className="text-xs font-semibold text-slate-600">连接失败时</h3><p className="mt-2 text-xs leading-6 text-slate-500">401/403：检查密钥与账号权限。404：检查 Base URL 是否正确。400/422：检查模型 ID、Responses API 与推理参数是否被服务商支持。推荐模型列表不代表账号已获授权；获取模型列表不发送生成请求，连接测试会发送真实模型请求并产生少量用量。</p></div>
  </div>;
}

export function SettingsDialog(props: Props) {
  const root = useRef<HTMLDivElement>(null);
  useDialogFocus(root, props.onClose);
  return <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/25 p-3 backdrop-blur-[3px] sm:p-5" onMouseDown={(event) => { if (event.target === event.currentTarget) props.onClose(); }}>
    <div ref={root} role="dialog" aria-modal="true" aria-labelledby="settings-title" className="flex h-[min(800px,calc(100dvh-40px))] w-full max-w-[1000px] flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-2xl">
      <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-100 px-5 sm:px-6"><h1 id="settings-title" className="text-sm font-semibold text-slate-700">工作区设置</h1><button type="button" aria-label="关闭设置" onClick={props.onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"><X className="size-4" /></button></header>
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <nav aria-label="设置类别" className="flex shrink-0 gap-1 overflow-x-auto border-b border-slate-100 bg-slate-50/70 p-3 md:w-44 md:flex-col md:gap-2 md:overflow-visible md:border-b-0 md:border-r md:p-4">{sections.map(({ id, label, icon: Icon }) => <button type="button" key={id} aria-current={props.section === id ? "page" : undefined} onClick={() => props.onSectionChange(id)} className={cn("flex shrink-0 items-center gap-2 rounded-xl px-3 py-2.5 text-xs transition", props.section === id ? "bg-white font-semibold text-blue-700 shadow-xs" : "text-slate-500 hover:bg-white")}><Icon className="size-4" />{label}</button>)}</nav>
        <main className="min-w-0 flex-1 overflow-y-auto overscroll-contain p-5 sm:p-7">
          {props.section === "providers" && <ProviderManager providers={props.providers} onChanged={props.onProvidersChanged} />}
          {props.section === "sources" && <SourcesPanel onChanged={props.onDocumentsChanged} />}
          {props.section === "usage" && <UsagePanel />}
          {props.section === "guide" && <GuidePanel />}
        </main>
      </div>
    </div>
  </div>;
}
