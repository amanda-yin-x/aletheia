import { NextRequest, NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { getSupabasePublicConfig, isLocalAuthBypassEnabled } from "@/lib/supabase/config";
import { CSRF_COOKIE_NAME, CSRF_HEADER_NAME, expectedRequestOrigin, mutationRequestIsTrusted } from "@/lib/security";

export async function POST(request: NextRequest) {
  const config = getSupabasePublicConfig();
  const trusted = mutationRequestIsTrusted({
    method: request.method,
    requestOrigin: request.headers.get("origin"),
    expectedOrigin: expectedRequestOrigin(request.url, config?.siteUrl),
    csrfHeader: request.headers.get(CSRF_HEADER_NAME),
    csrfCookie: request.cookies.get(CSRF_COOKIE_NAME)?.value || null,
    secFetchSite: request.headers.get("sec-fetch-site"),
  });
  if (!trusted) return NextResponse.json({ error: "untrusted_request" }, { status: 403 });

  if (!isLocalAuthBypassEnabled()) {
    if (!config) return NextResponse.json({ error: "auth_not_configured" }, { status: 503 });
    const supabase = await createSupabaseServerClient();
    const { error } = await supabase.auth.signOut({ scope: "local" });
    if (error) return NextResponse.json({ error: "logout_failed" }, { status: 502 });
  }
  const response = NextResponse.json({ ok: true });
  response.cookies.delete(CSRF_COOKIE_NAME);
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}
