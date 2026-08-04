import "server-only";

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { getSupabasePublicConfig } from "./config";

export class SupabaseConfigurationError extends Error {
  constructor() {
    super("Supabase authentication is not configured.");
    this.name = "SupabaseConfigurationError";
  }
}

export async function createSupabaseServerClient() {
  const config = getSupabasePublicConfig();
  if (!config) throw new SupabaseConfigurationError();
  const cookieStore = await cookies();

  return createServerClient(config.url, config.publishableKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          for (const { name, value, options } of cookiesToSet) {
            cookieStore.set(name, value, options);
          }
        } catch {
          // Server Components cannot write cookies. Route handlers refresh and
          // persist the same session before any protected API request is proxied.
        }
      },
    },
  });
}
