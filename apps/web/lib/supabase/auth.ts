import "server-only";

import { redirect } from "next/navigation";
import { createSupabaseServerClient } from "./server";
import { getSupabasePublicConfig, isLocalAuthBypassEnabled } from "./config";

export interface AuthIdentity {
  id: string;
  email: string | null;
  name: string | null;
  avatarUrl: string | null;
  localBypass?: boolean;
}

function stringClaim(claims: Record<string, unknown>, key: string): string | null {
  const value = claims[key];
  return typeof value === "string" && value.length > 0 ? value : null;
}

function identityFromClaims(claims: Record<string, unknown>): AuthIdentity | null {
  const id = stringClaim(claims, "sub");
  if (!id) return null;
  const metadata = typeof claims.user_metadata === "object" && claims.user_metadata
    ? claims.user_metadata as Record<string, unknown>
    : {};
  const name = stringClaim(metadata, "full_name") || stringClaim(metadata, "name") || stringClaim(claims, "name");
  const avatarUrl = stringClaim(metadata, "avatar_url") || stringClaim(metadata, "picture") || stringClaim(claims, "picture");
  return { id, email: stringClaim(claims, "email"), name, avatarUrl };
}

export async function getAuthIdentity(): Promise<AuthIdentity | null> {
  if (isLocalAuthBypassEnabled()) {
    return { id: "local-development", email: "local@aletheia.dev", name: "Local workspace", avatarUrl: null, localBypass: true };
  }
  if (!getSupabasePublicConfig()) return null;

  const supabase = await createSupabaseServerClient();
  const { data, error } = await supabase.auth.getClaims();
  if (error || !data?.claims) return null;
  return identityFromClaims(data.claims as Record<string, unknown>);
}

export async function requireAuth(nextPath = "/demo"): Promise<AuthIdentity> {
  const identity = await getAuthIdentity();
  if (!identity) redirect(`/login?next=${encodeURIComponent(nextPath)}`);
  return identity;
}

export async function getVerifiedAccessToken(): Promise<{ identity: AuthIdentity; accessToken: string | null } | null> {
  const identity = await getAuthIdentity();
  if (!identity) return null;
  if (identity.localBypass) return { identity, accessToken: null };

  // getSession is only used after getClaims has cryptographically verified the JWT.
  const supabase = await createSupabaseServerClient();
  const { data, error } = await supabase.auth.getSession();
  if (error || !data.session?.access_token) return null;
  return { identity, accessToken: data.session.access_token };
}
