"use client";

import { createBrowserClient } from "@supabase/ssr";
import type { SupabasePublicConfig } from "./config";

export function createSupabaseBrowserClient(config: SupabasePublicConfig) {
  return createBrowserClient(config.url, config.publishableKey);
}
