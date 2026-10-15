import { LoaderCircle, RefreshCw, Search, ShieldCheck, Users } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AdminUser } from "@/lib/types";
import { formatTokens } from "@/lib/utils";

export function AdminPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState<number>();
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setUsers(await api<AdminUser[]>("/admin/users")); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "账户加载失败"); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { if (user?.is_admin) void load(); }, [user?.is_admin, load]);
  if (!user?.is_admin) return <Navigate to="/research" replace />;

  async function update(item: AdminUser, changes: { is_active?: boolean; is_admin?: boolean }) {
    setPending(item.id); setError("");
    try {
      const saved = await api<AdminUser>(`/admin/users/${item.id}`, { method: "PATCH", body: JSON.stringify(changes) });
      setUsers((current) => current.map((entry) => entry.id === item.id ? { ...entry, ...saved, total_tokens: saved.total_tokens ?? entry.total_tokens } : entry));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "账户更新失败"); }
    finally { setPending(undefined); }
  }
  const matches = users.filter((item) => item.email.toLocaleLowerCase().includes(query.toLocaleLowerCase()));

  return <div className="space-y-6">
    <div className="flex items-start justify-between gap-4"><div><h1 className="flex items-center gap-2 text-2xl font-semibold"><ShieldCheck className="size-6 text-blue-600" />用户管理</h1><p className="mt-2 text-sm text-slate-500">管理账户访问权限，查看累计模型用量。</p></div><button disabled={loading || pending !== undefined} onClick={() => void load()} className="rounded-xl border border-slate-200 bg-white p-2.5 text-slate-400 hover:text-blue-600" aria-label="刷新账户列表"><RefreshCw className={"size-4 " + (loading ? "animate-spin" : "")} /></button></div>
    <div className="grid gap-3 sm:grid-cols-3">{[["账户总数", users.length], ["已启用", users.filter((item) => item.is_active).length], ["管理员", users.filter((item) => item.is_admin).length]].map(([title, count]) => <div key={title} className="rounded-2xl border border-slate-200 bg-white p-4"><p className="text-xs text-slate-400">{title}</p><p className="mt-2 text-2xl font-semibold text-slate-700">{count}</p></div>)}</div>
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white"><div className="flex items-center justify-between gap-3 border-b border-slate-100 p-4"><h2 className="flex items-center gap-2 text-sm font-semibold text-slate-700"><Users className="size-4 text-slate-400" />账户列表</h2><label className="flex w-48 max-w-[60%] items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-slate-400"><Search className="size-3.5 shrink-0" /><input aria-label="按邮箱搜索账户" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索邮箱" className="min-w-0 w-full bg-transparent text-xs text-slate-600 outline-none" /></label></div>
      {error && <p role="alert" className="m-4 rounded-xl bg-red-50 px-3 py-2 text-xs leading-6 text-red-700">{error}</p>}
      {loading && !users.length ? <p role="status" className="flex items-center justify-center gap-2 p-12 text-xs text-slate-400"><LoaderCircle className="size-4 animate-spin" />正在读取账户…</p> : !matches.length ? <p className="p-10 text-center text-xs text-slate-400">没有匹配的账户</p> : <ul className="divide-y divide-slate-100">{matches.map((item) => <li key={item.id} className="flex flex-wrap items-center gap-x-4 gap-y-3 px-4 py-4 sm:flex-nowrap sm:px-5"><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="truncate text-xs font-semibold text-slate-700">{item.email}</p>{item.id === user.id && <span className="rounded bg-blue-50 px-1.5 py-0.5 text-[9px] text-blue-600">当前账户</span>}{item.is_admin && <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] text-slate-500">管理员</span>}<span className={"size-1.5 rounded-full " + (item.is_active ? "bg-emerald-400" : "bg-slate-300")} aria-hidden="true" /><span className="text-[10px] text-slate-400">{item.is_active ? "已启用" : "已停用"}</span></div><p className="mt-1.5 text-[10px] text-slate-400">累计 {formatTokens(item.total_tokens)} tokens<span className="mx-2">·</span>注册于 {new Date(item.created_at).toLocaleDateString("zh-CN")}</p></div><div className="flex w-full shrink-0 justify-end gap-2 sm:w-auto"><button disabled={pending !== undefined || item.id === user.id} onClick={() => void update(item, { is_active: !item.is_active })} className="rounded-lg border border-slate-200 px-3 py-1.5 text-[11px] text-slate-600 hover:bg-slate-50 disabled:opacity-35">{pending === item.id ? "处理中…" : item.is_active ? "停用账户" : "启用账户"}</button><button disabled={pending !== undefined || item.id === user.id} onClick={() => void update(item, { is_admin: !item.is_admin })} className="rounded-lg border border-slate-200 px-3 py-1.5 text-[11px] text-slate-600 hover:bg-slate-50 disabled:opacity-35">{item.is_admin ? "移除管理权限" : "设为管理员"}</button></div></li>)}</ul>}
    </div>
  </div>;
}
