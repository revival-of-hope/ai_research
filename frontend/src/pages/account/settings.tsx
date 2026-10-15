import { ProviderForm } from "@/pages/account/provider-form";


export function SettingsPage() {
  return (
    <div className="space-y-7">
      <div><h1 className="text-2xl font-semibold">工作区设置</h1><p className="mt-1 text-sm text-slate-500">连接支持 Responses API 的模型服务，填写实际可用的模型 ID。</p></div>
      <ProviderForm />
    </div>
  );
}
