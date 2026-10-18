import type { Message } from "@/lib/types";

/** Old replies without a mode only show research controls when they contain research activity. */
export function isDeepResearch(message: Message): boolean {
  if (message.mode) return message.mode === "deep";
  return (message.events ?? []).some((event) => ["plan", "agent", "progress"].includes(event.type));
}
