import { useEffect, useState } from "react";

import { ProviderManager } from "@/components/settings/provider-manager";
import { api } from "@/lib/api";
import type { Provider } from "@/lib/types";

export function ProviderForm() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setError("");
    try { setProviders(await api<Provider[]>("/account/providers")); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "模型预设加载失败"); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, []);

  if (loading) return <p role="status" className="text-sm text-slate-400">正在读取模型预设…</p>;
  return <>{error && <p role="alert" className="mb-4 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}<button className="ml-3 underline" onClick={() => void load()}>重试</button></p>}<ProviderManager providers={providers} onChanged={async () => load()} /></>;
}
