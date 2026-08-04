import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const state = vi.hoisted(() => ({
  exchangeCodeForSession: vi.fn(async () => ({ error: null })),
}));

vi.mock("@/lib/supabase/config", () => ({
  getSupabasePublicConfig: () => ({
    url: "https://project.supabase.co",
    publishableKey: "publishable",
    turnstileSiteKey: "site-key",
    siteUrl: "https://aletheia.example",
  }),
}));

vi.mock("@/lib/supabase/server", () => ({
  createSupabaseServerClient: async () => ({
    auth: { exchangeCodeForSession: state.exchangeCodeForSession },
  }),
}));

import { GET } from "@/app/auth/callback/route";
import { CSRF_COOKIE_NAME } from "@/lib/security";

describe("Supabase auth callback", () => {
  beforeEach(() => state.exchangeCodeForSession.mockClear());

  it("rejects portable raw token-hash links without attempting an exchange", async () => {
    const response = await GET(
      new NextRequest(
        "https://aletheia.example/auth/callback?token_hash=portable&type=email&next=%2Fdemo",
      ),
    );

    expect(state.exchangeCodeForSession).not.toHaveBeenCalled();
    expect(response.headers.get("location")).toBe(
      "https://aletheia.example/login?error=callback_failed&next=%2Fdemo",
    );
  });

  it("exchanges a browser-bound PKCE code and creates the CSRF cookie", async () => {
    const response = await GET(
      new NextRequest(
        "https://aletheia.example/auth/callback?code=pkce-code&next=%2Fdemo",
      ),
    );

    expect(state.exchangeCodeForSession).toHaveBeenCalledWith("pkce-code");
    expect(response.headers.get("location")).toBe("https://aletheia.example/demo");
    expect(response.cookies.get(CSRF_COOKIE_NAME)?.value).toBeTruthy();
    expect(response.headers.get("cache-control")).toBe("private, no-store");
  });
});
