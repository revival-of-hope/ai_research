export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function errorMessage(status: number, raw: string): string {
  const fallback = `Request failed with ${status}`;
  if (!raw) return fallback;
  try {
    const body = JSON.parse(raw) as { detail?: unknown; message?: string };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((item: { msg?: string }) => item.msg || "请求参数有误").join("；");
    return body.message || fallback;
  } catch {
    return raw;
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, { ...options, headers, credentials: "include" });
  if (!response.ok) {
    const raw = await response.text();
    throw new ApiError(response.status, errorMessage(response.status, raw));
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export type StreamEvent = { type: string; data: Record<string, unknown> };

function parseEvent(block: string): StreamEvent | undefined {
  let type = "message";
  const data: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("event:")) type = line.slice(6).trim();
    if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (data.length === 0) return undefined;
  return { type, data: JSON.parse(data.join("\n")) as Record<string, unknown> };
}

export async function streamSse(
  path: string,
  payload: object,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`/api${path}`, {
    method: "POST",
    credentials: "include",
    headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    const raw = await response.text();
    throw new ApiError(response.status, errorMessage(response.status, raw));
  }
  if (!response.body) throw new ApiError(502, "浏览器没有收到流式响应体");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let boundary = /\r?\n\r?\n/.exec(buffer);
      while (boundary) {
        const block = buffer.slice(0, boundary.index);
        buffer = buffer.slice(boundary.index + boundary[0].length);
        const event = parseEvent(block);
        if (event) onEvent(event);
        boundary = /\r?\n\r?\n/.exec(buffer);
      }
      if (done) break;
    }
    const finalEvent = parseEvent(buffer.trim());
    if (finalEvent) onEvent(finalEvent);
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
