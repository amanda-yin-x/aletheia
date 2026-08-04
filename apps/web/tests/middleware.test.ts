import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const state = vi.hoisted(() => ({ requestCookieValue: null as string | null }));

vi.mock("@/lib/supabase/config", () => ({
  getSupabasePublicConfig: () => ({ url: "https://project.supabase.co", publishableKey: "publishable", turnstileSiteKey: "site-key", siteUrl: "https://aletheia.example" }),
  getSupabaseCookieOptions: (siteUrl: string) => ({ path: "/", sameSite: "lax", secure: process.env.NODE_ENV === "production" || new URL(siteUrl).protocol === "https:" }),
  isLocalAuthBypassEnabled: () => false,
}));

vi.mock("@supabase/ssr", () => ({
  createServerClient: vi.fn((_url: string, _key: string, options: {
    cookieOptions: { path: "/"; sameSite: "lax"; secure: boolean };
    cookies: {
      getAll: () => Array<{ name: string; value: string }>;
      setAll: (values: Array<{ name: string; value: string; options: { path: string; sameSite: "lax"; secure: boolean } }>) => void;
    };
  }) => ({
    auth: {
      getClaims: async () => {
        options.cookies.setAll([{ name: "sb-refreshed", value: "new-token", options: options.cookieOptions }]);
        state.requestCookieValue = options.cookies.getAll().find((cookie) => cookie.name === "sb-refreshed")?.value || null;
        return { data: { claims: { sub: "user-123" } }, error: null };
      },
    },
  })),
}));

import { createServerClient } from "@supabase/ssr";
import { middleware } from "@/middleware";

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllEnvs();
  state.requestCookieValue = null;
});

describe("Supabase session middleware", () => {
  it("puts refreshed cookies on both the protected request and response", async () => {
    const request = new NextRequest("https://aletheia.example/projects/project-1/overview", { headers: { cookie: "sb-old=old-token" } });
    const response = await middleware(request);
    expect(state.requestCookieValue).toBe("new-token");
    expect(response.headers.get("set-cookie")).toContain("sb-refreshed=new-token");
    expect(response.headers.get("cache-control")).toBe("private, no-store");
  });

  it("keeps the demo entry public and does not initialize auth middleware", async () => {
    const response = await middleware(new NextRequest("https://aletheia.example/demo"));
    expect(response.status).toBe(200);
    expect(createServerClient).not.toHaveBeenCalled();
  });

  it("permanently redirects production HTTP requests to the same HTTPS URL", async () => {
    vi.stubEnv("NODE_ENV", "production");
    const response = await middleware(new NextRequest("http://aletheia.example/demo?case=northstar"));
    expect(response.status).toBe(308);
    expect(response.headers.get("location")).toBe("https://aletheia.example/demo?case=northstar");
    expect(createServerClient).not.toHaveBeenCalled();
  });

  it("marks refreshed production session cookies Secure and SameSite=Lax", async () => {
    vi.stubEnv("NODE_ENV", "production");
    const response = await middleware(new NextRequest("https://aletheia.example/projects/project-1/overview"));
    const setCookie = response.headers.get("set-cookie") || "";
    expect(setCookie).toMatch(/Secure/i);
    expect(setCookie).toMatch(/SameSite=Lax/i);
    expect(setCookie).toMatch(/Path=\//i);
  });
});
