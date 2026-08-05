import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ConflictResolutionForm } from "@/features/conflict-resolution-form";
import type { Document, Finding, Rule } from "@/lib/types";

const finding: Finding = {
  id: "finding-1",
  project_id: "project-1",
  type: "contradiction",
  severity: "critical",
  related_rule_ids: ["rule-current", "rule-legacy"],
  proof_status: "proved",
  message: "Refund windows conflict.",
  witness: {},
  resolution_state: "open",
  resolution_note: "",
};

function rule(id: string, revision: number, documentName: string, quote: string): Rule {
  return {
    id,
    project_id: "project-1",
    stable_key: `refund.window.${revision}`,
    revision,
    title: `Refund window revision ${revision}`,
    normative_text: `Refunds are available for ${revision === 3 ? 30 : 60} days.`,
    category: "refunds",
    effect: "allow",
    severity: "critical",
    status: "needs_review",
    confidence: 1,
    scope: {},
    condition: {},
    enforcement: "guard",
    decidability: "deterministic",
    source_refs: [{ document_id: `document-${revision}`, document_name: documentName, line_start: 10, line_end: 10, quote, source_sha256: "sha" }],
    target_tools: ["issue_refund"],
    reviewer_note: "",
  };
}

const relatedRules = [
  rule("rule-current", 3, "Refund Policy v3", "Refund requests must be submitted within 30 days."),
  rule("rule-legacy", 2, "Legacy Refund Guide", "Refund requests may be submitted within 60 days."),
];

const documents: Document[] = [
  {
    id: "document-3",
    project_id: "project-1",
    kind: "current_policy",
    name: "Refund Policy v3",
    version: 3,
    version_label: "Policy v3",
    original_sha256: "a".repeat(64),
    normalized_sha256: "b".repeat(64),
    normalized_text: "Refund requests must be submitted within 30 days.",
    mime_type: "text/markdown",
    line_count: 1,
    token_estimate: 10,
    origin: {},
    owner: "Policy Operations",
    authority_status: "current",
    effective_at: "2026-07-12T00:00:00Z",
    created_at: "2026-07-12T00:00:00Z",
  },
  {
    id: "document-2",
    project_id: "project-1",
    kind: "stale_sop",
    name: "Legacy Refund Guide",
    version: 2,
    version_label: "Legacy v2",
    original_sha256: "c".repeat(64),
    normalized_sha256: "d".repeat(64),
    normalized_text: "Refund requests may be submitted within 60 days.",
    mime_type: "text/markdown",
    line_count: 1,
    token_estimate: 10,
    origin: {},
    owner: "Support Operations",
    authority_status: "superseded",
    effective_at: "2024-01-01T00:00:00Z",
    created_at: "2024-01-01T00:00:00Z",
  },
];

afterEach(cleanup);

describe("conflict resolution review", () => {
  it("requires an explicit source-linked winner, authority, and rationale", () => {
    const onSubmit = vi.fn();
    render(<ConflictResolutionForm finding={finding} relatedRules={relatedRules} isPending={false} onCancel={vi.fn()} onSubmit={onSubmit} />);

    expect(screen.getByText("Refund requests must be submitted within 30 days.")).toBeInTheDocument();
    expect(screen.getByText("Refund requests may be submitted within 60 days.")).toBeInTheDocument();
    expect(screen.getAllByRole("radio")[0]).toHaveFocus();
    const save = screen.getByRole("button", { name: "Save resolution" });
    expect(save).toBeDisabled();

    fireEvent.click(screen.getByRole("radio", { name: /Legacy Refund Guide · revision 2/i }));
    fireEvent.change(screen.getByLabelText("Decision authority"), { target: { value: "Policy Operations approval dated July 12" } });
    fireEvent.change(screen.getByLabelText("Resolution rationale"), { target: { value: "The approved exception extends this release scope to 60 days." } });
    expect(save).toBeEnabled();
    fireEvent.click(save);

    expect(onSubmit).toHaveBeenCalledWith({
      findingId: "finding-1",
      expectedResolutionState: "open",
      winnerRuleId: "rule-legacy",
      loserRuleId: "rule-current",
      authority: "Policy Operations approval dated July 12",
      rationale: "The approved exception extends this release scope to 60 days.",
    });
  });

  it("shows source authority, witness context, exact line links, and the winner/loser consequence", () => {
    render(<ConflictResolutionForm
      finding={{ ...finding, witness: { current_window_days: 30, legacy_window_days: 60 } }}
      relatedRules={relatedRules}
      documents={documents}
      projectId="project-1"
      isPending={false}
      onCancel={vi.fn()}
      onSubmit={vi.fn()}
    />);

    expect(screen.getByRole("group", { name: "Conflict witness context" })).toHaveTextContent("Current Window Days30");
    const current = screen.getByRole("radio", { name: /Refund Policy v3 · Policy v3 · revision 3/i });
    const legacy = screen.getByRole("radio", { name: /Legacy Refund Guide · Legacy v2 · revision 2/i });
    expect(within(current.closest("label")!).getByText("Policy Operations", { exact: false })).toBeInTheDocument();
    expect(within(legacy.closest("label")!).getByText("Superseded")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open Refund Policy v3, exact lines 10–10/i })).toHaveAttribute(
      "href",
      "/projects/project-1/sources?document=document-3#line-10",
    );

    fireEvent.click(current);
    expect(within(current.closest("label")!).getByText("Winner")).toBeInTheDocument();
    expect(within(legacy.closest("label")!).getByText("Loser")).toBeInTheDocument();
    expect(document.querySelector(".conflict-decision-summary")).toHaveTextContent("WinnerRefund window revision 3");
  });
});
