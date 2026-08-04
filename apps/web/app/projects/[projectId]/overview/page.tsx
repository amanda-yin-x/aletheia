"use client";

import { AlertTriangle, Check, Clock3, FileText, Play, ShieldCheck } from "lucide-react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, shortHash } from "@/lib/api";
import { caseArmSummary, normalizeArms } from "@/lib/run-presentation";
import type { Project, Summary } from "@/lib/types";
import { Badge, ErrorState, LinkButton, PageLoading, PageTitle, StatCard } from "@/components/ui";

export default function OverviewPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => api<Project>(`/api/v1/projects/${projectId}`) });
  const summary = useQuery({ queryKey: ["summary", projectId], queryFn: () => api<Summary>(`/api/v1/projects/${projectId}/summary`) });
  if (project.isLoading || summary.isLoading) return <PageLoading />;
  if (project.error || summary.error) return <ErrorState error={project.error || summary.error} onRetry={() => { project.refetch(); summary.refetch(); }} />;
  const data = summary.data!;
  const lastRunArms = normalizeArms(data.last_run?.requested_arms);
  const nextHref = data.critical_findings ? `/projects/${projectId}/rules` : data.current_build ? `/projects/${projectId}/tests` : `/projects/${projectId}/build`;
  const nextLabel = data.critical_findings ? "Continue policy review" : data.current_build ? "Run comparison" : "Build candidate";
  return <div className="content-wrap">
    <PageTitle eyebrow="Policy release workspace · Evaluation data" title={project.data!.name} detail={project.data!.description} actions={<><Badge tone="blue">Evaluation data</Badge><LinkButton href={nextHref}>{nextLabel}</LinkButton></>} />
    <div className="stat-grid">
      <StatCard label="Versioned sources" value={data.sources} note="Prompt, policies, SOP, schemas" />
      <StatCard label="Approved rules" value={data.approved_rules} note="Versioned source records" tone="teal" />
      <StatCard label="Unresolved critical" value={data.critical_findings} note={data.critical_findings ? "Blocks candidate build" : "No build blockers"} tone={data.critical_findings ? "red" : "teal"} />
      <StatCard label="Regression cases" value={data.tests} note="Positive, negative, and boundary" />
    </div>
    <section className="panel" style={{ marginBottom: 16 }}>
      <div className="panel-header"><div><h2>Release workflow</h2><p>Review gates are explicit; artifacts and results are stored snapshots.</p></div></div>
      <div className="workflow-track">
        <div className="workflow-stage complete"><span className="stage-icon"><Check size={13} /></span>Sources ingested</div>
        <div className={`workflow-stage ${data.critical_findings ? "current" : "complete"}`}><span className="stage-icon">2</span>Rules reviewed</div>
        <div className={`workflow-stage ${!data.critical_findings && !data.current_build ? "current" : data.current_build ? "complete" : ""}`}><span className="stage-icon">3</span>Candidate built</div>
        <div className={`workflow-stage ${data.current_build && !data.last_run ? "current" : data.last_run ? "complete" : ""}`}><span className="stage-icon">4</span>Comparison run</div>
        <div className={`workflow-stage ${data.last_run ? "current" : ""}`}><span className="stage-icon">5</span>Evidence report</div>
      </div>
    </section>
    <div className="two-column">
      <section className="panel">
        <div className="panel-header"><div><h2>Current release state</h2><p>Persisted, computed workspace facts.</p></div></div>
        <div className="panel-body">
          <ul className="activity-list">
            <li><FileText size={17} /><p><strong>Source corpus loaded</strong><small> {data.sources} versioned documents</small></p><Badge tone="teal">Complete</Badge></li>
            <li><AlertTriangle size={17} /><p><strong>Policy findings</strong><small> {data.critical_findings} critical unresolved</small></p><Badge tone={data.critical_findings ? "red" : "teal"}>{data.critical_findings ? "Action" : "Clear"}</Badge></li>
            <li><ShieldCheck size={17} /><p><strong>Candidate build</strong><small> {data.current_build ? shortHash(data.current_build.content_hash) : "Not built"}</small></p><Badge>{data.current_build ? "Stored" : "Pending"}</Badge></li>
          </ul>
        </div>
      </section>
      <section className="panel" id="latest-report">
        <div className="panel-header"><div><h2>Latest comparison</h2><p>All arms start from the same initial state.</p></div></div>
        <div className="panel-body">
          {data.last_run ? <>
            <div className="verdict-banner"><Play size={20} /><div><h2>Run completed</h2><p>{caseArmSummary(data.last_run.dataset_manifest.test_count, lastRunArms)} · deterministic replay</p></div></div>
            <LinkButton href={`/runs/${data.last_run.id}`}>Inspect comparison</LinkButton>
          </> : <div style={{ padding: "24px 0", textAlign: "center", color: "var(--muted)" }}><Clock3 size={24} /><p>No run yet. Complete review and build the candidate first.</p></div>}
        </div>
      </section>
    </div>
  </div>;
}
