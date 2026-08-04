import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const auth = vi.hoisted(() => ({
  getVerifiedAccessToken: vi.fn(async () => ({
    identity: { id: "user-1", email: "owner@example.com" },
    accessToken: "verified-user-jwt",
  })),
}));
const edge = vi.hoisted(() => ({
  enforceEdgeApiRateLimit: vi.fn(async () => ({ allowed: true, retryAfterSeconds: 60 })),
}));

vi.mock("@/lib/supabase/auth", () => ({
  getVerifiedAccessToken: auth.getVerifiedAccessToken,
}));
vi.mock("@/lib/edge-rate-limit", () => edge);

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
    vi.useRealTimers();
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

  it("keeps a read request open while the hosted API wakes", async () => {
    vi.useFakeTimers();
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("API_ORIGIN_URL", "https://api.internal.example");
    vi.stubEnv("API_ORIGIN_TOKEN", "server-only-origin-token");
    const upstream = vi
      .fn<() => Promise<Response>>()
      .mockResolvedValueOnce(new Response("waking", { status: 503 }))
      .mockResolvedValueOnce(new Response('{"id":"project-1"}', { status: 200 }));
    vi.stubGlobal("fetch", upstream);

    const pending = GET(
      new NextRequest("https://aletheia.example/api/v1/projects/project-1"),
      context(["projects", "project-1"]),
    );
    await vi.waitFor(() => expect(upstream).toHaveBeenCalledTimes(1));
    await vi.advanceTimersByTimeAsync(1_000);

    const response = await pending;
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ id: "project-1" });
    expect(upstream).toHaveBeenCalledTimes(2);
    expect(edge.enforceEdgeApiRateLimit).toHaveBeenCalledTimes(2);
  });

  it("aborts a hung upstream request at the bounded recovery deadline", async () => {
    vi.useFakeTimers();
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("API_ORIGIN_URL", "https://api.internal.example");
    vi.stubEnv("API_ORIGIN_TOKEN", "server-only-origin-token");
    const upstream = vi.fn((_input: URL | RequestInfo, init?: RequestInit) => (
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(init.signal?.reason), { once: true });
      })
    ));
    vi.stubGlobal("fetch", upstream);

    const pending = GET(
      new NextRequest("https://aletheia.example/api/v1/projects/project-1"),
      context(["projects", "project-1"]),
    );
    await vi.waitFor(() => expect(upstream).toHaveBeenCalledTimes(1));
    await vi.advanceTimersByTimeAsync(85_000);

    const response = await pending;
    expect(response.status).toBe(504);
    expect((await response.json()).code).toBe("api_timeout");
  });

  it("returns the last wake response intact when no retry fits the deadline", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(0));
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("API_ORIGIN_URL", "https://api.internal.example");
    vi.stubEnv("API_ORIGIN_TOKEN", "server-only-origin-token");
    const upstream = vi.fn(async () => {
      vi.setSystemTime(new Date(84_500));
      return new Response("still waking", { status: 503 });
    });
    vi.stubGlobal("fetch", upstream);

    const response = await GET(
      new NextRequest("https://aletheia.example/api/v1/projects/project-1"),
      context(["projects", "project-1"]),
    );

    expect(response.status).toBe(503);
    expect(await response.text()).toBe("still waking");
    expect(upstream).toHaveBeenCalledTimes(1);
  });

  it("cancels the origin fetch when the incoming browser request closes", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("API_ORIGIN_URL", "https://api.internal.example");
    vi.stubEnv("API_ORIGIN_TOKEN", "server-only-origin-token");
    const upstream = vi.fn((_input: URL | RequestInfo, init?: RequestInit) => (
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(init.signal?.reason), { once: true });
      })
    ));
    vi.stubGlobal("fetch", upstream);
    const controller = new AbortController();
    const request = new NextRequest("https://aletheia.example/api/v1/projects/project-1");
    // NextRequest uses Node's Fetch implementation while Vitest's jsdom
    // environment supplies a different AbortSignal realm. Override the
    // read-only signal after construction so this test exercises proxy
    // cancellation without failing NextRequest's cross-realm brand check.
    Object.defineProperty(request, "signal", { value: controller.signal });
    const pending = GET(
      request,
      context(["projects", "project-1"]),
    );
    await vi.waitFor(() => expect(upstream).toHaveBeenCalledTimes(1));
    controller.abort();

    const response = await pending;
    expect(response.status).toBe(499);
    expect((await response.json()).code).toBe("request_cancelled");
    expect((upstream.mock.calls[0]?.[1] as RequestInit).signal?.aborted).toBe(true);
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

  it("rejects an oversized mutation before forwarding it", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("API_ORIGIN_URL", "https://api.internal.example");
    vi.stubEnv("API_ORIGIN_TOKEN", "server-only-origin-token");
    const upstream = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", upstream);

    const response = await POST(
      new NextRequest("https://aletheia.example/api/v1/waitlist", {
        method: "POST",
        body: "x".repeat(64 * 1024 + 1),
        headers: {
          "Content-Type": "application/json",
          Cookie: `${CSRF_COOKIE_NAME}=csrf-token`,
          Origin: "https://aletheia.example",
          "Sec-Fetch-Site": "same-origin",
          [CSRF_HEADER_NAME]: "csrf-token",
        },
      }),
      context(["waitlist"]),
    );

    expect(response.status).toBe(413);
    expect((await response.json()).code).toBe("request_body_too_large");
    expect(upstream).not.toHaveBeenCalled();
  });

  it("never forwards a caller-controlled Content-Length", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("API_ORIGIN_URL", "https://api.internal.example");
    vi.stubEnv("API_ORIGIN_TOKEN", "server-only-origin-token");
    let forwardedHeaders = new Headers();
    const upstream = vi.fn(async (_input: URL | RequestInfo, init?: RequestInit) => {
      forwardedHeaders = new Headers(init?.headers);
      return new Response("{}", { status: 200 });
    });
    vi.stubGlobal("fetch", upstream);

    const response = await POST(
      new NextRequest("https://aletheia.example/api/v1/waitlist", {
        method: "POST",
        body: JSON.stringify({ email: "member@example.com" }),
        headers: {
          "Content-Length": "1",
          "Content-Type": "application/json",
          Cookie: `${CSRF_COOKIE_NAME}=csrf-token`,
          Origin: "https://aletheia.example",
          "Sec-Fetch-Site": "same-origin",
          [CSRF_HEADER_NAME]: "csrf-token",
        },
      }),
      context(["waitlist"]),
    );

    expect(response.status).toBe(200);
    expect(forwardedHeaders.has("content-length")).toBe(false);
  });

  it("returns a retryable 429 without touching the upstream API", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("API_ORIGIN_URL", "https://api.internal.example");
    vi.stubEnv("API_ORIGIN_TOKEN", "server-only-origin-token");
    edge.enforceEdgeApiRateLimit.mockResolvedValueOnce({ allowed: false, retryAfterSeconds: 60 });
    const upstream = vi.fn(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", upstream);

    const response = await GET(
      new NextRequest("https://aletheia.example/api/v1/jobs/job-1"),
      context(["jobs", "job-1"]),
    );

    expect(response.status).toBe(429);
    expect(response.headers.get("retry-after")).toBe("60");
    expect((await response.json()).code).toBe("rate_limit_reached");
    expect(upstream).not.toHaveBeenCalled();
  });
});
