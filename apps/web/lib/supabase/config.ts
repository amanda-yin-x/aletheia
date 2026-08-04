export interface SupabasePublicConfig {
  url: string;
  publishableKey: string;
  turnstileSiteKey: string;
  siteUrl: string;
}

const trimTrailingSlash = (value: string) => value.replace(/\/+$/, "");

function validRuntimeUrl(value: string, production: boolean): boolean {
  try {
    const parsed = new URL(value);
    if (parsed.username || parsed.password || !new Set(["http:", "https:"]).has(parsed.protocol)) return false;
    return !production || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export function getSupabasePublicConfig(): SupabasePublicConfig | null {
  const url = process.env.SUPABASE_URL?.trim();
  const publishableKey = process.env.SUPABASE_PUBLISHABLE_KEY?.trim();
  const turnstileSiteKey = process.env.TURNSTILE_SITE_KEY?.trim();
  const siteUrl = process.env.SITE_URL?.trim() || "http://localhost:3000";
  const production = process.env.NODE_ENV === "production";
  if (!url || !publishableKey || (production && !turnstileSiteKey) || !validRuntimeUrl(url, production) || !validRuntimeUrl(siteUrl, production)) return null;

  return {
    url: trimTrailingSlash(url),
    publishableKey,
    turnstileSiteKey: turnstileSiteKey || "",
    siteUrl: trimTrailingSlash(siteUrl),
  };
}

export function isLocalAuthBypassEnabled(): boolean {
  const mode = process.env.AUTH_MODE?.trim().toLowerCase();
  if (mode === "supabase") return false;
  if (mode === "local") {
    try {
      const siteUrl = new URL(process.env.SITE_URL?.trim() || "http://localhost:3000");
      return siteUrl.hostname === "localhost" || siteUrl.hostname === "127.0.0.1" || siteUrl.hostname === "::1" || siteUrl.hostname === "[::1]";
    } catch {
      return false;
    }
  }
  return process.env.NODE_ENV !== "production" && !getSupabasePublicConfig();
}
