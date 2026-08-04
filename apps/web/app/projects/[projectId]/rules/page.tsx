"use client";

import { Check, ExternalLink, ShieldCheck, X } from "lucide-react";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, label } from "@/lib/api";
import type { Finding, Rule, TestCase } from "@/lib/types";
import { conditionRows, updateConditionValue } from "@/lib/presentation";
import { Badge, Button, ErrorState, PageLoading, PageTitle } from "@/components/ui";
import { ConflictResolutionForm, type ConflictResolutionDecision } from "@/features/conflict-resolution-form";

const tone = (value: string) => value === "critical" || value === "rejected" ? "red" : value === "approved" ? "teal" : value === "needs_review" || value === "high" ? "amber" : "neutral";

export default function RulesPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const client = useQueryClient();
  const rules = useQuery({ queryKey: ["rules", projectId], queryFn: () => api<Rule[]>(`/api/v1/projects/${projectId}/rules`) });
  const findings = useQuery({ queryKey: ["findings", projectId], queryFn: () => api<Finding[]>(`/api/v1/projects/${projectId}/findings`) });
  const tests = useQuery({ queryKey: ["tests", projectId], queryFn: () => api<TestCase[]>(`/api/v1/projects/${projectId}/test-cases`) });
  const [selected, setSelected] = useState<Rule | null>(null);
  const [draftCondition, setDraftCondition] = useState<Record<string, unknown> | null>(null);
  const [filter, setFilter] = useState("all");
  const [resolvingFindingId, setResolvingFindingId] = useState<string | null>(null);
  const drawerRef = useRef<HTMLElement>(null);
  const openRule = (rule: Rule) => { setSelected(rule); setDraftCondition(structuredClone(rule.condition)); };
  const closeResolution = (findingId: string) => {
    resolve.reset();
    setResolvingFindingId(null);
    window.requestAnimationFrame(() => document.getElementById(`review-conflict-${findingId}`)?.focus());
  };
  useEffect(() => {
    if (!selected) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const frame = window.requestAnimationFrame(() => drawerRef.current?.querySelector<HTMLElement>("button, a, input, select, textarea")?.focus());
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); setSelected(null); return; }
      if (event.key !== "Tab" || !drawerRef.current) return;
      const controls = [...drawerRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])")];
      if (!controls.length) return;
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => { window.cancelAnimationFrame(frame); document.removeEventListener("keydown", onKeyDown); previous?.focus(); };
  }, [selected]);
  const refresh = async () => { await Promise.all([client.invalidateQueries({ queryKey: ["rules", projectId] }), client.invalidateQueries({ queryKey: ["findings", projectId] }), client.invalidateQueries({ queryKey: ["summary", projectId] })]); };
  const review = useMutation({ mutationFn: ({ rule, action }: { rule: Rule; action: "approve" | "reject" }) => api<Rule>(`/api/v1/rules/${rule.id}/${action}`, { method: "POST", body: JSON.stringify({ expected_revision: rule.revision }) }), onSuccess: async (value) => { setSelected(value); await refresh(); } });
  const saveCondition = useMutation({ mutationFn: ({ rule, condition }: { rule: Rule; condition: Record<string, unknown> }) => api<Rule>(`/api/v1/rules/${rule.id}`, { method: "PATCH", body: JSON.stringify({ expected_revision: rule.revision, condition, reviewer_note: "Condition revised in the bounded form editor; source quote unchanged." }) }), onSuccess: async (value) => { setSelected(value); setDraftCondition(structuredClone(value.condition)); await refresh(); } });
  const resolve = useMutation({
    mutationFn: (decision: ConflictResolutionDecision) => api<Finding>(`/api/v1/findings/${decision.findingId}`, {
      method: "PATCH",
      body: JSON.stringify({
        resolution_state: "resolved",
        expected_resolution_state: decision.expectedResolutionState,
        winner_rule_id: decision.winnerRuleId,
        loser_rule_id: decision.loserRuleId,
        authority: decision.authority,
        resolution_note: decision.rationale,
      }),
    }),
    onSuccess: async (_finding, decision) => {
      setResolvingFindingId(null);
      await refresh();
      window.requestAnimationFrame(() => document.getElementById(`finding-${decision.findingId}`)?.focus());
    },
  });
  const filtered = useMemo(() => (rules.data || []).filter((rule) => filter === "all" || (filter === "review" && rule.status === "needs_review") || (filter === "critical" && rule.severity === "critical") || (filter === "guarded" && rule.enforcement === "guard") || (filter === "missing" && !(tests.data || []).some((test) => test.spec.rule_ids.includes(rule.stable_key)))), [rules.data, tests.data, filter]);
  if (rules.isLoading || findings.isLoading || tests.isLoading) return <PageLoading label="Loading reviewed rule set" />;
  if (rules.error || findings.error || tests.error) return <ErrorState error={rules.error || findings.error || tests.error} onRetry={() => { rules.refetch(); findings.refetch(); tests.refetch(); }} />;
  const openFindings = findings.data!.filter((finding) => finding.resolution_state === "open");
  return <div className="content-wrap">
    <PageTitle eyebrow="Human review gate" title="Rules and findings" detail="Model-shaped candidates remain drafts until their quote, meaning, and deterministic condition are reviewed." actions={<Badge tone="blue">{rules.data!.length} current revisions</Badge>} />
    <div className="finding-stack">
      {findings.data!.map((finding) => {
        const related = rules.data!.filter((rule) => finding.related_rule_ids.includes(rule.id));
        const isResolving = resolvingFindingId === finding.id;
        return <article id={`finding-${finding.id}`} tabIndex={-1} key={finding.id} className={`finding-card ${finding.severity} ${finding.resolution_state === "resolved" ? "resolved" : ""} ${isResolving ? "is-reviewing" : ""}`}>
          <div><strong><Badge tone={tone(finding.severity) as "red" | "amber" | "neutral"}>{finding.proof_status}</Badge> {finding.message}</strong><p>{finding.resolution_state === "resolved" ? finding.resolution_note : `${label(finding.type)} · ${label(finding.severity)} severity`}</p>{related.length > 1 && !isResolving && <div className="finding-evidence">{related.map((rule) => <blockquote key={rule.id}><small>{rule.source_refs[0]?.document_name} · revision {rule.revision}</small>{rule.source_refs[0]?.quote}</blockquote>)}</div>}</div>
          {finding.resolution_state === "open" && finding.severity === "critical" ? !isResolving && <Button id={`review-conflict-${finding.id}`} variant="secondary" className="button-small" disabled={resolve.isPending} onClick={() => { resolve.reset(); setResolvingFindingId(finding.id); }}>Review conflict</Button> : <Badge tone={finding.resolution_state === "resolved" ? "teal" : "neutral"}>{label(finding.resolution_state)}</Badge>}
          {isResolving && <ConflictResolutionForm
            finding={finding}
            relatedRules={related}
            isPending={resolve.isPending}
            error={resolve.error}
            onCancel={() => closeResolution(finding.id)}
            onSubmit={(decision) => resolve.mutate(decision)}
          />}
        </article>;
      })}
    </div>
    <div className="toolbar" aria-label="Rule filters">
      {[["all", "All"], ["review", "Needs review"], ["critical", "Critical"], ["guarded", "Guarded"], ["missing", "Missing test"]].map(([value, text]) => <button key={value} className={`filter-button ${filter === value ? "active" : ""}`} onClick={() => setFilter(value)}>{text}</button>)}
      <span style={{ marginLeft: "auto", color: "var(--muted)", fontSize: 11 }}>{openFindings.filter((item) => item.severity === "critical").length} critical build blockers</span>
    </div>
    <section className="panel" style={{ overflow: "hidden" }}>
      <table className="data-table"><thead><tr><th>Status</th><th>Rule</th><th>Type</th><th>Severity</th><th>Enforcement</th><th>Source</th><th>Tests</th></tr></thead>
        <tbody>{filtered.map((rule) => { const count = tests.data!.filter((test) => test.spec.rule_ids.includes(rule.stable_key)).length; return <tr key={rule.id} onClick={() => openRule(rule)} tabIndex={0} onKeyDown={(event) => { if (event.key === "Enter") openRule(rule); }}>
          <td><Badge tone={tone(rule.status) as "red" | "teal" | "amber" | "neutral"}>{label(rule.status)}</Badge></td>
          <td className="rule-title"><strong>{rule.title}</strong><small>{rule.stable_key} · rev {rule.revision}</small></td>
          <td>{label(rule.category)}</td><td><Badge tone={tone(rule.severity) as "red" | "teal" | "amber" | "neutral"}>{label(rule.severity)}</Badge></td><td>{label(rule.enforcement)}</td><td>{rule.source_refs[0]?.document_name}<br /><small>lines {rule.source_refs[0]?.line_start}–{rule.source_refs[0]?.line_end}</small></td><td>{count}</td>
        </tr>; })}</tbody>
      </table>
    </section>
    {selected && <div className="drawer-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelected(null); }}>
      <aside ref={drawerRef} className="drawer" role="dialog" aria-modal="true" aria-labelledby="rule-drawer-title">
        <div className="drawer-head"><div><Badge tone={tone(selected.status) as "red" | "teal" | "amber" | "neutral"}>{label(selected.status)}</Badge><h2 id="rule-drawer-title">{selected.title}</h2></div><button className="icon-button" aria-label="Close rule details" onClick={() => setSelected(null)}><X size={17} /></button></div>
        <div className="drawer-body">
          <section className="drawer-section"><h3>Exact source quote</h3><blockquote className="quote">{selected.source_refs[0]?.quote}</blockquote><a className="arrow-label" style={{ marginTop: 9 }} href={`/projects/${projectId}/sources?document=${encodeURIComponent(selected.source_refs[0]?.document_id || "")}#line-${selected.source_refs[0]?.line_start || 1}`}>Open {selected.source_refs[0]?.document_name}, lines {selected.source_refs[0]?.line_start}–{selected.source_refs[0]?.line_end} <ExternalLink size={13} /></a></section>
          <section className="drawer-section"><h3>Normalized rule</h3><p>{selected.normative_text}</p></section>
          <section className="drawer-section"><h3>Deterministic condition · bounded form editor</h3>{conditionRows(draftCondition || selected.condition).length ? <><div className="condition-card">{conditionRows(draftCondition || selected.condition).map((row, index) => <div className="condition-row" key={index}><code>{row.fact}</code><Badge>{label(row.op)}</Badge><input aria-label={`Value for ${row.fact}`} value={row.value} onClick={(event) => event.stopPropagation()} onChange={(event) => setDraftCondition(updateConditionValue(draftCondition || selected.condition, index, event.target.value))} /></div>)}</div><div className="condition-editor-footer"><small>Values accept JSON scalars. Facts and operators are allowlisted by the API.</small><Button variant="secondary" className="button-small" disabled={saveCondition.isPending || JSON.stringify(draftCondition) === JSON.stringify(selected.condition)} onClick={() => draftCondition && saveCondition.mutate({ rule: selected, condition: draftCondition })}>Save condition revision</Button></div></> : <p style={{ color: "var(--muted)" }}>No machine condition. This rule remains prompt, test, or human-review content.</p>}</section>
          <section className="drawer-section"><h3>Compilation route</h3><p><ShieldCheck size={15} /> {label(selected.enforcement)} · {label(selected.decidability)} · targets {selected.target_tools.join(", ") || "agent response"}</p></section>
          {selected.reviewer_note && <section className="drawer-section"><h3>Reviewer note</h3><p>{selected.reviewer_note}</p></section>}
          <section className="drawer-section"><h3>Linked tests</h3><div className="tags">{tests.data!.filter((test) => test.spec.rule_ids.includes(selected.stable_key)).map((test) => <span className="tag" key={test.id}>{test.title}</span>)}</div></section>
        </div>
        <div className="drawer-actions"><Button variant="danger" disabled={review.isPending || selected.status === "rejected"} onClick={() => review.mutate({ rule: selected, action: "reject" })}>Reject</Button><Button disabled={review.isPending || selected.status === "approved"} onClick={() => review.mutate({ rule: selected, action: "approve" })}><Check size={15} /> Approve revision</Button></div>
      </aside>
    </div>}
  </div>;
}
