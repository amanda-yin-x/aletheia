import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { LoginForm } from "./login-form";
import { getAuthIdentity } from "@/lib/supabase/auth";
import { getSupabasePublicConfig, isLocalAuthBypassEnabled } from "@/lib/supabase/config";
import { safeNextPath } from "@/lib/security";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Sign in — Aletheia", robots: { index: false, follow: false } };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string; error?: string }> }) {
  const query = await searchParams;
  const nextPath = safeNextPath(query.next);
  const identity = await getAuthIdentity();
  // Anonymous visitors may still choose a persistent email or GitHub identity.
  if (identity && !identity.isAnonymous) redirect(nextPath);

  const config = getSupabasePublicConfig();
  if (!config) {
    if (isLocalAuthBypassEnabled()) redirect(nextPath);
    return <main className="auth-page"><section className="auth-card"><h1>Authentication is unavailable.</h1><p className="auth-lede">The deployment is missing its Supabase runtime configuration. Ask the site operator to configure it before signing in.</p></section></main>;
  }
  const initialError = query.error === "callback_failed" ? "That sign-in link could not be verified. Request a new link and try again." : null;
  return <LoginForm config={config} nextPath={nextPath} initialError={initialError} hasAnonymousSession={identity?.isAnonymous === true} />;
}
