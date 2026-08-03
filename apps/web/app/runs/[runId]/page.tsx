"use client";

import { ArrowLeft, CheckCircle2, FileText, GitCompareArrows, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, pct } from "@/lib/api";
import type { ArmMetrics, Report, Result, Run } from "@/lib/types";
import { Badge, Button, ErrorState, PageLoading, PageTitle, StatCard } from "@/components/ui";

const arms = ["baseline_unenforced", "compiled_unenforced", "compiled_enforced"];
const armNames: Record<string, string> = { baseline_unenforced: "Original · observe", compiled_unenforced: "Compiled · observe", compiled_enforced: "Compiled · enforced" };

export default function RunPage() {
  const { runId } = useParams<{ runId: string }>();
  const router = useRouter();
  const run = useQuery({ queryKey: ["run", runId], queryFn: () => api<Run>(`/api/v1/runs/${runId}`), refetchInterval: (query) => query.state.data?.status === "succeeded" ? false : 1000 });
  const results = useQuery({ queryKey: ["results", runId], queryFn: () => api<Result[]>(`/api/v1/runs/${runId}/results`), enabled: run.data?.status === "succeeded" });
  const report = useMutation({ mutationFn: () => api<Report>(`/api/v1/runs/${runId}/reports`, { method: "POST", body: "{}" }), onSuccess: (value) => router.push(`/reports/${value.id}`) });
  const [filter, setFilter] = useState("all");
  const grouped = useMemo(() => {
    const map = new Map<string, { test: Result["test"]; rows: Record<string, Result> }>();
    for (const row of results.data || []) {
      const entry = map.get(row.test_case_id) || { test: row.test, rows: {} };
      entry.rows[row.arm] = row;
      map.set(row.test_case_id, entry);
    }
    return [...map.values()].filter((entry) => filter === "all" || (filter === "failed" && Object.values(entry.rows).some((row) => row.verdict === "failed")) || (filter === "blocked" && Object.values(entry.rows).some((row) => Number(row.metrics.blocked_calls) > 0)) || (filter === "changed" && new Set(Object.values(entry.rows).map((row) => row.verdict)).size > 1));
  }, [results.data, filter]);
  if (run.isLoading || (run.data?.status === "succeeded" && results.isLoading)) return <main className="landing"><PageLoading label="Loading three-arm comparison" /></main>;
  if (run.error || results.error) return <main className="landing"><ErrorState error={run.error || results.error} onRetry={() => { run.refetch(); results.refetch(); }} /></main>;
  const metrics = run.data!.metrics as Record<string, ArmMetrics>;
  const guarded = metrics.compiled_enforced;
  const coverage = metrics.coverage as unknown as { test_count?: number };
  const expectedCases = run.data!.dataset_manifest.test_count;
  const ready = expectedCases > 0 && guarded?.cases === expectedCases && coverage?.test_count === expectedCases && guarded?.task_success_rate === 1 && guarded?.executed_violation_rate === 0 && guarded?.false_block_rate === 0;
  const adapterLabel = run.data!.adapter === "fixture" ? "Deterministic replay" : run.data!.adapter;
  const chart = arms.map((arm) => ({ arm: arm === "baseline_unenforced" ? "Original" : arm === "compiled_unenforced" ? "Compiled" : "Guarded", success: Math.round(metrics[arm].task_success_rate * 100), violations: Math.round(metrics[arm].executed_violation_rate * 100), falseBlocks: Math.round(metrics[arm].false_block_rate * 100) }));
  return <main className="landing" style={{ maxWidth: 1280, paddingTop: 34 }}>
    <div style={{ marginBottom: 18 }}><Link className="arrow-label" href={`/projects/${run.data!.project_id}/tests`}><ArrowLeft size={14} /> Back to tests</Link></div>
    <PageTitle eyebrow="Run comparison · Deterministic replay" title="Release behavior" detail="Prompt and guard effects remain separate across three arms, each starting from an identical initial state." actions={<Button onClick={() => report.mutate()} disabled={report.isPending}><FileText size={15} /> {report.isPending ? "Creating report…" : "Create evidence report"}</Button>} />
    <div className={`verdict-banner ${ready ? "" : "changes"}`}><CheckCircle2 size={22} /><div><h2>{ready ? "Ready for controlled pilot" : "Changes required"}</h2><p>{ready ? "All 16 guarded cases passed with no executed violations or false blocks." : "Review incomplete or failed guarded cases before the next controlled pilot."}</p></div></div>
    <div className="stat-grid">
      <StatCard label="Original success" value={pct(metrics.baseline_unenforced.task_success_rate)} note="Observe-only baseline" />
      <StatCard label="Compiled success" value={pct(metrics.compiled_unenforced.task_success_rate)} note="Prompt/workflow, observe only" />
      <StatCard label="Guarded success" value={pct(metrics.compiled_enforced.task_success_rate)} note="Compiled + enforced" tone="teal" />
      <StatCard label="Executed violations" value={pct(metrics.compiled_enforced.executed_violation_rate)} note="Guarded arm" tone="teal" />
    </div>
    <div className="two-column" style={{ marginBottom: 16 }}>
      <section className="panel"><div className="panel-header"><div><h2><GitCompareArrows size={15} /> Arm comparison</h2><p>Percentage of all 16 cases; lower is better for violations and false blocks.</p></div></div><div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={chart} margin={{ top: 5, right: 14, left: -12, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" /><XAxis dataKey="arm" tick={{ fontSize: 11 }} /><YAxis domain={[0, 100]} tick={{ fontSize: 10 }} /><Tooltip /><Legend wrapperStyle={{ fontSize: 11 }} /><Bar dataKey="success" name="Task success" fill="#0f766e" radius={[3, 3, 0, 0]} /><Bar dataKey="violations" name="Executed violations" fill="#b42318" radius={[3, 3, 0, 0]} /><Bar dataKey="falseBlocks" name="False blocks" fill="#b45309" radius={[3, 3, 0, 0]} /></BarChart></ResponsiveContainer></div></section>
      <section className="panel"><div className="panel-header"><div><h2>Run manifest</h2><p>Exact dataset and adapter provenance.</p></div></div><div className="panel-body"><div className="hash-list"><span>Adapter</span><code>{adapterLabel}</code><span>Model</span><code>{run.data!.model || "Not used — deterministic replay"}</code><span>Dataset</span><code>{run.data!.dataset_manifest.name}</code><span>Dataset hash</span><code>{run.data!.dataset_manifest.hash}</code><span>Cases</span><code>{run.data!.dataset_manifest.test_count} × {run.data!.requested_arms.length} arms</code></div></div></section>
    </div>
    <div className="toolbar">{[["all", "All cases"], ["failed", "Any failed"], ["blocked", "Blocked"], ["changed", "Changed outcome"]].map(([value, name]) => <button key={value} className={`filter-button ${filter === value ? "active" : ""}`} onClick={() => setFilter(value)}>{name}</button>)}</div>
    <section className="panel" style={{ overflow: "hidden" }}><table className="data-table"><thead><tr><th>Case</th>{arms.map((arm) => <th key={arm}>{armNames[arm]}</th>)}<th>First divergence</th></tr></thead><tbody>
      {grouped.map((entry) => { const guardedRow = entry.rows.compiled_enforced; return <tr key={guardedRow?.test_case_id}><td className="rule-title"><strong>{entry.test.title}</strong><small>{entry.test.stable_key}</small></td>{arms.map((arm) => <td key={arm}><span className={entry.rows[arm]?.verdict === "passed" ? "pass" : "fail"}>{entry.rows[arm]?.verdict === "passed" ? "Passed" : "Failed"}</span>{Number(entry.rows[arm]?.metrics.blocked_calls) > 0 && <><br /><Badge tone="amber">Intercepted</Badge></>}</td>)}<td>{guardedRow ? <Link className="arrow-label" href={`/scenario-results/${guardedRow.id}`}><ShieldCheck size={13} /> Inspect trace</Link> : "—"}</td></tr>; })}
    </tbody></table></section>
  </main>;
}
