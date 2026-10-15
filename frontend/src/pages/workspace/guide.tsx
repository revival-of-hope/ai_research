import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";

import { GuidePanel } from "@/components/settings/settings-dialog";

export function GuidePage() {
  return <div className="mx-auto max-w-3xl"><GuidePanel /><Link to="/research" className="mt-6 inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-medium text-white hover:bg-blue-700">前往研究工作台<ArrowUpRight className="size-4" /></Link></div>;
}
