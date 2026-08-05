"use client";

import Link from "next/link";
import { AlertTriangle, Hammer } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BuildInspectionView } from "@/features/build-inspection";
import { api, RequestError } from "@/lib/api";
import { startOperationAndLoadResource } from "@/lib/operations";
import type { Build, BuildInspection, Document, Operation, Summary } from "@/lib/types";
import { Button, EmptyState, ErrorState, PageLoading, PageTitle } from "@/components/ui";

export function BuildWorkbench({ projectId, requestedBuildId }: { projectId: string; requestedBuildId?: string }) {
  const router = useRouter();
  const client = useQueryClient();
  const builds = useQuery({ queryKey: ["builds", projectId], queryFn: () => api<Build[]>(`/api/v1/projects/${projectId}/builds`) });
  const summary = useQuery({ queryKey: ["summary", projectId], queryFn: () => api<Summary>(`/api/v1/projects/${projectId}/summary`) });
  const documents = useQuery({ queryKey: ["documents", projectId], queryFn: () => api<Document[]>(`/api/v1/projects/${projectId}/documents`) });
  const build = useMemo(() => {
    if (!builds.data) return undefined;
    if (requestedBuildId) return builds.data.find((item) => item.id === requestedBuildId);
    return builds.data[0];
  }, [builds.data, requestedBuildId]);
  const inspection = useQuery({
    queryKey: ["build-inspection", build?.id || "none"],
    queryFn: () => {
      if (!build) throw new Error("A build is required for inspection.");
      return api<BuildInspection>(`/api/v1/builds/${encodeURIComponent(build.id)}/inspection`);
    },
    enabled: Boolean(build),
  });
  const [operation, setOperation] = useState<Operation | null>(null);
  const [waking, setWaking] = useState(false);
  const create = useMutation({
    mutationFn: () => startOperationAndLoadResource<Build>({
      path: `/api/v1/projects/${projectId}/builds`,
      init: { method: "POST", body: "{}", retryMutation: true, coldStartRetries: 20, coldStartTimeoutMs: 85_000, onRetry: () => setWaking(true) },
      operationKind: "compile",
      resourceType: "build",
      resourcePath: (id) => `/api/v1/builds/${encodeURIComponent(id)}`,
      validateResource: (value) => value.project_id === projectId,
      onProgress: (value) => { setWaking(false); setOperation(value); },
    }),
    onMutate: () => { setOperation(null); setWaking(false); },
    onSuccess: async (createdBuild) => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ["builds", projectId] }),
        client.invalidateQueries({ queryKey: ["summary", projectId] }),
      ]);
      router.replace(`/projects/${projectId}/builds/${createdBuild.id}`);
    },
  });

  if (builds.isLoading || summary.isLoading || documents.isLoading) return <PageLoading label="Loading compiler artifacts" />;
  if (builds.error || summary.error || documents.error) return <ErrorState error={builds.error || summary.error || documents.error} onRetry={() => { void builds.refetch(); void summary.refetch(); void documents.refetch(); }} />;

  const requestedBuildMissing = Boolean(requestedBuildId && !build);
  const blockers = summary.data?.critical_findings || 0;
  const action = <Button disabled={Boolean(blockers) || create.isPending} onClick={() => create.mutate()}><Hammer size={15} /> {create.isPending ? (waking ? "Waking your workspace…" : `Building… ${operation?.progress ?? 0}%`) : build ? "Build new snapshot" : "Build candidate"}</Button>;

  if (requestedBuildMissing) return <div className="content-wrap">
    <PageTitle eyebrow="Deterministic compiler" title="Build snapshot not found" detail="The requested build is not available in this project-scoped workspace." />
    <EmptyState title="No matching build" detail="Open the current build list instead of substituting a different snapshot." action={<Link className="button button-secondary" href={`/projects/${encodeURIComponent(projectId)}/build`}>Open current build</Link>} />
  </div>;

  if (build && inspection.isLoading) return <PageLoading label="Loading build inspection" detail="Reading exact artifact hashes, generated spans, and stored compilation reports…" />;
  if (build && inspection.error) return <div className="content-wrap"><PageTitle eyebrow="Deterministic compiler" title="Candidate build" detail="Inspect a stored compiler snapshot and its evidence boundary." actions={action} /><ErrorState error={inspection.error} onRetry={() => void inspection.refetch()} /></div>;
  if (build && inspection.data && (inspection.data.project_id !== projectId || inspection.data.build_id !== build.id)) return <div className="content-wrap"><ErrorState error={new Error("The inspection response does not match the requested project and build.")} onRetry={() => void inspection.refetch()} /></div>;

  return <div className="content-wrap">
    <PageTitle eyebrow="Deterministic compiler" title="Candidate build" detail="Reviewed rules and placements compile into a versioned artifact bundle with inspectable conformance evidence." actions={action} />
    {blockers > 0 && <div className="build-blocked"><div><strong><AlertTriangle size={16} /> Candidate build blocked</strong><p>{blockers} critical conflicts still need a human resolution. Compilation never uses document order as policy priority.</p></div><Link className="button button-secondary" href={`/projects/${projectId}/rules`}>Resolve in Rules</Link></div>}
    {create.error && <div className="build-blocked"><div><strong>Build could not complete</strong><p>{create.error instanceof RequestError || create.error instanceof Error ? create.error.message : "Review the current rule and placement decisions, then try again."}</p></div><Link className="button button-secondary" href={`/projects/${encodeURIComponent(projectId)}/routing`}>Review placements</Link></div>}
    {!build ? <EmptyState title={blockers ? "Review is not complete" : "No candidate build yet"} detail={blockers ? "Resolve each critical authority or boundary conflict before compiling." : "Create a stored artifact snapshot from the reviewed rule revisions and explicit placements."} /> : inspection.data && <BuildInspectionView key={build.id} projectId={projectId} build={build} inspection={inspection.data} documents={documents.data || []} />}
  </div>;
}
