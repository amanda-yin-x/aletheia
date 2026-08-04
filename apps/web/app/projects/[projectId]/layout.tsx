import { ProjectShell } from "@/components/project-shell";
import { requireAuth } from "@/lib/supabase/auth";

export const dynamic = "force-dynamic";

export default async function Layout({ children, params }: { children: React.ReactNode; params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  await requireAuth(`/projects/${projectId}/overview`);
  return <ProjectShell projectId={projectId}>{children}</ProjectShell>;
}
