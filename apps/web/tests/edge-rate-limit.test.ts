import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  general: vi.fn(),
  poll: vi.fn(),
  heavy: vi.fn(),
  getCloudflareContext: vi.fn(),
}));

vi.mock("@opennextjs/cloudflare", () => ({
  getCloudflareContext: mocks.getCloudflareContext,
}));

import { enforceEdgeApiRateLimit } from "@/lib/edge-rate-limit";

beforeEach(() => {
  vi.stubEnv("NODE_ENV", "production");
  mocks.general.mockResolvedValue({ success: true });
  mocks.poll.mockResolvedValue({ success: true });
  mocks.heavy.mockResolvedValue({ success: true });
  mocks.getCloudflareContext.mockResolvedValue({
    env: {
      API_RATE_LIMITER: { limit: mocks.general },
      API_POLL_RATE_LIMITER: { limit: mocks.poll },
      API_HEAVY_RATE_LIMITER: { limit: mocks.heavy },
    },
  });
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.clearAllMocks();
});

describe("Cloudflare API rate limits", () => {
  it("uses both the user and polling buckets for job reads", async () => {
    await expect(enforceEdgeApiRateLimit("user-1", ["jobs", "job-1"]))
      .resolves.toEqual({ allowed: true, retryAfterSeconds: 60 });
    expect(mocks.general).toHaveBeenCalledWith({ key: "user:user-1" });
    expect(mocks.poll).toHaveBeenCalledWith({ key: "poll:user:user-1" });
    expect(mocks.heavy).not.toHaveBeenCalled();
  });

  it("uses the stricter heavy bucket for traces and downloads", async () => {
    mocks.heavy.mockResolvedValue({ success: false });
    await expect(enforceEdgeApiRateLimit("user-2", ["reports", "report-1", "export"]))
      .resolves.toEqual({ allowed: false, retryAfterSeconds: 60 });
    expect(mocks.heavy).toHaveBeenCalledWith({ key: "heavy:user:user-2" });
  });

  it("fails closed when a production binding is missing", async () => {
    mocks.getCloudflareContext.mockResolvedValue({ env: {} });
    await expect(enforceEdgeApiRateLimit("user-3", ["me"]))
      .rejects.toThrow("Required API rate-limit bindings");
  });
});
