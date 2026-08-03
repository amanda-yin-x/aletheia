"use client";

import { Play, ShieldCheck } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, label, RequestError } from "@/lib/api";
import type { Run, Summary, TestCase } from "@/lib/types";
import { Badge, Button, ErrorState, PageLoading, PageTitle, StatCard } from "@/components/ui";

export default function TestsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const router = useRouter();
  const client = useQueryClient();
  const tests = useQuery({ queryKey: ["tests", projectId], queryFn: () => api<TestCase[]>(`/api/v1/projects/${projectId}/test-cases`) });
  const summary = useQuery({ queryKey: ["summary", projectId], queryFn: () => api<Summary>(`/api/v1/projects/${projectId}/summary`) });
  const [filter, setFilter] = useState("all");
  const run = useMutation({ mutationFn: () => api<Run>(`/api/v1/projects/${projectId}/runs`, { method: "POST", body: JSON.stringify({ build_id: summary.data?.current_build?.id }) }), onSuccess: async (value) => { await client.invalidateQueries({ queryKey: ["summary", projectId] }); router.push(`/runs/${value.id}`); } });
  const filtered = useMemo(() => (tests.data || []).filter((test) => filter === "all" || test.spec.tags.includes(filter)), [tests.data, filter]);
  if (tests.isLoading || summary.isLoading) return <PageLoading label="Loading regression coverage" />;
  if (tests.error || summary.error) return <ErrorState error={tests.error || summary.error} onRetry={() => { tests.refetch(); summary.refetch(); }} />;
  const allTags = tests.data!.flatMap((test) => test.spec.tags);
  const positive = tests.data!.filter((test) => test.spec.tags.includes("positive")).length;
  const negative = tests.data!.filter((test) => test.spec.tags.includes("negative")).length;
  const boundary = tests.data!.filter((test) => test.spec.tags.includes("boundary")).length;
  return <div className="content-wrap">
    <PageTitle eyebrow="Declarative release suite" title="Regression tests" detail="Sixteen Aletheia-authored cases run against the baseline, compiled prompt, and compiled prompt with enforcement." actions={<Badge tone="blue">Aletheia suite</Badge>} />
    <div className="stat-grid">
      <StatCard label="Reviewed cases" value={tests.data!.length} note="Reviewed refund cases" />
      <StatCard label="Positive cases" value={positive} note="Allowed operations" tone="teal" />
      <StatCard label="Negative cases" value={negative} note="Denied or routed operations" tone="amber" />
      <StatCard label="Boundary cases" value={boundary} note="x−ε, x, and x+ε" />
    </div>
    <section className="panel" style={{ marginBottom: 16 }}>
      <div className="panel-header"><div><h2>Run comparison</h2><p>Every arm begins from an isolated initial state with a matching hash.</p></div></div>
      <div className="panel-body run-controls">
        <div className="field"><label htmlFor="adapter">Adapter</label><select id="adapter" defaultValue="fixture"><option value="fixture">Deterministic replay</option></select></div>
        <div className="field"><label htmlFor="arms">Comparison arms</label><select id="arms" defaultValue="all"><option value="all">All three arms</option></select></div>
        <div className="field"><label htmlFor="cases">Case set</label><select id="cases" defaultValue="demo"><option value="demo">Aletheia refund suite · 16</option></select></div>
        <Button disabled={!summary.data!.current_build || run.isPending} onClick={() => run.mutate()}><Play size={15} /> {run.isPending ? "Running 0 / 48…" : "Run comparison"}</Button>
      </div>
      {!summary.data!.current_build && <div className="build-blocked" style={{ margin: "0 18px 18px" }}><div><strong>Candidate build required</strong><p>Complete rule review and compile the artifacts before testing.</p></div><a className="button button-secondary" href={`/projects/${projectId}/build`}>Open Build</a></div>}
      {run.error && <div className="build-blocked" style={{ margin: "0 18px 18px" }}><div><strong>Run could not start</strong><p>{run.error instanceof RequestError ? run.error.message : "Try again after checking the current build."}</p></div></div>}
    </section>
    <div className="toolbar" aria-label="Test filters">{["all", "refund", "boundary", "approval", "identity", "finding", "style"].map((tag) => <button className={`filter-button ${filter === tag ? "active" : ""}`} key={tag} onClick={() => setFilter(tag)}>{label(tag)} {tag !== "all" && `(${allTags.filter((value) => value === tag).length})`}</button>)}</div>
    <section className="panel" style={{ overflow: "hidden" }}>
      <table className="data-table"><thead><tr><th>Case</th><th>Coverage</th><th>Expected guarded decision</th><th>Provenance</th><th>Review</th></tr></thead><tbody>
        {filtered.map((test) => <tr key={test.id}><td className="rule-title"><strong>{test.title}</strong><small>{test.stable_key}</small></td><td><div className="tags">{test.spec.tags.map((tag) => <span className="tag" key={tag}>{tag}</span>)}</div></td><td><Badge tone={test.spec.expected.guarded_decision === "allow" ? "teal" : test.spec.expected.guarded_decision === "deny" ? "red" : "amber"}><ShieldCheck size={11} /> {label(String(test.spec.expected.guarded_decision))}</Badge></td><td><Badge tone="blue">Aletheia-authored</Badge></td><td><Badge tone="teal">{label(test.review_status)}</Badge></td></tr>)}
      </tbody></table>
    </section>
  </div>;
}
