import { ProviderForm } from "@/pages/account/provider-form";


export function SettingsPage() {
  return (
    <div className="space-y-7">
      <div><h1 className="text-2xl font-semibold">工作区设置</h1><p className="mt-1 text-sm text-slate-500">选择模型提供方，配置 Responses API 地址与可用模型。</p></div>
      <ProviderForm />
    </div>
  );
}
