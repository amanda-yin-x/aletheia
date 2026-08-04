import { NextRequest, NextResponse } from "next/server";
import { getVerifiedAccessToken } from "@/lib/supabase/auth";
import { getSupabasePublicConfig, isLocalAuthBypassEnabled } from "@/lib/supabase/config";
import { CSRF_COOKIE_NAME, CSRF_HEADER_NAME, expectedRequestOrigin, mutationRequestIsTrusted, parseApiOrigin } from "@/lib/security";
import { enforceEdgeApiRateLimit } from "@/lib/edge-rate-limit";

export const dynamic = "force-dynamic";

const HOP_BY_HOP_HEADERS = new Set([
  "authorization", "connection", "content-length", "cookie", "host", "keep-alive", "proxy-authenticate",
  "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade",
  "x-aletheia-origin-token", CSRF_HEADER_NAME.toLowerCase(),
]);
const RETRYABLE_STATUSES = new Set([502, 503, 504]);
const READ_WAKE_RETRIES = 20;
const READ_WAKE_TIMEOUT_MS = 85_000;
const MUTATION_TIMEOUT_MS = 85_000;
const MAX_WAKE_DELAY_MS = 8_000;
const MAX_MUTATION_BODY_BYTES = 64 * 1024;

class UpstreamTimeoutError extends Error {
  constructor() {
    super("The upstream API did not respond before the request deadline.");
    this.name = "UpstreamTimeoutError";
  }
}

class RequestCancelledError extends Error {
  constructor() {
    super("The incoming request was cancelled.");
    this.name = "RequestCancelledError";
  }
}

function apiError(status: number, code: string, message: string) {
  const response = NextResponse.json({ code, message, details: {}, request_id: crypto.randomUUID() }, { status });
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}

function upstreamBaseUrl(): URL | null {
  const configured = process.env.API_ORIGIN_URL?.trim();
  const raw = configured || (process.env.NODE_ENV !== "production" ? "http://localhost:8000" : "");
  if (!raw) return null;
  return parseApiOrigin(raw, process.env.NODE_ENV === "production");
}

function copyRequestHeaders(request: NextRequest, accessToken: string | null, originToken: string | undefined): Headers {
  const headers = new Headers();
  request.headers.forEach((value, name) => {
    if (!HOP_BY_HOP_HEADERS.has(name.toLowerCase()) && !name.toLowerCase().startsWith("x-forwarded-")) headers.set(name, value);
  });
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  if (originToken) headers.set("X-Aletheia-Origin-Token", originToken);
  headers.set("X-Forwarded-Proto", request.nextUrl.protocol.replace(":", ""));
  headers.set("X-Forwarded-Host", request.nextUrl.host);
  return headers;
}

function copyResponseHeaders(upstream: Response, request: NextRequest): Headers {
  const headers = new Headers();
  upstream.headers.forEach((value, name) => {
    const lower = name.toLowerCase();
    if (!HOP_BY_HOP_HEADERS.has(lower) && !["set-cookie", "content-length", "content-encoding"].includes(lower)) headers.set(name, value);
  });
  const location = headers.get("location");
  if (location) {
    try {
      const parsed = new URL(location, request.url);
      if (parsed.origin !== request.nextUrl.origin) headers.set("Location", `${parsed.pathname}${parsed.search}${parsed.hash}`);
    } catch {
      headers.delete("location");
    }
  }
  headers.set("Cache-Control", "private, no-store");
  headers.set("Vary", "Cookie");
  return headers;
}

async function wait(milliseconds: number, signal: AbortSignal) {
  await new Promise<void>((resolve, reject) => {
    if (signal.aborted) {
      reject(new RequestCancelledError());
      return;
    }
    const onAbort = () => {
      globalThis.clearTimeout(timeout);
      reject(new RequestCancelledError());
    };
    const timeout = globalThis.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, milliseconds);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

async function boundedRequestBody(request: NextRequest): Promise<ArrayBuffer | null> {
  const declaredLength = request.headers.get("content-length");
  if (declaredLength !== null) {
    const parsedLength = Number(declaredLength);
    if (!Number.isSafeInteger(parsedLength) || parsedLength < 0) {
      throw new TypeError("The request Content-Length is invalid.");
    }
    if (parsedLength > MAX_MUTATION_BODY_BYTES) {
      throw new RangeError("The request body is too large.");
    }
  }
  if (!request.body) return null;

  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_MUTATION_BODY_BYTES) {
        await reader.cancel("request body too large");
        throw new RangeError("The request body is too large.");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return body.buffer as ArrayBuffer;
}

async function fetchBeforeDeadline(
  target: URL,
  init: RequestInit,
  deadline: number,
  incomingSignal: AbortSignal,
): Promise<Response> {
  const remainingMs = deadline - Date.now();
  if (remainingMs <= 0) throw new UpstreamTimeoutError();
  if (incomingSignal.aborted) throw new RequestCancelledError();
  const controller = new AbortController();
  const cancelFromIncoming = () => controller.abort(new RequestCancelledError());
  incomingSignal.addEventListener("abort", cancelFromIncoming, { once: true });
  const timeout = globalThis.setTimeout(
    () => controller.abort(new UpstreamTimeoutError()),
    remainingMs,
  );
  try {
    return await fetch(target, { ...init, signal: controller.signal });
  } catch (error) {
    if (incomingSignal.aborted) throw new RequestCancelledError();
    if (controller.signal.aborted) throw new UpstreamTimeoutError();
    throw error;
  } finally {
    globalThis.clearTimeout(timeout);
    incomingSignal.removeEventListener("abort", cancelFromIncoming);
  }
}

function wakeRetryDelay(response: Response | null, attempt: number): number {
  const retryAfter = response?.headers.get("retry-after");
  if (retryAfter) {
    const seconds = Number(retryAfter);
    if (Number.isFinite(seconds)) return Math.min(MAX_WAKE_DELAY_MS, Math.max(0, seconds * 1_000));
    const date = Date.parse(retryAfter);
    if (Number.isFinite(date)) return Math.min(MAX_WAKE_DELAY_MS, Math.max(0, date - Date.now()));
  }
  return Math.min(MAX_WAKE_DELAY_MS, 1_000 * 1.5 ** attempt);
}

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  if (request.method === "OPTIONS") return new NextResponse(null, { status: 204, headers: { Allow: "GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS" } });

  const supabaseConfig = getSupabasePublicConfig();
  if (!supabaseConfig && !isLocalAuthBypassEnabled()) return apiError(503, "auth_not_configured", "Authentication is not configured for this deployment.");

  const expectedOrigin = expectedRequestOrigin(request.url, supabaseConfig?.siteUrl || process.env.SITE_URL);
  if (!mutationRequestIsTrusted({
    method: request.method,
    requestOrigin: request.headers.get("origin"),
    expectedOrigin,
    csrfHeader: request.headers.get(CSRF_HEADER_NAME),
    csrfCookie: request.cookies.get(CSRF_COOKIE_NAME)?.value || null,
    secFetchSite: request.headers.get("sec-fetch-site"),
  })) return apiError(403, "untrusted_request", "The request failed same-origin or CSRF validation.");

  const auth = await getVerifiedAccessToken();
  if (!auth) return apiError(401, "unauthenticated", "Sign in to access this workspace.");

  const baseUrl = upstreamBaseUrl();
  const originToken = process.env.API_ORIGIN_TOKEN?.trim();
  if (!baseUrl) return apiError(503, "api_origin_not_configured", "The API connection is not configured.");
  if (process.env.NODE_ENV === "production" && !originToken) return apiError(503, "origin_token_not_configured", "The API origin credential is not configured.");

  const { path } = await context.params;
  if (!path.length || path.some((segment) => !segment || segment === "." || segment === "..")) {
    return apiError(400, "invalid_api_path", "The API path is invalid.");
  }
  try {
    const rateLimit = await enforceEdgeApiRateLimit(auth.identity.id, path);
    if (!rateLimit.allowed) {
      const response = apiError(429, "rate_limit_reached", "Too many workspace requests. Wait a minute, then try again.");
      response.headers.set("Retry-After", String(rateLimit.retryAfterSeconds));
      return response;
    }
  } catch {
    return apiError(503, "rate_limit_unavailable", "Request protection is temporarily unavailable. Please try again.");
  }
  const target = new URL(`/api/v1/${path.map(encodeURIComponent).join("/")}`, baseUrl);
  target.search = request.nextUrl.search;
  const method = request.method.toUpperCase();
  const hasBody = !["GET", "HEAD"].includes(method);
  let requestBody: ArrayBuffer | null = null;
  if (hasBody) {
    try {
      requestBody = await boundedRequestBody(request);
    } catch (error) {
      if (error instanceof RangeError) {
        return apiError(413, "request_body_too_large", `Mutation bodies are limited to ${MAX_MUTATION_BODY_BYTES} bytes.`);
      }
      return apiError(400, "invalid_request_body", "The request body could not be read safely.");
    }
  }
  const init: RequestInit = {
    method,
    headers: copyRequestHeaders(request, auth.accessToken, originToken),
    body: requestBody,
    redirect: "manual",
  };

  try {
    let upstream: Response | null = null;
    const retries = hasBody ? 0 : READ_WAKE_RETRIES;
    const deadline = Date.now() + (hasBody ? MUTATION_TIMEOUT_MS : READ_WAKE_TIMEOUT_MS);
    for (let attempt = 0; attempt <= retries; attempt += 1) {
      if (attempt > 0) {
        try {
          const retryLimit = await enforceEdgeApiRateLimit(auth.identity.id, path);
          if (!retryLimit.allowed) {
            const response = apiError(429, "rate_limit_reached", "Too many workspace requests. Wait a minute, then try again.");
            response.headers.set("Retry-After", String(retryLimit.retryAfterSeconds));
            return response;
          }
        } catch {
          return apiError(503, "rate_limit_unavailable", "Request protection is temporarily unavailable. Please try again.");
        }
      }
      try {
        upstream = await fetchBeforeDeadline(target, init, deadline, request.signal);
        if (!RETRYABLE_STATUSES.has(upstream.status) || attempt === retries) break;
        const delayMs = wakeRetryDelay(upstream, attempt);
        if (Date.now() + delayMs > deadline) break;
        await upstream.body?.cancel();
        await wait(delayMs, request.signal);
      } catch (error) {
        if (error instanceof RequestCancelledError) {
          return apiError(499, "request_cancelled", "The client cancelled the API request.");
        }
        if (error instanceof UpstreamTimeoutError) {
          return apiError(504, "api_timeout", "The API did not respond before the bounded recovery window ended.");
        }
        upstream = null;
        if (attempt === retries) break;
      }
    }
    if (!upstream) return apiError(502, "api_unavailable", "The API did not return a response.");
    return new NextResponse(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: copyResponseHeaders(upstream, request),
    });
  } catch {
    return apiError(502, "api_unavailable", "The API is temporarily unavailable. Please try again.");
  }
}

export const GET = proxy;
export const HEAD = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
