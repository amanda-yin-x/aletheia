import { CSRF_COOKIE_NAME, CSRF_HEADER_NAME, isMutationMethod } from "./security";
import type { APIError } from "./types";

export const API_IS_CONFIGURED = true;
export const API_URL = "";

const RETRYABLE_GATEWAY_STATUSES = new Set([502, 503, 504]);
const MAX_RETRY_DELAY_MS = 4_000;
let csrfRequest: Promise<string> | null = null;

export class RequestError extends Error {
  constructor(public payload: APIError, public status: number) {
    super(payload.message);
    this.name = "RequestError";
  }
}

export interface ApiRequestInit extends RequestInit {
  coldStartRetries?: number;
  coldStartTimeoutMs?: number;
  retryMutation?: boolean;
  idempotencyKey?: string;
  onRetry?: (event: { attempt: number; delayMs: number; status: number | null }) => void;
}

function cookieValue(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${encodeURIComponent(name)}=`;
  for (const part of document.cookie.split(";")) {
    const value = part.trim();
    if (value.startsWith(prefix)) return decodeURIComponent(value.slice(prefix.length));
  }
  return null;
}

export async function ensureCsrfToken(): Promise<string> {
  const existing = cookieValue(CSRF_COOKIE_NAME);
  if (existing) return existing;
  if (!csrfRequest) {
    csrfRequest = fetch("/auth/csrf", { credentials: "same-origin", cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("Could not initialize request protection.");
        const payload = await response.json() as { token?: string };
        if (!payload.token) throw new Error("Request protection did not return a token.");
        return payload.token;
      })
      .finally(() => { csrfRequest = null; });
  }
  return csrfRequest;
}

function retryDelay(response: Response | null, attempt: number, extendedWakeWindow: boolean): number {
  const retryAfter = response?.headers.get("retry-after");
  if (retryAfter) {
    const seconds = Number(retryAfter);
    if (Number.isFinite(seconds)) return Math.min(MAX_RETRY_DELAY_MS, Math.max(0, seconds * 1_000));
    const date = Date.parse(retryAfter);
    if (Number.isFinite(date)) return Math.min(MAX_RETRY_DELAY_MS, Math.max(0, date - Date.now()));
  }
  return extendedWakeWindow
    ? Math.min(8_000, 1_000 * 1.5 ** attempt)
    : Math.min(MAX_RETRY_DELAY_MS, 350 * 2 ** attempt);
}

function wait(milliseconds: number, signal?: AbortSignal | null): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(signal.reason || new DOMException("Aborted", "AbortError"));
    const timeout = globalThis.setTimeout(resolve, milliseconds);
    signal?.addEventListener("abort", () => {
      globalThis.clearTimeout(timeout);
      reject(signal.reason || new DOMException("Aborted", "AbortError"));
    }, { once: true });
  });
}

function normalizePath(path: string): string {
  if (!path.startsWith("/api/v1/") && path !== "/api/v1") throw new Error("API requests must use the same-origin /api/v1 route.");
  return path;
}

async function errorPayload(response: Response): Promise<APIError> {
  const fallback: APIError = {
    code: "request_failed",
    message: response.status === 503 ? "The service is waking up. Please try again." : "Request failed.",
    details: {},
    request_id: response.headers.get("x-request-id") || "unknown",
  };
  const payload = await response.json().catch(() => null) as Partial<APIError> | null;
  return payload && typeof payload.message === "string"
    ? { ...fallback, ...payload, details: payload.details || {} }
    : fallback;
}

export async function apiWithResponse<T>(path: string, init: ApiRequestInit = {}): Promise<{ data: T; response: Response }> {
  const { coldStartRetries, coldStartTimeoutMs, retryMutation = false, idempotencyKey, onRetry, ...requestInit } = init;
  const method = (requestInit.method || "GET").toUpperCase();
  const mutation = isMutationMethod(method);
  const headers = new Headers(requestInit.headers);
  if (requestInit.body != null && !(requestInit.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (mutation) {
    headers.set(CSRF_HEADER_NAME, await ensureCsrfToken());
    if (retryMutation || idempotencyKey) headers.set("Idempotency-Key", idempotencyKey || crypto.randomUUID());
  }

  const retries = Math.max(0, Math.min(24, coldStartRetries ?? (mutation ? (retryMutation ? 2 : 0) : 3)));
  const extendedWakeWindow = typeof coldStartTimeoutMs === "number" && coldStartTimeoutMs > 10_000;
  const deadline = Date.now() + Math.max(0, Math.min(90_000, coldStartTimeoutMs ?? 10_000));
  let response: Response | null = null;
  let lastNetworkError: unknown;
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      response = await fetch(normalizePath(path), {
        ...requestInit,
        method,
        headers,
        credentials: "same-origin",
        cache: "no-store",
      });
      if (!RETRYABLE_GATEWAY_STATUSES.has(response.status) || attempt === retries) break;
      const delayMs = retryDelay(response, attempt, extendedWakeWindow);
      if (Date.now() + delayMs > deadline) break;
      onRetry?.({ attempt: attempt + 1, delayMs, status: response.status });
      await wait(delayMs, requestInit.signal);
    } catch (error) {
      if (requestInit.signal?.aborted || (error instanceof DOMException && error.name === "AbortError")) throw error;
      lastNetworkError = error;
      if (attempt === retries) throw error;
      const delayMs = retryDelay(null, attempt, extendedWakeWindow);
      if (Date.now() + delayMs > deadline) throw error;
      onRetry?.({ attempt: attempt + 1, delayMs, status: null });
      await wait(delayMs, requestInit.signal);
    }
  }

  if (!response) throw lastNetworkError instanceof Error ? lastNetworkError : new Error("The request did not receive a response.");
  if (!response.ok) throw new RequestError(await errorPayload(response), response.status);
  const data = response.status === 204 ? undefined as T : await response.json() as T;
  return { data, response };
}

export async function api<T>(path: string, init?: ApiRequestInit): Promise<T> {
  return (await apiWithResponse<T>(path, init)).data;
}

export const shortHash = (value?: string) => value ? `${value.slice(0, 8)}…${value.slice(-4)}` : "N/A";
export const pct = (value: number | undefined) => typeof value === "number" ? `${Math.round(value * 100)}%` : "N/A";
export const label = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
