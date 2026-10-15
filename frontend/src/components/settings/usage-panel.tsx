import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Usage } from "@/lib/types";
import { formatTokens } from "@/lib/utils";

export function UsagePanel() {
  const [usage, setUsage] = useState<Usage>();
  const [error, setError] = useState("");

  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    setError("");
    void api<Usage>("/account/usage").then(setUsage).catch((reason) => {
      setError(reason instanceof Error ? reason.message : "用量加载失败");
    });
  }, [attempt]);

  if (error) return <div role="alert" className="rounded-xl bg-red-50 p-4 text-xs leading-6 text-red-700"><p>{error}</p><button className="mt-2 font-medium underline" onClick={() => setAttempt((value) => value + 1)}>重新加载用量</button></div>;
  if (!usage) return <p className="text-sm text-slate-500">正在加载用量…</p>;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold">Token 用量</h2>
        <p className="mt-1 text-xs leading-6 text-slate-500">汇总研究过程中所有智能体调用的用量，按模型预设分别统计。</p>
        <p className="mt-1 text-[10px] text-slate-400">今日与本月按服务端 UTC 时间划分。</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {[
          ["今日", usage.today_tokens],
          ["本月", usage.month_tokens],
          ["累计", usage.lifetime_tokens],
        ].map(([label, value]) => (
          <div key={label as string} className="rounded-2xl border border-slate-200 p-4">
            <p className="text-xs text-slate-500">{label}</p>
            <p className="mt-2 text-2xl font-semibold">{formatTokens(value as number)}</p>
          </div>
        ))}
      </div>
      <div className="space-y-3">
        <h3 className="text-sm font-medium text-slate-800">按模型预设</h3>
        {usage.by_provider.length === 0 && <p className="text-sm text-slate-500">还没有模型调用记录。</p>}
        {usage.by_provider.map((item, index) => (
          <div key={`${item.provider_id}-${index}`} className="rounded-2xl border border-slate-200 p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0"><p className="truncate text-sm font-medium">{item.provider_name}</p><p className="truncate text-xs text-slate-500">{item.model}</p></div>
              <p className="text-lg font-semibold">{formatTokens(item.total_tokens)}</p>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-500 sm:grid-cols-4">
              <span>今日 {formatTokens(item.today_tokens)}</span>
              <span>本月 {formatTokens(item.month_tokens)}</span>
              <span>输入 {formatTokens(item.input_tokens)}</span>
              <span>输出 {formatTokens(item.output_tokens)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
