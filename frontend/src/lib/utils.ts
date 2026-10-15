import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";


export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}


export function formatTokens(value: number) {
  return new Intl.NumberFormat("zh-CN", { notation: value > 99_999 ? "compact" : "standard" }).format(value);
}
