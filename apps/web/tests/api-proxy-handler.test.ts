import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const auth = vi.hoisted(() => ({
  getVerifiedAccessToken: vi.fn(async () => ({
    identity: { id: "user-1", email: "owner@example.com" },
    accessToken: "verified-user-jwt",
  })),
}));

vi.mock("@/lib/supabase/auth", () => ({
  getVerifiedAccessToken: auth.getVerifiedAccessToken,
}));

vi.mock("@/lib/supabase/config", () => ({
  getSupabasePublicConfig: () => ({
    url: "https://project.supabase.co",
    publishableKey: "publishable",
    turnstileSiteKey: "site-key",
    siteUrl: "https://aletheia.example",
  }),
  isLocalAuthBypassEnabled: () => false,
}));

import { GET, POST } from "@/app/api/v1/[...path]/route";
import { CSRF_COOKIE_NAME, CSRF_HEADER_NAME } from "@/lib/security";

const context = (path: string[]) => ({ params: Promise.resolve({ path }) });

describe("same-origin API proxy handler", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it("strips caller credentials, injects server credentials, and streams safe headers", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("API_ORIGIN_URL", "https://api.internal.example");
    vi.stubEnv("API_ORIGIN_TOKEN", "server-only-origin-token");

    let forwardedUrl = "";
    let forwardedHeaders = new Headers();
    vi.stubGlobal("fetch", vi.fn(async (input: URL | RequestInfo, init?: RequestInit) => {
      forwardedUrl = input.toString();
      forwardedHeaders = new Headers(init?.headers);
      return new Response("download-bytes", {
        status: 200,
        headers: {
          "Content-Disposition": "attachment; filename=evidence.json",
          "Content-Type": "application/json",
          Location: "https://untrusted.example/api/v1/jobs/job-1",
          "Set-Cookie": "upstream=must-not-reach-browser",
        },
      });
    }));

    const request = new NextRequest(
      "https://aletheia.example/api/v1/reports/report-1/export?format=json",
      {
        headers: {
          Authorization: "Bearer caller-controlled-token",
          Cookie: "private-browser-cookie=value",
          "X-Aletheia-Origin-Token": "caller-controlled-origin",
          "X-Forwarded-Host": "attacker.example",
        },
      },
    );
    const response = await GET(
      request,
      context(["reports", "report-1", "export"]),
    );

    expect(forwardedUrl).toBe(
      "https://api.internal.example/api/v1/reports/report-1/export?format=json",
    );
    expect(forwardedHeaders.get("authorization")).toBe("Bearer verified-user-jwt");
    expect(forwardedHeaders.get("x-aletheia-origin-token")).toBe(
      "server-only-origin-token",
    );
    expect(forwardedHeaders.has("cookie")).toBe(false);
    expect(forwardedHeaders.get("x-forwarded-host")).toBe("aletheia.example");
    expect(await response.text()).toBe("download-bytes");
    expect(response.headers.get("content-disposition")).toBe(
      "attachment; filename=evidence.json",
    );
    expect(response.headers.has("set-cookie")).toBe(false);
    expect(response.headers.get("location")).toBe("/api/v1/jobs/job-1");
    expect(response.headers.get("cache-control")).toBe("private, no-store");
  });

  it("rejects a production mutation until Origin and CSRF both match", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("API_ORIGIN_URL", "https://api.internal.example");
    vi.stubEnv("API_ORIGIN_TOKEN", "server-only-origin-token");
    const upstream = vi.fn(async () => new Response("{}", { status: 202 }));
    vi.stubGlobal("fetch", upstream);

    const untrusted = await POST(
      new NextRequest("https://aletheia.example/api/v1/workspaces/bootstrap", {
        method: "POST",
        body: "{}",
        headers: { "Content-Type": "application/json" },
      }),
      context(["workspaces", "bootstrap"]),
    );
    expect(untrusted.status).toBe(403);
    expect(upstream).not.toHaveBeenCalled();

    const trusted = await POST(
      new NextRequest("https://aletheia.example/api/v1/workspaces/bootstrap", {
        method: "POST",
        body: "{}",
        headers: {
          "Content-Type": "application/json",
          Cookie: `${CSRF_COOKIE_NAME}=csrf-token`,
          Origin: "https://aletheia.example",
          "Sec-Fetch-Site": "same-origin",
          [CSRF_HEADER_NAME]: "csrf-token",
        },
      }),
      context(["workspaces", "bootstrap"]),
    );
    expect(trusted.status).toBe(202);
    expect(upstream).toHaveBeenCalledTimes(1);
  });
});
