import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn("inline-flex rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700", className)}
      {...props}
    />
  );
}
