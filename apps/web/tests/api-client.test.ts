import { afterEach, describe, expect, it, vi } from "vitest";

import {
  API_CLIENT_MUTATION_TIMEOUT_MS,
  API_CLIENT_READ_TIMEOUT_MS,
  API_PROXY_RESPONSE_HEADER_TIMEOUT_MS,
  api,
} from "@/lib/api";
import { CSRF_COOKIE_NAME } from "@/lib/security";

describe("browser API client deadlines", () => {
  afterEach(() => {
    document.cookie = `${CSRF_COOKIE_NAME}=; Max-Age=0; Path=/`;
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("keeps an ordinary GET alive through the proxy response-header window", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn((_input: URL | RequestInfo, init?: RequestInit) => (
      new Promise<Response>((resolve, reject) => {
        const timer = globalThis.setTimeout(() => {
          resolve(new Response('{"status":"ready"}', {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }));
        }, API_PROXY_RESPONSE_HEADER_TIMEOUT_MS);
        init?.signal?.addEventListener("abort", () => {
          globalThis.clearTimeout(timer);
          reject(init.signal?.reason);
        }, { once: true });
      })
    ));
    vi.stubGlobal("fetch", fetchMock);

    const pending = api<{ status: string }>("/api/v1/me", { coldStartRetries: 0 });
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await vi.advanceTimersByTimeAsync(API_PROXY_RESPONSE_HEADER_TIMEOUT_MS - 1);
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit | undefined)?.signal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);

    await expect(pending).resolves.toEqual({ status: "ready" });
  });

  it("aborts an ordinary GET at the client read deadline", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn((_input: URL | RequestInfo, init?: RequestInit) => (
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(init.signal?.reason), { once: true });
      })
    ));
    vi.stubGlobal("fetch", fetchMock);

    const pending = api("/api/v1/me", { coldStartRetries: 0 });
    const rejection = expect(pending).rejects.toMatchObject({ name: "TimeoutError" });
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await vi.advanceTimersByTimeAsync(API_CLIENT_READ_TIMEOUT_MS);

    await rejection;
  });

  it("keeps non-retried mutations on the short default deadline", async () => {
    vi.useFakeTimers();
    document.cookie = `${CSRF_COOKIE_NAME}=csrf-token; Path=/`;
    const fetchMock = vi.fn((_input: URL | RequestInfo, init?: RequestInit) => (
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(init.signal?.reason), { once: true });
      })
    ));
    vi.stubGlobal("fetch", fetchMock);

    const pending = api("/api/v1/waitlist", {
      method: "POST",
      body: JSON.stringify({ email: "owner@example.com" }),
    });
    const rejection = expect(pending).rejects.toMatchObject({ name: "TimeoutError" });
    await vi.advanceTimersByTimeAsync(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(API_CLIENT_MUTATION_TIMEOUT_MS - 1);
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit | undefined)?.signal?.aborted).toBe(false);
    await vi.advanceTimersByTimeAsync(1);

    await rejection;
  });

  it("honors a shorter explicit timeout override", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn((_input: URL | RequestInfo, init?: RequestInit) => (
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(init.signal?.reason), { once: true });
      })
    ));
    vi.stubGlobal("fetch", fetchMock);

    const pending = api("/api/v1/me", {
      coldStartRetries: 0,
      coldStartTimeoutMs: 50,
    });
    const rejection = expect(pending).rejects.toMatchObject({ name: "TimeoutError" });
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await vi.advanceTimersByTimeAsync(50);

    await rejection;
  });
});
