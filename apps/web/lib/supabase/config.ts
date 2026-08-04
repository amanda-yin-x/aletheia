export interface SupabasePublicConfig {
  url: string;
  publishableKey: string;
  turnstileSiteKey: string;
  siteUrl: string;
  githubAuthEnabled: boolean;
  emailOtpEnabled: boolean;
}

export interface SupabaseCookieOptions {
  path: "/";
  sameSite: "lax";
  secure: boolean;
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
    githubAuthEnabled: process.env.GITHUB_AUTH_ENABLED?.trim().toLowerCase() === "true",
    emailOtpEnabled: process.env.EMAIL_OTP_ENABLED?.trim().toLowerCase() === "true",
  };
}

/**
 * Keep the browser, Server Components, and middleware on one cookie policy.
 * Production cookies are always secure; HTTPS development URLs opt in while
 * plain HTTP localhost remains usable.
 */
export function getSupabaseCookieOptions(siteUrl: string): SupabaseCookieOptions {
  let siteUsesHttps = false;
  try {
    siteUsesHttps = new URL(siteUrl).protocol === "https:";
  } catch {
    // Runtime config validation reports malformed URLs before this is called.
  }

  return {
    path: "/",
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production" || siteUsesHttps,
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
