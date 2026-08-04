import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import {
  getSupabaseCookieOptions,
  getSupabasePublicConfig,
  isLocalAuthBypassEnabled,
} from "@/lib/supabase/config";

const protectedPrefixes = ["/projects/", "/runs/", "/reports/", "/scenario-results/"];

function isProtectedPath(pathname: string): boolean {
  return protectedPrefixes.some((prefix) => pathname.startsWith(prefix));
}

export async function middleware(request: NextRequest) {
  if (process.env.NODE_ENV === "production" && request.nextUrl.protocol === "http:") {
    const secureUrl = request.nextUrl.clone();
    secureUrl.protocol = "https:";
    return NextResponse.redirect(secureUrl, 308);
  }

  if (!isProtectedPath(request.nextUrl.pathname) || isLocalAuthBypassEnabled()) return NextResponse.next();

  const config = getSupabasePublicConfig();
  if (!config) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", `${request.nextUrl.pathname}${request.nextUrl.search}`);
    return NextResponse.redirect(login);
  }

  let response = NextResponse.next({ request: { headers: new Headers(request.headers) } });
  const supabase = createServerClient(config.url, config.publishableKey, {
    cookieOptions: getSupabaseCookieOptions(config.siteUrl),
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll(cookiesToSet) {
        // Update both sides: the protected Server Component must see refreshed
        // credentials on this request, and the browser must persist them.
        for (const { name, value } of cookiesToSet) request.cookies.set(name, value);
        response = NextResponse.next({ request: { headers: new Headers(request.headers) } });
        for (const { name, value, options } of cookiesToSet) response.cookies.set(name, value, options);
      },
    },
  });
  const { data, error } = await supabase.auth.getClaims();
  if (error || !data?.claims?.sub) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", `${request.nextUrl.pathname}${request.nextUrl.search}`);
    const redirect = NextResponse.redirect(login);
    redirect.headers.set("Cache-Control", "private, no-store");
    return redirect;
  }
  response.headers.set("Cache-Control", "private, no-store");
  response.headers.set("Vary", "Cookie");
  return response;
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico|css|js|map|woff|woff2|ttf)$).*)",
  ],
};
