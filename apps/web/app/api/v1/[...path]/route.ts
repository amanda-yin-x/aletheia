import { NextRequest, NextResponse } from "next/server";
import { getVerifiedAccessToken } from "@/lib/supabase/auth";
import { getSupabasePublicConfig, isLocalAuthBypassEnabled } from "@/lib/supabase/config";
import { CSRF_COOKIE_NAME, CSRF_HEADER_NAME, expectedRequestOrigin, mutationRequestIsTrusted, parseApiOrigin } from "@/lib/security";

export const dynamic = "force-dynamic";

const HOP_BY_HOP_HEADERS = new Set([
  "authorization", "connection", "cookie", "host", "keep-alive", "proxy-authenticate",
  "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade",
  "x-aletheia-origin-token", CSRF_HEADER_NAME.toLowerCase(),
]);
const RETRYABLE_STATUSES = new Set([502, 503, 504]);

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

async function wait(milliseconds: number) {
  await new Promise((resolve) => setTimeout(resolve, milliseconds));
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
  const target = new URL(`/api/v1/${path.map(encodeURIComponent).join("/")}`, baseUrl);
  target.search = request.nextUrl.search;
  const method = request.method.toUpperCase();
  const hasBody = !["GET", "HEAD"].includes(method);
  const init: RequestInit & { duplex?: "half" } = {
    method,
    headers: copyRequestHeaders(request, auth.accessToken, originToken),
    body: hasBody ? request.body : null,
    redirect: "manual",
  };
  if (hasBody) init.duplex = "half";

  try {
    let upstream: Response | null = null;
    const retries = hasBody ? 0 : 2;
    for (let attempt = 0; attempt <= retries; attempt += 1) {
      upstream = await fetch(target, init);
      if (!RETRYABLE_STATUSES.has(upstream.status) || attempt === retries) break;
      await upstream.body?.cancel();
      await wait(250 * 2 ** attempt);
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
