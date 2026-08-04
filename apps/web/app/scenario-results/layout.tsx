import { requireAuth } from "@/lib/supabase/auth";

export const dynamic = "force-dynamic";

export default async function ResultsLayout({ children }: { children: React.ReactNode }) {
  await requireAuth("/demo");
  return children;
}
