import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Rule } from "@/lib/types";

const apiMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useParams: () => ({ projectId: "project-1" }),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: apiMock };
});

import RulesPage from "@/app/projects/[projectId]/rules/page";

const rule: Rule = {
  id: "rule-1",
  project_id: "project-1",
  stable_key: "rule.refund.approval_threshold",
  revision: 1,
  title: "Approval threshold",
  normative_text: "Refunds over $200 require approval.",
  category: "refund",
  effect: "require_approval",
  severity: "critical",
  status: "needs_review",
  confidence: 1,
  scope: {},
  condition: { kind: "predicate", fact: "order.total", op: "gt", value: 200 },
  enforcement: "guard",
  decidability: "deterministic",
  source_refs: [{
    document_id: "document-1",
    document_name: "Refund Policy v3",
    line_start: 12,
    line_end: 12,
    quote: "Approval is required above $200.",
    source_sha256: "sha",
  }],
  target_tools: ["issue_refund"],
  reviewer_note: "",
};

describe("rule mutation feedback", () => {
  it("surfaces failed condition saves and review decisions in the drawer", async () => {
    apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.endsWith("/rules") && !init?.method) return [rule];
      if (path.endsWith("/findings")) return [];
      if (path.endsWith("/test-cases")) return [];
      if (path === "/api/v1/rules/rule-1" && init?.method === "PATCH") {
        throw new Error("Condition service unavailable.");
      }
      if (path === "/api/v1/rules/rule-1/approve") {
        throw new Error("Review service unavailable.");
      }
      throw new Error(`Unexpected API call: ${path}`);
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <RulesPage />
      </QueryClientProvider>,
    );

    const title = await screen.findByText("Approval threshold");
    fireEvent.click(title.closest("tr")!);
    fireEvent.change(screen.getByLabelText("Value for order.total"), { target: { value: "225" } });
    fireEvent.click(screen.getByRole("button", { name: "Save condition revision" }));
    expect(await screen.findByText("Condition service unavailable.")).toHaveAttribute("role", "alert");

    fireEvent.click(screen.getByRole("button", { name: "Approve revision" }));
    expect(await screen.findByText("Review service unavailable.")).toHaveAttribute("role", "alert");
  });
});
