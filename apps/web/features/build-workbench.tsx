"use client";

import { AlertTriangle, ArrowDown, CheckCircle2, FileDiff, Hammer, Route, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, RequestError, shortHash } from "@/lib/api";
import type { Build, Document, Summary } from "@/lib/types";
import { Badge, Button, EmptyState, ErrorState, PageLoading, PageTitle, StatCard } from "@/components/ui";

const tabs = [
  ["Prompt kernel", "prompt-kernel.md"],
  ["Refund workflow", "workflows/refunds.md"],
  ["Tool policy", "policies/tool-policy.json"],
  ["Regression tests", "tests/regression.yaml"],
] as const;

export function BuildWorkbench({ projectId, requestedBuildId }: { projectId: string; requestedBuildId?: string }) {
  const router = useRouter();
  const client = useQueryClient();
  const builds = useQuery({ queryKey: ["builds", projectId], queryFn: () => api<Build[]>(`/api/v1/projects/${projectId}/builds`) });
  const summary = useQuery({ queryKey: ["summary", projectId], queryFn: () => api<Summary>(`/api/v1/projects/${projectId}/summary`) });
  const documents = useQuery({ queryKey: ["documents", projectId], queryFn: () => api<Document[]>(`/api/v1/projects/${projectId}/documents`) });
  const [tab, setTab] = useState<(typeof tabs)[number][1]>("prompt-kernel.md");
  const create = useMutation({ mutationFn: () => api<Build>(`/api/v1/projects/${projectId}/builds`, { method: "POST", body: "{}" }), onSuccess: async (build) => { await Promise.all([client.invalidateQueries({ queryKey: ["builds", projectId] }), client.invalidateQueries({ queryKey: ["summary", projectId] })]); router.replace(`/projects/${projectId}/builds/${build.id}`); } });
  const build = useMemo(() => builds.data?.find((item) => item.id === requestedBuildId) || builds.data?.[0], [builds.data, requestedBuildId]);
  if (builds.isLoading || summary.isLoading || documents.isLoading) return <PageLoading label="Loading compiler artifacts" />;
  if (builds.error || summary.error || documents.error) return <ErrorState error={builds.error || summary.error || documents.error} onRetry={() => { builds.refetch(); summary.refetch(); documents.refetch(); }} />;
  const blockers = summary.data!.critical_findings;
  const baseline = documents.data!.find((document) => document.kind === "baseline_prompt")?.normalized_text || "";
  const artifact = build?.artifacts[tab];
  const display = typeof artifact === "string" ? artifact : JSON.stringify(artifact, null, 2);
  return <div className="content-wrap">
    <PageTitle eyebrow="Deterministic compiler" title="Candidate build" detail="Approved revisions route into a smaller prompt, scoped workflow, tool policy, tests, and source map." actions={<Button disabled={Boolean(blockers) || create.isPending} onClick={() => create.mutate()}><Hammer size={15} /> {create.isPending ? "Building…" : build ? "Build new snapshot" : "Build candidate"}</Button>} />
    {blockers > 0 && <div className="build-blocked"><div><strong><AlertTriangle size={16} /> Candidate build blocked</strong><p>{blockers} critical conflicts still need a human resolution. Compilation never uses document order as policy priority.</p></div><a className="button button-secondary" href={`/projects/${projectId}/rules`}>Resolve in Rules</a></div>}
    {create.error && <div className="build-blocked"><div><strong>Build could not start</strong><p>{create.error instanceof RequestError ? create.error.message : "Review the current policy findings and try again."}</p></div></div>}
    {!build ? <EmptyState title={blockers ? "Review is not complete" : "No candidate build yet"} detail={blockers ? "Resolve the exact 30/60-day and $200/$250 conflicts first." : "Create an immutable artifact bundle from the approved rule revisions."} /> : <>
      <div className="stat-grid">
        <StatCard label="Prompt lines" value={<>{build.stats.original.lines} <ArrowDown size={15} /> {build.stats.candidate.lines}</>} note={`${build.stats.reduction.lines} fewer source lines`} />
        <StatCard label="Token estimate" value={<>{build.stats.original.tokens} <ArrowDown size={15} /> {build.stats.candidate.tokens}</>} note={build.stats.reduction.label} />
        <StatCard label="Guarded rules" value={build.stats.routing.guarded} note="Approved + machine-decidable" tone="teal" />
        <StatCard label="Regression cases" value={build.stats.routing.tested} note="Referenced in manifest" />
      </div>
      <section className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-header"><div><h2>Build snapshot <Badge tone="teal"><CheckCircle2 size={11} /> Immutable</Badge></h2><p className="hash-line">Manifest {shortHash(build.content_hash)} · input {shortHash(build.input_hash)} · compiler {build.compiler_version}</p></div><Badge tone="blue">{new Date(build.created_at).toLocaleString()}</Badge></div>
        <div className="tabs" role="tablist">{tabs.map(([title, path]) => <button role="tab" aria-selected={tab === path} className={`tab ${tab === path ? "active" : ""}`} key={path} onClick={() => setTab(path)}>{path.includes("policy") && <ShieldCheck size={13} />} {title}</button>)}</div>
        <pre className="artifact-code" aria-label={`${tab} artifact`}>{display}</pre>
      </section>
      <section className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-header"><div><h2><FileDiff size={15} /> Original / prompt kernel</h2><p>Measured source text against the compiled always-on candidate.</p></div><Badge>{build.stats.reduction.estimated_tokens} estimated tokens routed out</Badge></div>
        <div className="diff-grid">
          <div className="diff-pane removed"><div className="diff-label">Original · {build.stats.original.lines} lines</div><pre>{baseline}</pre></div>
          <div className="diff-pane added"><div className="diff-label">Candidate · {build.stats.candidate.lines} lines</div><pre>{String(build.artifacts["prompt-kernel.md"])}</pre></div>
        </div>
      </section>
      <section className="panel"><div className="panel-header"><div><h2><Route size={15} /> Routing summary</h2><p>Rule categories determine placement; token reduction is an observed result, not a target.</p></div></div><div className="panel-body stat-grid" style={{ marginBottom: 0 }}>
        <StatCard label="Prompt summaries" value={build.stats.routing.kept_in_prompt} note="Hard constraints + style" />
        <StatCard label="Scoped workflow" value={build.stats.routing.moved_to_workflow} note="Loaded for refund tasks" />
        <StatCard label="Tool guard" value={build.stats.routing.guarded} note="Pre-tool JSON policy" />
        <StatCard label="Tests" value={build.stats.routing.tested} note="Manifest-linked cases" />
      </div></section>
    </>}
  </div>;
}
