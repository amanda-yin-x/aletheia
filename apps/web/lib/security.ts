export const CSRF_COOKIE_NAME = "aletheia_csrf";
export const CSRF_HEADER_NAME = "X-Aletheia-CSRF";

export function parseApiOrigin(value: string, production: boolean): URL | null {
  try {
    const url = new URL(value);
    if (!new Set(["http:", "https:"]).has(url.protocol) || url.username || url.password) return null;
    if (url.pathname !== "/" || url.search || url.hash) return null;
    if (production && url.protocol !== "https:") return null;
    return url;
  } catch {
    return null;
  }
}

export function safeNextPath(value: string | null | undefined, fallback = "/demo"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return fallback;
  try {
    const parsed = new URL(value, "https://aletheia.invalid");
    return parsed.origin === "https://aletheia.invalid" ? `${parsed.pathname}${parsed.search}${parsed.hash}` : fallback;
  } catch {
    return fallback;
  }
}

export function expectedRequestOrigin(requestUrl: string, configuredSiteUrl?: string | null): string {
  const candidate = configuredSiteUrl?.trim() || requestUrl;
  return new URL(candidate).origin;
}

export function isMutationMethod(method: string): boolean {
  return !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());
}

export function mutationRequestIsTrusted(input: {
  method: string;
  requestOrigin: string | null;
  expectedOrigin: string;
  csrfHeader: string | null;
  csrfCookie: string | null;
  secFetchSite?: string | null;
}): boolean {
  if (!isMutationMethod(input.method)) return true;
  if (!input.requestOrigin || input.requestOrigin !== input.expectedOrigin) return false;
  if (!input.csrfHeader || !input.csrfCookie || input.csrfHeader !== input.csrfCookie) return false;
  return !input.secFetchSite || input.secFetchSite === "same-origin" || input.secFetchSite === "same-site";
}
