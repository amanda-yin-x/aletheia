"use client";

import { ArrowLeft, FileJson2, FileText, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Fragment } from "react";
import { useQuery } from "@tanstack/react-query";
import { API_URL, api, pct, shortHash } from "@/lib/api";
import { armMetrics, armName, caseArmSummary, evidenceValue, normalizeArms } from "@/lib/run-presentation";
import type { Report } from "@/lib/types";
import { ErrorState, PageLoading, PageTitle, StatCard } from "@/components/ui";

export default function ReportPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const report = useQuery({ queryKey: ["report", reportId], queryFn: () => api<Report>(`/api/v1/reports/${reportId}`) });
  if (report.isLoading) return <main className="landing"><PageLoading label="Loading evidence report snapshot" /></main>;
  if (report.error || !report.data) return <main className="landing"><ErrorState error={report.error || new Error("The report response was empty.")} onRetry={() => report.refetch()} /></main>;

  const data = report.data;
  const metrics = data.evidence.metrics;
  const arms = normalizeArms(data.evidence.comparison_arms);
  const guardedArm = arms.includes("compiled_enforced") ? "compiled_enforced" : arms.at(-1);
  const guarded = armMetrics(metrics, guardedArm);
  const matrixSummary = caseArmSummary(data.evidence.test_count, arms);
  const rawProvenance = data.evidence.provenance;
  const provenance = [
    ["Dataset", evidenceValue(rawProvenance.dataset || rawProvenance.name || "Aletheia-authored refund boundary suite")],
    ["Version", evidenceValue(rawProvenance.version || "1")],
    ["Data scope", evidenceValue(rawProvenance.data_scope || "Evaluation dataset · no customer records")],
    ["Adapter", rawProvenance.adapter === "fixture" ? "Deterministic replay" : evidenceValue(rawProvenance.adapter)],
    ["Model", !rawProvenance.model || String(rawProvenance.model).toLowerCase().includes("fixture") ? "Not used" : evidenceValue(rawProvenance.model)],
  ] as const;
  const hashes = data.evidence.report_digest
    ? { report_digest: data.evidence.report_digest, ...data.evidence.hashes }
    : data.evidence.hashes;

  return <main className="landing" style={{ maxWidth: 1180, paddingTop: 34 }}>
    <div style={{ marginBottom: 18 }}><Link className="arrow-label" href={`/runs/${data.run_id}`}><ArrowLeft size={14} /> Back to run comparison</Link></div>
    <PageTitle eyebrow="Stored release evidence" title="Policy release report" detail={`Snapshot ${shortHash(data.content_hash)} · ${new Date(data.created_at).toLocaleString()}`} actions={<><a className="button button-secondary" href={`${API_URL}/api/v1/reports/${reportId}/export?format=markdown`}><FileText size={15} /> Download Markdown</a><a className="button button-primary" href={`${API_URL}/api/v1/reports/${reportId}/export?format=json`}><FileJson2 size={15} /> Download JSON</a></>} />
    <section className="report-scope"><h2>Scope and evidence boundary</h2><p>{data.evidence.evidence_boundary}</p><p><strong>{data.evidence.deterministic_runtime_boundary}</strong></p></section>
    <div className={`verdict-banner ${data.verdict === "Fixture suite passed" ? "" : "changes"}`}><ShieldCheck size={22} /><div><h2>{data.verdict}</h2><p>This verdict covers the persisted build, {matrixSummary}, and deterministic replay.</p></div></div>
    <div className="stat-grid">
      <StatCard label="Cases" value={data.evidence.test_count} note="Aletheia-authored cases" />
      {arms.map((arm) => {
        const value = armMetrics(metrics, arm);
        return <StatCard key={arm} label={`${armName(arm)} success`} value={value ? pct(value.task_success_rate) : "Not recorded"} note={`${value?.cases ?? 0} evaluated ${value?.cases === 1 ? "case" : "cases"}`} tone={arm === guardedArm ? "teal" : undefined} />;
      })}
      <StatCard label={`${guardedArm ? armName(guardedArm) : "Guarded arm"} violations`} value={guarded ? pct(guarded.executed_violation_rate) : "Not recorded"} note="Executed tool violations" tone="teal" />
    </div>
    <section className="panel">
      <div className="report-section"><h2>Dataset and execution provenance</h2><div className="hash-list">{provenance.flatMap(([name, value]) => [<span key={`${name}-label`}>{name}</span>, <code key={`${name}-value`}>{value}</code>])}</div></div>
      <div className="report-section"><h2>Evidence hashes</h2><div className="hash-list">{Object.entries(hashes).map(([name, value]) => <Fragment key={name}><span>{name}</span><code>{evidenceValue(value)}</code></Fragment>)}</div></div>
      <div className="report-section"><h2>Limitations</h2><ul className="limitations">{data.evidence.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>
    </section>
  </main>;
}
