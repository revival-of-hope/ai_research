import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { User } from "@/lib/types";


export function RegisterPage() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  if (user) return <Navigate to="/research" replace />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password"));
    if (password !== form.get("confirm")) { setBusy(false); setError("两次输入的密码不一致"); return; }
    try {
      await api<User>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      await refresh(); navigate("/research", { replace: true });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "注册失败");
    } finally { setBusy(false); }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-slate-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader><CardTitle>创建账户</CardTitle><CardDescription>无需邮箱验证码，创建后将直接登录。</CardDescription></CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={submit}>
            <label className="block text-sm font-medium">邮箱<Input disabled={busy} className="mt-1" name="email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
            <label className="block text-sm font-medium">密码<Input disabled={busy} className="mt-1" name="password" type="password" autoComplete="new-password" minLength={10} aria-describedby="password-hint" required /><span id="password-hint" className="mt-1 block text-xs font-normal text-slate-400">至少 10 位字符</span></label>
            <label className="block text-sm font-medium">确认密码<Input disabled={busy} className="mt-1" name="confirm" type="password" autoComplete="new-password" minLength={10} required /></label>
            {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
            <Button className="w-full" disabled={busy}>{busy ? "正在创建" : "注册并登录"}</Button>
          </form>
          <p className="mt-5 text-center text-sm text-slate-500">已有账户 <Link className="text-blue-600 hover:underline" to="/login">登录</Link></p>
        </CardContent>
      </Card>
    </main>
  );
}
