import { MarketingLanding } from "@/components/marketing-landing";
import { getAuthIdentity } from "@/lib/supabase/auth";
import { getSupabasePublicConfig } from "@/lib/supabase/config";

export const dynamic = "force-dynamic";

export default async function LandingPage() {
  const identity = await getAuthIdentity();
  return <MarketingLanding config={getSupabasePublicConfig()} initialHasSession={identity !== null} />;
}
