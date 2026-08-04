import { DemoEntry } from "@/components/demo-entry";
import { getAuthIdentity } from "@/lib/supabase/auth";
import { getSupabasePublicConfig } from "@/lib/supabase/config";

export const dynamic = "force-dynamic";

export default async function DemoPage() {
  const identity = await getAuthIdentity();
  return <DemoEntry config={getSupabasePublicConfig()} initialHasSession={identity !== null} />;
}
