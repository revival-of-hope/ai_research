import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { User } from "@/lib/types";


export function LoginPage() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/research" replace />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      await api<User>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
      });
      await refresh();
      navigate((location.state as { from?: string } | null)?.from || "/research", { replace: true });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "登录失败");
    } finally { setBusy(false); }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader><CardTitle>登录研究工作区</CardTitle><CardDescription>继续你的研究，查看资料与历史报告。</CardDescription></CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={submit}>
            <label className="block text-sm font-medium">邮箱<Input disabled={busy} className="mt-1" name="email" type="email" autoComplete="email" required /></label>
            <label className="block text-sm font-medium">密码<Input disabled={busy} className="mt-1" name="password" type="password" autoComplete="current-password" required /></label>
            {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
            <Button className="w-full" disabled={busy}>{busy ? "正在登录" : "登录"}</Button>
          </form>
          <p className="mt-5 text-center text-sm text-slate-500">还没有账户 <Link className="text-blue-600 hover:underline" to="/register">注册</Link></p>
        </CardContent>
      </Card>
    </main>
  );
}
