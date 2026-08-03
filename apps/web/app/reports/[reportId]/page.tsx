"use client";

import { ArrowLeft, FileJson2, FileText, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Fragment } from "react";
import { useQuery } from "@tanstack/react-query";
import { API_URL, api, pct, shortHash } from "@/lib/api";
import type { Report } from "@/lib/types";
import { ErrorState, PageLoading, PageTitle, StatCard } from "@/components/ui";

export default function ReportPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const report = useQuery({ queryKey: ["report", reportId], queryFn: () => api<Report>(`/api/v1/reports/${reportId}`) });
  if (report.isLoading) return <main className="landing"><PageLoading label="Loading immutable evidence report" /></main>;
  if (report.error) return <main className="landing"><ErrorState error={report.error} onRetry={() => report.refetch()} /></main>;
  const data = report.data!;
  const metrics = data.evidence.metrics;
  const rawProvenance = data.evidence.provenance;
  const provenance = [
    ["Dataset", String(rawProvenance.dataset || rawProvenance.name || "Aletheia-authored refund boundary suite")],
    ["Version", String(rawProvenance.version || "1")],
    ["Data scope", String(rawProvenance.data_scope || "Evaluation dataset · no customer records")],
    ["Adapter", rawProvenance.adapter === "fixture" ? "Deterministic replay" : String(rawProvenance.adapter || "Not recorded")],
    ["Model", !rawProvenance.model || String(rawProvenance.model).includes("fixture") ? "Not used" : String(rawProvenance.model)],
  ] as const;
  return <main className="landing" style={{ maxWidth: 1180, paddingTop: 34 }}>
    <div style={{ marginBottom: 18 }}><Link className="arrow-label" href={`/runs/${data.run_id}`}><ArrowLeft size={14} /> Back to run comparison</Link></div>
    <PageTitle eyebrow="Immutable release evidence" title="Policy release report" detail={`Snapshot ${shortHash(data.content_hash)} · ${new Date(data.created_at).toLocaleString()}`} actions={<><a className="button button-secondary" href={`${API_URL}/api/v1/reports/${reportId}/export?format=markdown`}><FileText size={15} /> Download Markdown</a><a className="button button-primary" href={`${API_URL}/api/v1/reports/${reportId}/export?format=json`}><FileJson2 size={15} /> Download JSON</a></>} />
    <section className="report-scope"><h2>Scope and evidence boundary</h2><p>{data.evidence.evidence_boundary}</p><p><strong>{data.evidence.deterministic_runtime_boundary}</strong></p></section>
    <div className="verdict-banner"><ShieldCheck size={22} /><div><h2>{data.verdict}</h2><p>This verdict covers the persisted build, the 16-case release suite, and deterministic replay.</p></div></div>
    <div className="stat-grid">
      <StatCard label="Cases" value={data.evidence.test_count} note="Aletheia-authored cases" />
      <StatCard label="Original success" value={pct(metrics.baseline_unenforced.task_success_rate)} note="Observe-only" />
      <StatCard label="Guarded success" value={pct(metrics.compiled_enforced.task_success_rate)} note="Compiled + enforcement" tone="teal" />
      <StatCard label="Guarded violations" value={pct(metrics.compiled_enforced.executed_violation_rate)} note="Executed tool violations" tone="teal" />
    </div>
    <section className="panel">
      <div className="report-section"><h2>Dataset and execution provenance</h2><div className="hash-list">{provenance.flatMap(([name, value]) => [<span key={`${name}-label`}>{name}</span>, <code key={`${name}-value`}>{value}</code>])}</div></div>
      <div className="report-section"><h2>Evidence hashes</h2><div className="hash-list">{Object.entries(data.evidence.hashes).map(([name, value]) => <Fragment key={name}><span>{name}</span><code>{value}</code></Fragment>)}</div></div>
      <div className="report-section"><h2>Limitations</h2><ul className="limitations">{data.evidence.limitations.map((item) => <li key={item}>{item}</li>)}</ul></div>
    </section>
  </main>;
}
