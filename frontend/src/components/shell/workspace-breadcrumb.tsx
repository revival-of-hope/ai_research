import { ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

export function WorkspaceBreadcrumb({ current }: { current: string }) {
  return <nav aria-label="面包屑" className="flex min-w-0 items-center gap-2 text-sm">
    <Link to="/research" className="shrink-0 text-slate-400 hover:text-blue-700">工作台</Link>
    <ChevronRight className="size-3.5 shrink-0 text-slate-300" aria-hidden="true" />
    <span aria-current="page" className="min-w-0 truncate font-medium text-slate-700">{current}</span>
  </nav>;
}
