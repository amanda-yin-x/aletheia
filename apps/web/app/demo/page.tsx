import { DemoEntry } from "@/components/demo-entry";
import { requireAuth } from "@/lib/supabase/auth";

export const dynamic = "force-dynamic";

export default async function DemoPage() {
  await requireAuth("/demo");
  return <DemoEntry />;
}
