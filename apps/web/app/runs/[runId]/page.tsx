"use client";

import { AlertTriangle, ArrowLeft, CheckCircle2, FileText, GitCompareArrows, RefreshCw, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, pct } from "@/lib/api";
import { operationStatusFailed, operationStatusIsTerminal } from "@/lib/operations";
import { armChartName, armMetrics, armName, caseArmSummary, normalizeArms, recordMetric, releaseCoverageReady } from "@/lib/run-presentation";
import type { Report, Result, Run } from "@/lib/types";
import { Badge, Button, ErrorState, PageLoading, PageTitle, StatCard } from "@/components/ui";

export default function RunPage() {
  const { runId } = useParams<{ runId: string }>();
  const router = useRouter();
  const run = useQuery({
    queryKey: ["run", runId],
    queryFn: () => api<Run>(`/api/v1/runs/${runId}`),
    refetchInterval: (query) => operationStatusIsTerminal(query.state.data?.status) ? false : 1000,
  });
  const results = useQuery({
    queryKey: ["results", runId],
    queryFn: () => api<Result[]>(`/api/v1/runs/${runId}/results`),
    enabled: run.data?.status === "succeeded",
  });
  const report = useMutation({
    mutationFn: () => api<Report>(`/api/v1/runs/${runId}/reports`, { method: "POST", body: "{}" }),
    onSuccess: (value) => router.push(`/reports/${value.id}`),
  });
  const [filter, setFilter] = useState("all");
  const grouped = useMemo(() => {
    const map = new Map<string, { test: Result["test"]; rows: Record<string, Result> }>();
    for (const row of results.data || []) {
      const entry = map.get(row.test_case_id) || { test: row.test, rows: {} };
      entry.rows[row.arm] = row;
      map.set(row.test_case_id, entry);
    }
    return [...map.values()].filter((entry) =>
      filter === "all"
      || (filter === "failed" && Object.values(entry.rows).some((row) => row.verdict === "failed"))
      || (filter === "blocked" && Object.values(entry.rows).some((row) => Number(row.metrics.blocked_calls) > 0))
      || (filter === "changed" && new Set(Object.values(entry.rows).map((row) => row.verdict)).size > 1),
    );
  }, [results.data, filter]);

  if (run.isLoading) return <main className="landing"><PageLoading label="Loading run status" /></main>;
  if (run.error || !run.data) return <main className="landing"><ErrorState error={run.error || new Error("The run response was empty.")} onRetry={() => run.refetch()} /></main>;

  const data = run.data;
  const arms = normalizeArms(data.requested_arms);
  const expectedCases = data.dataset_manifest.test_count;
  const matrixSummary = caseArmSummary(expectedCases, arms);

  if (operationStatusFailed(data.status)) {
    const status = data.status.replaceAll("_", " ");
    return <main className="landing" style={{ maxWidth: 980, paddingTop: 34 }}>
      <div style={{ marginBottom: 18 }}><Link className="arrow-label" href={`/projects/${data.project_id}/tests`}><ArrowLeft size={14} /> Back to tests</Link></div>
      <PageTitle eyebrow="Run comparison · Terminal state" title="Run did not complete" detail={`${matrixSummary} · deterministic replay`} />
      <div className="build-blocked" role="alert">
        <AlertTriangle size={22} />
        <div><strong>The run ended as {status}.</strong><p>Polling has stopped. Review the worker logs or current build, then start a new comparison from Tests.</p></div>
        <Button variant="secondary" onClick={() => run.refetch()}><RefreshCw size={15} /> Refresh status</Button>
      </div>
    </main>;
  }

  if (!operationStatusIsTerminal(data.status)) {
    return <main className="landing"><PageLoading label={`Running ${matrixSummary}`} /></main>;
  }
  if (results.isLoading) return <main className="landing"><PageLoading label={`Loading results for ${matrixSummary}`} /></main>;
  if (results.error) return <main className="landing"><ErrorState error={results.error} onRetry={() => results.refetch()} /></main>;

  const guardedArm = arms.includes("compiled_enforced") ? "compiled_enforced" : arms.at(-1);
  const guarded = armMetrics(data.metrics, guardedArm);
  const coverage = recordMetric(data.metrics, "coverage");
  const ready = expectedCases > 0
    && guarded?.cases === expectedCases
    && releaseCoverageReady(coverage, expectedCases)
    && guarded.task_success_rate === 1
    && guarded.executed_violation_rate === 0
    && guarded.false_block_rate === 0
    && guarded.tool_validation_error_rate === 0;
  const adapterLabel = data.adapter === "fixture" ? "Deterministic replay" : data.adapter;
  const chart = arms.flatMap((arm) => {
    const value = armMetrics(data.metrics, arm);
    return value ? [{
      arm: armChartName(arm),
      success: Math.round(value.task_success_rate * 100),
      violations: Math.round(value.executed_violation_rate * 100),
      falseBlocks: Math.round(value.false_block_rate * 100),
    }] : [];
  });

  return <main className="landing" style={{ maxWidth: 1280, paddingTop: 34 }}>
    <div style={{ marginBottom: 18 }}><Link className="arrow-label" href={`/projects/${data.project_id}/tests`}><ArrowLeft size={14} /> Back to tests</Link></div>
    <PageTitle
      eyebrow="Run comparison · Deterministic replay"
      title="Release behavior"
      detail={`Prompt and guard effects remain separate across ${arms.length} labelled ${arms.length === 1 ? "arm" : "arms"}, each starting from an identical initial state.`}
      actions={<Button onClick={() => report.mutate()} disabled={report.isPending}><FileText size={15} /> {report.isPending ? "Creating report…" : "Create evidence report"}</Button>}
    />
    {report.error && <div className="build-blocked" role="alert"><AlertTriangle size={20} /><div><strong>Evidence report could not be created</strong><p>{report.error instanceof Error ? report.error.message : "Try again after checking this run."}</p></div><Button variant="secondary" onClick={() => report.mutate()}>Try again</Button></div>}
    <div className={`verdict-banner ${ready ? "" : "changes"}`}>
      {ready ? <CheckCircle2 size={22} /> : <AlertTriangle size={22} />}
      <div><h2>{ready ? "Fixture suite passed" : "Changes required"}</h2><p>{ready ? `All ${expectedCases} ${expectedCases === 1 ? "guarded case passed" : "guarded cases passed"} with no executed violations, validation errors, or false blocks.` : "Review incomplete or failed guarded cases before another fixture run."}</p></div>
    </div>
    <div className="stat-grid">
      {arms.map((arm) => {
        const value = armMetrics(data.metrics, arm);
        return <StatCard key={arm} label={`${armName(arm)} success`} value={value ? pct(value.task_success_rate) : "Not recorded"} note={`${value?.cases ?? 0} evaluated ${value?.cases === 1 ? "case" : "cases"}`} tone={arm === guardedArm ? "teal" : undefined} />;
      })}
      <StatCard label={`${guardedArm ? armName(guardedArm) : "Guarded arm"} violations`} value={guarded ? pct(guarded.executed_violation_rate) : "Not recorded"} note="Executed tool violations" tone="teal" />
    </div>
    <div className="two-column" style={{ marginBottom: 16 }}>
      <section className="panel"><div className="panel-header"><div><h2><GitCompareArrows size={15} /> Arm comparison</h2><p>Percentage of all {expectedCases} {expectedCases === 1 ? "case" : "cases"}; lower is better for violations and false blocks.</p></div></div><div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={chart} margin={{ top: 5, right: 14, left: -12, bottom: 0 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" /><XAxis dataKey="arm" tick={{ fontSize: 11 }} /><YAxis domain={[0, 100]} tick={{ fontSize: 10 }} /><Tooltip /><Legend wrapperStyle={{ fontSize: 11 }} /><Bar dataKey="success" name="Task success" fill="#0f766e" radius={[3, 3, 0, 0]} /><Bar dataKey="violations" name="Executed violations" fill="#b42318" radius={[3, 3, 0, 0]} /><Bar dataKey="falseBlocks" name="False blocks" fill="#b45309" radius={[3, 3, 0, 0]} /></BarChart></ResponsiveContainer></div></section>
      <section className="panel"><div className="panel-header"><div><h2>Run manifest</h2><p>Exact dataset and adapter provenance.</p></div></div><div className="panel-body"><div className="hash-list"><span>Adapter</span><code>{adapterLabel}</code><span>Model</span><code>{data.model || "Not used — deterministic replay"}</code><span>Dataset</span><code>{data.dataset_manifest.name}</code><span>Dataset hash</span><code>{data.dataset_manifest.hash}</code><span>Cases</span><code>{matrixSummary}</code></div></div></section>
    </div>
    <div className="toolbar">{[["all", "All cases"], ["failed", "Any failed"], ["blocked", "Blocked"], ["changed", "Changed outcome"]].map(([value, name]) => <button key={value} className={`filter-button ${filter === value ? "active" : ""}`} onClick={() => setFilter(value)}>{name}</button>)}</div>
    <section className="panel" style={{ overflow: "hidden" }}><table className="data-table"><thead><tr><th>Case</th>{arms.map((arm) => <th key={arm}>{armName(arm)}</th>)}<th>First divergence</th></tr></thead><tbody>
      {grouped.map((entry) => {
        const inspectedRow = (guardedArm && entry.rows[guardedArm]) || arms.map((arm) => entry.rows[arm]).find(Boolean);
        return <tr key={entry.test.stable_key}>
          <td className="rule-title"><strong>{entry.test.title}</strong><small>{entry.test.stable_key}</small></td>
          {arms.map((arm) => {
            const row = entry.rows[arm];
            return <td key={arm}>{row ? <><span className={row.verdict === "passed" ? "pass" : "fail"}>{row.verdict === "passed" ? "Passed" : "Failed"}</span>{Number(row.metrics.blocked_calls) > 0 && <><br /><Badge tone="amber">Intercepted</Badge></>}</> : <span>Not returned</span>}</td>;
          })}
          <td>{inspectedRow ? <Link className="arrow-label" href={`/scenario-results/${inspectedRow.id}`}><ShieldCheck size={13} /> Inspect trace</Link> : "—"}</td>
        </tr>;
      })}
    </tbody></table></section>
  </main>;
}
