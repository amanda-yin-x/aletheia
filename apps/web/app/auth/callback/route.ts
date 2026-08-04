import { NextRequest, NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { getSupabasePublicConfig } from "@/lib/supabase/config";
import { CSRF_COOKIE_NAME, safeNextPath } from "@/lib/security";

export async function GET(request: NextRequest) {
  const nextPath = safeNextPath(request.nextUrl.searchParams.get("next"));
  const code = request.nextUrl.searchParams.get("code");
  const redirectBase = getSupabasePublicConfig()?.siteUrl || request.nextUrl.origin;

  try {
    // Accept only Supabase's PKCE authorization-code callback. A raw token_hash
    // link is portable between browsers and can create login-CSRF/session-swap
    // behavior; PKCE binds exchange to the initiating browser's verifier cookie.
    if (!code) throw new Error("Missing PKCE authorization code.");
    const supabase = await createSupabaseServerClient();
    const result = await supabase.auth.exchangeCodeForSession(code);
    if (result.error) throw result.error;

    const response = NextResponse.redirect(new URL(nextPath, redirectBase));
    response.cookies.set(CSRF_COOKIE_NAME, crypto.randomUUID(), {
      httpOnly: false,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
      maxAge: 60 * 60 * 8,
    });
    response.headers.set("Cache-Control", "private, no-store");
    return response;
  } catch {
    const response = NextResponse.redirect(new URL(`/login?error=callback_failed&next=${encodeURIComponent(nextPath)}`, redirectBase));
    response.headers.set("Cache-Control", "private, no-store");
    return response;
  }
}
