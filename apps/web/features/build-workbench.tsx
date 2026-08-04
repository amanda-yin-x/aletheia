"use client";

import { AlertTriangle, ArrowDown, CheckCircle2, Download, FileDiff, Hammer, Route, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, RequestError, shortHash } from "@/lib/api";
import { startOperationAndLoadResource } from "@/lib/operations";
import type { Build, Document, Operation, Summary } from "@/lib/types";
import { Badge, Button, EmptyState, ErrorState, PageLoading, PageTitle, StatCard } from "@/components/ui";

function artifactLabel(path: string): string {
  const leaf = path.split("/").at(-1) || path;
  return leaf.replace(/\.[^.]+$/, "").replaceAll(/[-_]/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function artifactHashes(build: Build | undefined): Record<string, string> {
  if (!build) return {};
  try {
    const manifest = JSON.parse(String(build.artifacts["manifest.json"])) as { artifact_hashes?: Record<string, string> };
    return { ...(manifest.artifact_hashes || {}), "manifest.json": build.content_hash };
  } catch {
    return { "manifest.json": build.content_hash };
  }
}

export function BuildWorkbench({ projectId, requestedBuildId }: { projectId: string; requestedBuildId?: string }) {
  const router = useRouter();
  const client = useQueryClient();
  const builds = useQuery({ queryKey: ["builds", projectId], queryFn: () => api<Build[]>(`/api/v1/projects/${projectId}/builds`) });
  const summary = useQuery({ queryKey: ["summary", projectId], queryFn: () => api<Summary>(`/api/v1/projects/${projectId}/summary`) });
  const documents = useQuery({ queryKey: ["documents", projectId], queryFn: () => api<Document[]>(`/api/v1/projects/${projectId}/documents`) });
  const [tab, setTab] = useState("prompt-kernel.md");
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
    onSuccess: async (build) => { await Promise.all([client.invalidateQueries({ queryKey: ["builds", projectId] }), client.invalidateQueries({ queryKey: ["summary", projectId] })]); router.replace(`/projects/${projectId}/builds/${build.id}`); },
  });
  const build = useMemo(() => builds.data?.find((item) => item.id === requestedBuildId) || builds.data?.[0], [builds.data, requestedBuildId]);
  if (builds.isLoading || summary.isLoading || documents.isLoading) return <PageLoading label="Loading compiler artifacts" />;
  if (builds.error || summary.error || documents.error) return <ErrorState error={builds.error || summary.error || documents.error} onRetry={() => { builds.refetch(); summary.refetch(); documents.refetch(); }} />;
  const blockers = summary.data!.critical_findings;
  const baseline = documents.data!.find((document) => document.kind === "baseline_prompt")?.normalized_text || "";
  const artifactPaths = build ? Object.keys(build.artifacts).sort((left, right) => left === "manifest.json" ? -1 : right === "manifest.json" ? 1 : left.localeCompare(right)) : [];
  const selectedArtifact = artifactPaths.includes(tab) ? tab : artifactPaths[0] || tab;
  const hashes = artifactHashes(build);
  const artifact = build?.artifacts[selectedArtifact];
  const display = typeof artifact === "string" ? artifact : JSON.stringify(artifact, null, 2);
  const mappedRules = build?.source_map[selectedArtifact] || [];
  return <div className="content-wrap">
    <PageTitle eyebrow="Deterministic compiler" title="Candidate build" detail="Approved revisions route into a smaller prompt, scoped workflow, tool policy, tests, and source map." actions={<Button disabled={Boolean(blockers) || create.isPending} onClick={() => create.mutate()}><Hammer size={15} /> {create.isPending ? (waking ? "Waking your workspace…" : `Building… ${operation?.progress ?? 0}%`) : build ? "Build new snapshot" : "Build candidate"}</Button>} />
    {blockers > 0 && <div className="build-blocked"><div><strong><AlertTriangle size={16} /> Candidate build blocked</strong><p>{blockers} critical conflicts still need a human resolution. Compilation never uses document order as policy priority.</p></div><a className="button button-secondary" href={`/projects/${projectId}/rules`}>Resolve in Rules</a></div>}
    {create.error && <div className="build-blocked"><div><strong>Build could not complete</strong><p>{create.error instanceof RequestError || create.error instanceof Error ? create.error.message : "Review the current policy findings and try again."}</p></div></div>}
    {!build ? <EmptyState title={blockers ? "Review is not complete" : "No candidate build yet"} detail={blockers ? "Resolve each critical authority or boundary conflict before compiling." : "Create a stored artifact snapshot from the approved rule revisions."} /> : <>
      <div className="stat-grid">
        <StatCard label="Prompt lines" value={<>{build.stats.original.lines} <ArrowDown size={15} /> {build.stats.candidate.lines}</>} note={`${build.stats.reduction.lines} fewer source lines`} />
        <StatCard label="Token estimate" value={<>{build.stats.original.tokens} <ArrowDown size={15} /> {build.stats.candidate.tokens}</>} note={build.stats.reduction.label} />
        <StatCard label="Guarded rules" value={build.stats.routing.guarded} note="Approved + machine-decidable" tone="teal" />
        <StatCard label="Regression cases" value={build.stats.routing.tested} note="Referenced in manifest" />
      </div>
      <section className="panel" style={{ marginBottom: 16 }}>
        <div className="panel-header"><div><h2>Build snapshot <Badge tone="teal"><CheckCircle2 size={11} /> Stored</Badge></h2><p className="hash-line">Manifest {shortHash(build.content_hash)} · input {shortHash(build.input_hash)} · compiler {build.compiler_version}</p></div><Badge tone="blue">{new Date(build.created_at).toLocaleString()}</Badge></div>
        <div className="tabs" role="tablist" aria-label="Compiled artifacts">{artifactPaths.map((path) => <button role="tab" aria-selected={selectedArtifact === path} className={`tab ${selectedArtifact === path ? "active" : ""}`} key={path} onClick={() => setTab(path)}>{path.includes("policy") && <ShieldCheck size={13} />} {artifactLabel(path)}</button>)}</div>
        <div className="panel-body artifact-detail">
          <div><strong>{selectedArtifact}</strong><p className="hash-line">SHA-256 {hashes[selectedArtifact] || "Digest unavailable"}</p></div>
          <a className="button button-secondary" href={`/api/v1/builds/${encodeURIComponent(build.id)}/artifacts/${selectedArtifact.split("/").map(encodeURIComponent).join("/")}`} download><Download size={14} /> Download exact bytes</a>
        </div>
        <pre className="artifact-code" aria-label={`${selectedArtifact} artifact`}>{display}</pre>
        <div className="panel-body artifact-source-map"><strong>Source map</strong><p>{mappedRules.length ? mappedRules.join(" · ") : "No rule revision is directly mapped to this artifact."}</p></div>
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
        <StatCard label="Scoped workflow" value={build.stats.routing.moved_to_workflow} note="Loaded for scoped tasks" />
        <StatCard label="Tool guard" value={build.stats.routing.guarded} note="Pre-tool JSON policy" />
        <StatCard label="Tests" value={build.stats.routing.tested} note="Manifest-linked cases" />
      </div></section>
    </>}
  </div>;
}
