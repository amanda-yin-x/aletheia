"use client";

import { Check, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Badge, Button } from "@/components/ui";
import { authorityTone, documentPresentation, formattedEffectiveDate, metadataLabel } from "@/lib/document-presentation";
import type { Document, Finding, Rule } from "@/lib/types";

export interface ConflictResolutionDecision {
  findingId: string;
  expectedResolutionState: Finding["resolution_state"];
  winnerRuleId: string;
  loserRuleId: string;
  authority: string;
  rationale: string;
}

interface ConflictResolutionFormProps {
  finding: Finding;
  relatedRules: Rule[];
  documents?: Document[];
  projectId?: string;
  isPending: boolean;
  error?: unknown;
  onCancel: () => void;
  onSubmit: (decision: ConflictResolutionDecision) => void;
}

function witnessValue(value: unknown): string {
  if (value == null) return "Not provided";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
  try { return JSON.stringify(value); } catch { return "Unavailable"; }
}

function witnessLabel(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

export function ConflictResolutionForm({ finding, relatedRules, documents = [], projectId, isPending, error, onCancel, onSubmit }: ConflictResolutionFormProps) {
  const [winnerRuleId, setWinnerRuleId] = useState("");
  const [authority, setAuthority] = useState("");
  const [rationale, setRationale] = useState("");
  const isPairwiseConflict = relatedRules.length === 2;
  const canSubmit = isPairwiseConflict && Boolean(winnerRuleId && authority.trim() && rationale.trim()) && !isPending;
  const fieldPrefix = `conflict-${finding.id}`;
  const errorMessage = error instanceof Error ? error.message : error ? "The decision could not be saved. Refresh and try again." : "";
  const winner = relatedRules.find((rule) => rule.id === winnerRuleId);
  const loser = winnerRuleId ? relatedRules.find((rule) => rule.id !== winnerRuleId) : undefined;
  const witness = Object.entries(finding.witness || {}).filter(([key]) => key !== "resolution");

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const loser = relatedRules.find((rule) => rule.id !== winnerRuleId);
    if (!canSubmit || !loser) return;
    onSubmit({
      findingId: finding.id,
      expectedResolutionState: finding.resolution_state,
      winnerRuleId,
      loserRuleId: loser.id,
      authority: authority.trim(),
      rationale: rationale.trim(),
    });
  };

  return <form className="conflict-resolution-form" aria-label={`Resolve conflict: ${finding.message}`} onSubmit={submit}>
    <div className="conflict-resolution-head">
      <div>
        <span className="workspace-label">Reviewer decision</span>
        <h3>Which revision governs this release?</h3>
        <p>Select the authoritative revision, then record the authority and reasoning another reviewer can audit.</p>
      </div>
      <Badge tone="red">Build gate</Badge>
    </div>

    {witness.length > 0 && <div className="conflict-witness" role="group" aria-label="Conflict witness context">
      <strong>Relevant witness / context</strong>
      <dl>{witness.map(([key, value]) => <div key={key}><dt>{witnessLabel(key)}</dt><dd>{witnessValue(value)}</dd></div>)}</dl>
    </div>}

    <fieldset className="conflict-options" disabled={isPending || !isPairwiseConflict}>
      <legend>Select the authoritative rule revision</legend>
      {relatedRules.map((rule, index) => {
        const source = rule.source_refs[0];
        const selected = winnerRuleId === rule.id;
        const losing = Boolean(winnerRuleId && !selected);
        const sourceDocument = documents.find((document) => document.id === source?.document_id);
        const sourceMetadata = documentPresentation(sourceDocument);
        return <label className={`conflict-option ${selected ? "selected" : ""}`} key={rule.id}>
          <input
            type="radio"
            name={`${fieldPrefix}-winner`}
            value={rule.id}
            checked={selected}
            autoFocus={index === 0}
            onChange={() => setWinnerRuleId(rule.id)}
          />
          <span className="conflict-option-content">
            <span className="conflict-option-heading">
              <span>
                <strong>{rule.title}</strong>
                <small>{source?.document_name || "Source unavailable"} · {sourceDocument ? `${sourceMetadata.versionLabel} · ` : ""}revision {rule.revision}</small>
              </span>
              {selected ? <Badge tone="teal"><Check size={11} /> Winner</Badge> : losing ? <Badge tone="amber">Loser</Badge> : null}
            </span>
            <blockquote>{source?.quote || "No source quote is attached to this revision."}</blockquote>
            {source && projectId && <Link className="conflict-source-link" href={`/projects/${encodeURIComponent(projectId)}/sources?document=${encodeURIComponent(source.document_id)}#line-${source.line_start}`} onClick={(event) => event.stopPropagation()}>
              Open {source.document_name || "source"}, exact lines {source.line_start}–{source.line_end} <ExternalLink size={12} aria-hidden="true" />
            </Link>}
            {sourceDocument && <div className="conflict-source-authority" aria-label={`Authority metadata for ${sourceDocument.name}`}>
              <Badge tone={authorityTone(sourceMetadata.authorityStatus)}>{sourceMetadata.authorityStatus ? metadataLabel(sourceMetadata.authorityStatus) : "Authority unavailable"}</Badge>
              <span>Owner: {sourceMetadata.owner || "not provided"}</span>
              <span>Effective: {formattedEffectiveDate(sourceMetadata.effectiveAt)}</span>
            </div>}
            <span className="conflict-option-rule">Normalized as: {rule.normative_text}</span>
          </span>
        </label>;
      })}
    </fieldset>

    {!isPairwiseConflict && <p className="conflict-form-error" role="alert">This reviewer currently supports pairwise conflicts. Refresh the finding data or use an administrative review for {relatedRules.length} related revisions.</p>}

    {winner && loser && <div className="conflict-decision-summary" aria-live="polite">
      <span><strong>Winner</strong>{winner.title}</span>
      <span><strong>Loser</strong>{loser.title}</span>
    </div>}

    <div className="conflict-decision-fields">
      <div className="field">
        <label htmlFor={`${fieldPrefix}-authority`}>Decision authority</label>
        <input
          id={`${fieldPrefix}-authority`}
          value={authority}
          maxLength={500}
          placeholder="e.g. Current policy, approved by Policy Operations"
          disabled={isPending || !isPairwiseConflict}
          onChange={(event) => setAuthority(event.target.value)}
          aria-describedby={`${fieldPrefix}-authority-help`}
          required
        />
        <small id={`${fieldPrefix}-authority-help`}>Name the document, owner, or approval that makes this revision authoritative.</small>
      </div>
      <div className="field">
        <label htmlFor={`${fieldPrefix}-rationale`}>Resolution rationale</label>
        <textarea
          id={`${fieldPrefix}-rationale`}
          value={rationale}
          maxLength={5000}
          rows={3}
          placeholder="Explain why the selected revision applies and why the other revision is superseded."
          disabled={isPending || !isPairwiseConflict}
          onChange={(event) => setRationale(event.target.value)}
          aria-describedby={`${fieldPrefix}-rationale-help`}
          required
        />
        <small id={`${fieldPrefix}-rationale-help`}>This note is stored with the finding and retained in build provenance.</small>
      </div>
    </div>

    {errorMessage && <p className="conflict-form-error" role="alert">{errorMessage}</p>}

    <div className="conflict-form-actions">
      <Button type="button" variant="secondary" disabled={isPending} onClick={onCancel}>Cancel</Button>
      <Button type="submit" disabled={!canSubmit}>
        <Check size={15} /> {isPending ? "Saving decision…" : "Save resolution"}
      </Button>
    </div>
  </form>;
}
