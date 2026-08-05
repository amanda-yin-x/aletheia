"use client";

import Link from "next/link";
import { AlertTriangle, CheckCircle2, Pencil, RefreshCw, Route, ShieldAlert, X } from "lucide-react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Badge, Button, EmptyState, ErrorState, PageLoading, PageTitle, StatCard } from "@/components/ui";
import {
  destinationLabel,
  dispositionLabel,
  dispositionTone,
  latestPlacementsByRule,
  PLACEMENT_DESTINATIONS,
  transformLabel,
} from "@/lib/compilation-presentation";
import { api, label, RequestError } from "@/lib/api";
import { authorityTone, documentPresentation, metadataLabel } from "@/lib/document-presentation";
import type {
  Document,
  PlacementDecision,
  PlacementDestination,
  PlacementDisposition,
  PlacementReviewStatus,
  PlacementTransformKind,
  Rule,
} from "@/lib/types";

const transformKinds: PlacementTransformKind[] = [
  "verbatim",
  "reviewed_normalization",
  "reviewer_authored_guidance",
  "compiler_scaffold",
];
const dispositions: PlacementDisposition[] = ["routed", "blocked", "unsupported", "retired"];

function PlacementEditor({
  decision,
  rule,
  onClose,
  onSaved,
  onRefresh,
}: {
  decision: PlacementDecision;
  rule: Rule;
  onClose: () => void;
  onSaved: (value: PlacementDecision) => void;
  onRefresh: () => Promise<unknown>;
}) {
  const [destinations, setDestinations] = useState<PlacementDestination[]>(decision.destinations);
  const [disposition, setDisposition] = useState<PlacementDisposition>(decision.disposition);
  const [transformKind, setTransformKind] = useState<PlacementTransformKind>(decision.transform_kind);
  const [reviewStatus, setReviewStatus] = useState<PlacementReviewStatus>(decision.review_status);
  const [reviewer, setReviewer] = useState(decision.reviewer);
  const [rationale, setRationale] = useState(decision.rationale);
  const [validationError, setValidationError] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: () => api<PlacementDecision>(`/api/v1/placement-decisions/${encodeURIComponent(decision.id)}`, {
      method: "PATCH",
      body: JSON.stringify({
        expected_version: decision.version,
        destinations,
        disposition,
        transform_kind: transformKind,
        review_status: reviewStatus,
        reviewer: reviewer.trim(),
        rationale: rationale.trim(),
      }),
    }),
    onSuccess: onSaved,
  });
  const dirty = disposition !== decision.disposition
    || transformKind !== decision.transform_kind
    || reviewStatus !== decision.review_status
    || reviewer.trim() !== decision.reviewer
    || rationale.trim() !== decision.rationale
    || destinations.join("|") !== decision.destinations.join("|");
  const versionConflict = mutation.error instanceof RequestError
    && (mutation.error.status === 409 || mutation.error.payload.code === "placement_version_conflict");

  function toggleDestination(destination: PlacementDestination, checked: boolean) {
    setValidationError(null);
    if (destination === "unsupported" && checked) {
      setDestinations(["unsupported"]);
      setDisposition("unsupported");
      return;
    }
    setDestinations((current) => {
      const withoutUnsupported = current.filter((item) => item !== "unsupported");
      if (checked) return [...withoutUnsupported.filter((item) => item !== destination), destination];
      return withoutUnsupported.filter((item) => item !== destination);
    });
    if (disposition === "unsupported") setDisposition("routed");
  }

  function changeDisposition(value: PlacementDisposition) {
    setValidationError(null);
    setDisposition(value);
    if (value === "unsupported") setDestinations(["unsupported"]);
    else setDestinations((current) => current.filter((item) => item !== "unsupported"));
  }

  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!destinations.length) {
      setValidationError("Select at least one explicit destination.");
      return;
    }
    if (!reviewer.trim() || !rationale.trim()) {
      setValidationError("Reviewer and rationale are required for a placement revision.");
      return;
    }
    if (disposition === "unsupported" && !destinations.includes("unsupported")) {
      setValidationError("An unsupported disposition must use the Unsupported destination.");
      return;
    }
    mutation.mutate();
  }

  return <div className="drawer-backdrop placement-drawer-backdrop" role="presentation">
    <aside className="drawer placement-drawer" role="dialog" aria-modal="true" aria-labelledby="placement-editor-title">
      <form onSubmit={submit}>
        <div className="drawer-head">
          <div><span className="eyebrow">Reviewed placement · version {decision.version}</span><h2 id="placement-editor-title">{rule.title}</h2></div>
          <button className="icon-button" type="button" aria-label="Close placement editor" onClick={onClose}><X size={17} /></button>
        </div>
        <div className="drawer-body">
          <section className="drawer-section">
            <h3>Rule revision</h3>
            <blockquote className="quote">{rule.normative_text}</blockquote>
            <p className="placement-editor-meta"><code>{rule.stable_key}@{rule.revision}</code> · profile {decision.profile_name} {decision.profile_version}{decision.scope_slug ? ` · scope ${decision.scope_slug}` : ""}</p>
          </section>
          <fieldset className="placement-destinations">
            <legend>Explicit destinations</legend>
            {PLACEMENT_DESTINATIONS.map((destination) => <label key={destination} className={destinations.includes(destination) ? "selected" : undefined}>
              <input
                type="checkbox"
                checked={destinations.includes(destination)}
                onChange={(event) => toggleDestination(destination, event.target.checked)}
              />
              <span>{destinationLabel(destination)}</span>
            </label>)}
          </fieldset>
          <div className="placement-form-grid">
            <div className="field"><label htmlFor="placement-disposition">Disposition</label><select id="placement-disposition" value={disposition} onChange={(event) => changeDisposition(event.target.value as PlacementDisposition)}>{dispositions.map((value) => <option key={value} value={value}>{dispositionLabel(value)}</option>)}</select></div>
            <div className="field"><label htmlFor="placement-transform">Transform kind</label><select id="placement-transform" value={transformKind} onChange={(event) => setTransformKind(event.target.value as PlacementTransformKind)}>{transformKinds.map((value) => <option key={value} value={value}>{transformLabel(value)}</option>)}</select></div>
            <div className="field"><label htmlFor="placement-review-status">Review status</label><select id="placement-review-status" value={reviewStatus} onChange={(event) => setReviewStatus(event.target.value as PlacementReviewStatus)}><option value="approved">Approved</option><option value="needs_review">Needs review</option></select></div>
            <div className="field"><label htmlFor="placement-reviewer">Reviewer</label><input id="placement-reviewer" required maxLength={200} value={reviewer} onChange={(event) => setReviewer(event.target.value)} /></div>
          </div>
          <div className="field placement-rationale"><label htmlFor="placement-rationale">Rationale</label><textarea id="placement-rationale" required maxLength={5000} value={rationale} onChange={(event) => setRationale(event.target.value)} /></div>
          {decision.rendering && <section className="drawer-section placement-rendering"><h3>Reviewed rendering</h3><pre>{decision.rendering}</pre><small>This versioned rendering is shown read-only in this editor.</small></section>}
          {validationError && <p className="conflict-form-error" role="alert">{validationError}</p>}
          {mutation.error && <div className="placement-save-error" role="alert">
            <strong>{versionConflict ? "This placement has a newer version." : "Placement revision could not be stored."}</strong>
            <p>{mutation.error instanceof Error ? mutation.error.message : "Try again after reviewing the current placement."}</p>
            {versionConflict && <Button type="button" variant="secondary" onClick={() => void onRefresh()}><RefreshCw size={14} /> Refresh current version</Button>}
          </div>}
        </div>
        <div className="drawer-actions"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button type="submit" disabled={!dirty || mutation.isPending}>{mutation.isPending ? "Saving revision…" : `Save as version ${decision.version + 1}`}</Button></div>
      </form>
    </aside>
  </div>;
}

function sourceAuthority(rule: Rule, documents: Document[], projectId: string) {
  if (!rule.source_refs.length) return <span className="placement-source-empty">No source anchor is declared for this rule revision.</span>;
  return <div className="placement-source-list">{rule.source_refs.map((reference, index) => {
    const document = documents.find((item) => item.id === reference.document_id);
    const metadata = documentPresentation(document);
    const lineLabel = reference.line_start === reference.line_end ? `line ${reference.line_start}` : `lines ${reference.line_start}–${reference.line_end}`;
    return <div key={`${reference.document_id}:${reference.line_start}:${index}`}>
      <Link href={`/projects/${encodeURIComponent(projectId)}/sources?document=${encodeURIComponent(reference.document_id)}#line-${reference.line_start}`}>{reference.document_name} · {lineLabel}</Link>
      <Badge tone={authorityTone(metadata.authorityStatus)}>{metadata.authorityStatus ? metadataLabel(metadata.authorityStatus) : "Authority unavailable"}</Badge>
      {metadata.owner && <small>{metadata.owner}</small>}
    </div>;
  })}</div>;
}

export function PlacementWorkbench({ projectId }: { projectId: string }) {
  const client = useQueryClient();
  const rules = useQuery({ queryKey: ["rules", projectId], queryFn: () => api<Rule[]>(`/api/v1/projects/${projectId}/rules`) });
  const placements = useQuery({ queryKey: ["placement-decisions", projectId], queryFn: () => api<PlacementDecision[]>(`/api/v1/projects/${projectId}/placement-decisions`) });
  const documents = useQuery({ queryKey: ["documents", projectId], queryFn: () => api<Document[]>(`/api/v1/projects/${projectId}/documents`) });
  const [selectedRuleId, setSelectedRuleId] = useState<string | null>(null);
  const [saved, setSaved] = useState<PlacementDecision | null>(null);
  const latest = useMemo(() => latestPlacementsByRule(placements.data || []), [placements.data]);
  const selectedRule = rules.data?.find((rule) => rule.id === selectedRuleId);
  const selectedDecision = selectedRule ? latest.get(selectedRule.id) : undefined;

  if (rules.isLoading || placements.isLoading || documents.isLoading) return <PageLoading label="Loading routing decisions" detail="Reading active rules, placement versions, and source authority…" />;
  if (rules.error || placements.error || documents.error) return <ErrorState error={rules.error || placements.error || documents.error} onRetry={() => { void rules.refetch(); void placements.refetch(); void documents.refetch(); }} />;

  const activeRules = rules.data || [];
  const decisions = activeRules.map((rule) => latest.get(rule.id));
  const routed = decisions.filter((decision) => decision?.disposition === "routed").length;
  const pending = decisions.filter((decision) => !decision || decision.review_status === "needs_review" || decision.disposition === "blocked").length;
  const unsupported = decisions.filter((decision) => decision?.disposition === "unsupported").length;
  const humanReview = decisions.filter((decision) => decision?.destinations.includes("human_review")).length;

  async function refreshPlacements() {
    await placements.refetch();
  }

  async function savedPlacement(value: PlacementDecision) {
    client.setQueryData<PlacementDecision[]>(["placement-decisions", projectId], (current) => [...(current || []), value]);
    setSaved(value);
    setSelectedRuleId(null);
    await Promise.all([
      client.invalidateQueries({ queryKey: ["placement-decisions", projectId] }),
      client.invalidateQueries({ queryKey: ["builds", projectId] }),
      client.invalidateQueries({ queryKey: ["summary", projectId] }),
    ]);
  }

  return <div className="content-wrap">
    <PageTitle eyebrow="Explicit compiler routing" title="Placements" detail="Every active rule needs a reviewed disposition. Placement revisions are stored independently from compiled snapshots." />
    {saved && <div className="placement-saved" role="status"><CheckCircle2 size={16} /><span><strong>{saved.rule_id}</strong> placement version {saved.version} was stored. Build a new snapshot to compile it.</span></div>}
    <div className="stat-grid placement-stat-grid">
      <StatCard label="Active rules" value={activeRules.length} note="All non-superseded revisions" />
      <StatCard label="Routed" value={routed} note="Explicit routed disposition" tone="teal" />
      <StatCard label="Needs attention" value={pending} note="Unrouted, blocked, or unreviewed" tone={pending ? "amber" : undefined} />
      <StatCard label="Unsupported / human" value={`${unsupported} / ${humanReview}`} note="Kept visible outside automatic enforcement" tone={unsupported ? "red" : undefined} />
    </div>
    {!activeRules.length ? <EmptyState title="No active rules" detail="This project has no non-superseded rule revisions to place." /> : <section className="placement-list" aria-label="Active rule placements">
      {activeRules.map((rule) => {
        const decision = latest.get(rule.id);
        const needsAttention = !decision || decision.review_status === "needs_review" || decision.disposition !== "routed";
        return <article className={`placement-card ${needsAttention ? "needs-attention" : ""}`} key={rule.id}>
          <div className="placement-card-main">
            <div className="placement-card-heading">
              <div><span className="placement-rule-key">{rule.stable_key}@{rule.revision}</span><h2>{rule.title}</h2></div>
              <div className="placement-card-badges"><Badge tone={rule.status === "approved" ? "teal" : "amber"}>{label(rule.status)}</Badge><Badge tone={rule.severity === "critical" ? "red" : rule.severity === "high" ? "amber" : "neutral"}>{label(rule.severity)}</Badge></div>
            </div>
            <p className="placement-rule-text">{rule.normative_text}</p>
            <div className="placement-source-authority"><strong>Source authority</strong>{sourceAuthority(rule, documents.data || [], projectId)}</div>
          </div>
          <div className="placement-card-decision">
            {!decision ? <div className="placement-unrouted"><ShieldAlert size={18} /><strong>Placement missing</strong><p>This active rule is unrouted, so compilation must stop.</p></div> : <>
              <div className="placement-decision-head"><Badge tone={dispositionTone(decision.disposition)}>{dispositionLabel(decision.disposition)}</Badge><span>v{decision.version} · {decision.review_status === "approved" ? "Reviewed" : "Needs review"}</span></div>
              <dl className="placement-decision-details">
                <div><dt>Transform</dt><dd>{transformLabel(decision.transform_kind)}</dd></div>
                <div><dt>Reviewer</dt><dd>{decision.reviewer}</dd></div>
                <div><dt>Profile</dt><dd>{decision.profile_name} {decision.profile_version}</dd></div>
                <div><dt>Scope</dt><dd>{decision.scope_slug || "Project default"}</dd></div>
              </dl>
              <div className="placement-destination-list" aria-label={`Destinations for ${rule.title}`}>{decision.destinations.map((destination) => <Badge key={destination} tone={destination === "unsupported" ? "red" : destination === "human_review" ? "amber" : "blue"}>{destinationLabel(destination)}</Badge>)}</div>
              <div className="placement-rationale-copy"><strong>Rationale</strong><p>{decision.rationale}</p></div>
              {decision.rendering && <details className="placement-rendering-summary"><summary>Reviewed rendering</summary><pre>{decision.rendering}</pre></details>}
              <Button variant="secondary" onClick={() => { setSaved(null); setSelectedRuleId(rule.id); }}><Pencil size={14} /> Review placement</Button>
            </>}
          </div>
        </article>;
      })}
    </section>}
    <section className="placement-boundary" aria-label="Routing evidence boundary"><AlertTriangle size={17} /><div><strong>Placement is a reviewed compiler input.</strong><p>It records where a clause is routed or why it is blocked. Behavioral fidelity remains not measured.</p></div><Link href={`/projects/${encodeURIComponent(projectId)}/build`}><Route size={14} /> Inspect compiled snapshot</Link></section>
    {selectedRule && selectedDecision && <PlacementEditor
      key={selectedDecision.id}
      decision={selectedDecision}
      rule={selectedRule}
      onClose={() => setSelectedRuleId(null)}
      onSaved={(value) => void savedPlacement(value)}
      onRefresh={refreshPlacements}
    />}
  </div>;
}
