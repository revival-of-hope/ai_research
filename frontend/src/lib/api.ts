export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

type ConnectionPhase = "connect" | "response" | "stream";
const connectionMessages: Record<ConnectionPhase, string> = {
  connect: "连接应用服务失败，请检查网络或服务状态后重试。若持续失败，请重新加载页面并确认服务可用。",
  response: "读取服务响应时连接中断，请检查网络或服务状态后重新加载。提交操作可能已经执行，请先刷新确认结果。",
  stream: "回答连接中断，当前内容可能尚未保存。请先复制已有内容，检查网络或服务状态后重新发送。",
};

export class ApiConnectionError extends Error {
  constructor(public phase: ConnectionPhase, cause: unknown) {
    super(connectionMessages[phase], { cause });
    this.name = "ApiConnectionError";
  }
}

function connectionFailure(reason: unknown, phase: ConnectionPhase, signal?: AbortSignal | null): never {
  if (reason && typeof reason === "object" && "name" in reason && reason.name === "AbortError") throw reason;
  if (signal?.aborted) throw new DOMException("请求已取消", "AbortError");
  throw new ApiConnectionError(phase, reason);
}

async function request(path: string, options: RequestInit): Promise<Response> {
  try {
    return await fetch(`/api${path}`, { ...options, credentials: "include" });
  } catch (reason) { return connectionFailure(reason, "connect", options.signal); }
}

async function readResponse<T>(read: () => Promise<T>, signal?: AbortSignal | null): Promise<T> {
  try { return await read(); }
  catch (reason) {
    if (reason instanceof SyntaxError) throw new Error("服务返回了无法解析的响应，请重新加载页面后重试。", { cause: reason });
    return connectionFailure(reason, "response", signal);
  }
}

function errorMessage(status: number, raw: string): string {
  const fallback = `请求失败（HTTP ${status}），请稍后重试。`;
  if (!raw) return fallback;
  try {
    const body = JSON.parse(raw) as { detail?: unknown; message?: string };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return body.detail.map((item: { msg?: string }) => item.msg || "请求参数有误").join("；");
    return typeof body.message === "string" ? body.message : fallback;
  } catch {
    return raw.trim().startsWith("<") ? fallback : raw;
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await request(path, { ...options, headers });
  if (!response.ok) {
    const raw = await readResponse(() => response.text(), options.signal);
    throw new ApiError(response.status, errorMessage(response.status, raw));
  }
  if (response.status === 204) return undefined as T;
  return readResponse(() => response.json() as Promise<T>, options.signal);
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
  try {
    const value: unknown = JSON.parse(data.join("\n"));
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new SyntaxError("Expected an event object");
    return { type, data: value as Record<string, unknown> };
  } catch (reason) {
    throw new Error("收到的回答数据不完整或格式异常。请先复制已有内容，检查服务状态后重新发送。", { cause: reason });
  }
}

export async function streamSse(
  path: string,
  payload: object,
  onEvent: (event: StreamEvent) => void | boolean,
  signal?: AbortSignal,
): Promise<void> {
  const response = await request(path, {
    method: "POST",
    headers: { Accept: "text/event-stream", "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) {
    const raw = await readResponse(() => response.text(), signal);
    throw new ApiError(response.status, errorMessage(response.status, raw));
  }
  if (!response.body) throw new ApiError(502, "浏览器没有收到流式响应体");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      let chunk: ReadableStreamReadResult<Uint8Array>;
      try { chunk = await reader.read(); }
      catch (reason) { return connectionFailure(reason, "stream", signal); }
      const { done, value } = chunk;
      buffer += decoder.decode(value, { stream: !done });
      let boundary = /\r?\n\r?\n/.exec(buffer);
      while (boundary) {
        const block = buffer.slice(0, boundary.index);
        buffer = buffer.slice(boundary.index + boundary[0].length);
        const event = parseEvent(block);
        if (event && onEvent(event) === false) return;
        boundary = /\r?\n\r?\n/.exec(buffer);
      }
      if (done) break;
    }
    const finalEvent = parseEvent(buffer.trim());
    if (finalEvent && onEvent(finalEvent) === false) return;
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
