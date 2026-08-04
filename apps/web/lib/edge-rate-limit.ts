import { getCloudflareContext } from "@opennextjs/cloudflare";

type RateLimitCategory = "general" | "poll" | "heavy";

interface RateLimiter {
  limit(options: { key: string }): Promise<{ success: boolean }>;
}

interface RateLimitEnv {
  API_RATE_LIMITER?: RateLimiter;
  API_POLL_RATE_LIMITER?: RateLimiter;
  API_HEAVY_RATE_LIMITER?: RateLimiter;
}

export interface EdgeRateLimitResult {
  allowed: boolean;
  retryAfterSeconds: number;
}

function categoryForPath(path: readonly string[]): RateLimitCategory {
  if (path[0] === "jobs") return "poll";
  if (
    path[0] === "reports"
    || path[0] === "scenario-results"
    || path.includes("results")
    || path.includes("export")
  ) return "heavy";
  return "general";
}

export async function enforceEdgeApiRateLimit(
  subject: string,
  path: readonly string[],
): Promise<EdgeRateLimitResult> {
  if (process.env.NODE_ENV !== "production") {
    return { allowed: true, retryAfterSeconds: 60 };
  }

  const { env } = await getCloudflareContext({ async: true });
  const bindings = env as unknown as RateLimitEnv;
  const general = bindings.API_RATE_LIMITER;
  const category = categoryForPath(path);
  const specialized = category === "poll"
    ? bindings.API_POLL_RATE_LIMITER
    : category === "heavy"
      ? bindings.API_HEAVY_RATE_LIMITER
      : null;
  if (!general || (category !== "general" && !specialized)) {
    throw new Error("Required API rate-limit bindings are unavailable.");
  }

  const generalResult = await general.limit({ key: `user:${subject}` });
  if (!generalResult.success) return { allowed: false, retryAfterSeconds: 60 };
  if (specialized) {
    const specializedResult = await specialized.limit({ key: `${category}:user:${subject}` });
    if (!specializedResult.success) return { allowed: false, retryAfterSeconds: 60 };
  }
  return { allowed: true, retryAfterSeconds: 60 };
}
