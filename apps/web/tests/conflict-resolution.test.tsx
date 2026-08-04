import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConflictResolutionForm } from "@/features/conflict-resolution-form";
import type { Finding, Rule } from "@/lib/types";

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
});
