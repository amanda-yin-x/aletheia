import { describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const state = vi.hoisted(() => ({ requestCookieValue: null as string | null }));

vi.mock("@/lib/supabase/config", () => ({
  getSupabasePublicConfig: () => ({ url: "https://project.supabase.co", publishableKey: "publishable", turnstileSiteKey: null, siteUrl: "https://aletheia.example" }),
  isLocalAuthBypassEnabled: () => false,
}));

vi.mock("@supabase/ssr", () => ({
  createServerClient: (_url: string, _key: string, options: { cookies: { getAll: () => Array<{ name: string; value: string }>; setAll: (values: Array<{ name: string; value: string; options: { path: string } }>) => void } }) => ({
    auth: {
      getClaims: async () => {
        options.cookies.setAll([{ name: "sb-refreshed", value: "new-token", options: { path: "/" } }]);
        state.requestCookieValue = options.cookies.getAll().find((cookie) => cookie.name === "sb-refreshed")?.value || null;
        return { data: { claims: { sub: "user-123" } }, error: null };
      },
    },
  }),
}));

import { middleware } from "@/middleware";

describe("Supabase session middleware", () => {
  it("puts refreshed cookies on both the protected request and response", async () => {
    const request = new NextRequest("https://aletheia.example/projects/project-1/overview", { headers: { cookie: "sb-old=old-token" } });
    const response = await middleware(request);
    expect(state.requestCookieValue).toBe("new-token");
    expect(response.headers.get("set-cookie")).toContain("sb-refreshed=new-token");
    expect(response.headers.get("cache-control")).toBe("private, no-store");
  });
});
