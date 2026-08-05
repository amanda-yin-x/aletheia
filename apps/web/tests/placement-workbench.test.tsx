import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PlacementWorkbench } from "@/features/placement-workbench";
import { RequestError } from "@/lib/api";
import type { Document, PlacementDecision, Rule } from "@/lib/types";

const apiMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: apiMock };
});

const documents: Document[] = [
  {
    id: "document-current", project_id: "project-1", kind: "policy", name: "Scheduling Policy", version: 4, version_label: "Policy v4",
    original_sha256: "a".repeat(64), normalized_sha256: "b".repeat(64), normalized_text: "Current source", mime_type: "text/markdown", line_count: 8, token_estimate: 3,
    owner: "Care Operations", authority_status: "current", origin: {}, created_at: "2026-08-01T00:00:00Z",
  },
  {
    id: "document-legacy", project_id: "project-1", kind: "procedure", name: "Legacy Procedure", version: 2, version_label: "Procedure v2",
    original_sha256: "c".repeat(64), normalized_sha256: "d".repeat(64), normalized_text: "Legacy source", mime_type: "text/markdown", line_count: 12, token_estimate: 3,
    owner: "Service Operations", authority_status: "superseded", origin: {}, created_at: "2025-08-01T00:00:00Z",
  },
];

function rule(id: string, title: string, document: Document | null): Rule {
  return {
    id, project_id: "project-1", stable_key: `rule.${id}`, revision: 1, title,
    normative_text: `${title} must be reviewed before execution.`, category: "workflow", effect: "require", severity: id === "rule-a" ? "critical" : "high",
    status: "approved", confidence: 1, scope: {}, condition: {}, enforcement: "guard", decidability: "machine_decidable", target_tools: ["update_record"], reviewer_note: "",
    source_refs: document ? [{ document_id: document.id, document_name: document.name, line_start: 4, line_end: 5, quote: "Reviewed source text.", source_sha256: document.original_sha256 }] : [],
  };
}

const rules = [
  rule("rule-a", "Verify the requested change", documents[0]),
  rule("rule-b", "Escalate an unsupported exception", documents[1]),
  rule("rule-c", "Record downstream notification", null),
  { ...rule("rule-d", "Retain withdrawn language as historical evidence", documents[1]), status: "rejected" } satisfies Rule,
];

function placement(overrides: Partial<PlacementDecision> = {}): PlacementDecision {
  return {
    schema_version: "1.0", id: "placement-a-v2", project_id: "project-1", rule_id: "rule-a", version: 2,
    profile_name: "default", profile_version: "1.0.0", destinations: ["prompt_kernel", "pre_tool_policy", "test"], scope_slug: "change-review",
    rendering: null, transform_kind: "reviewed_normalization", disposition: "routed", rationale: "The clause is always visible and machine checked.", review_status: "approved", reviewer: "Reviewer Two",
    created_at: "2026-08-01T00:00:00Z", updated_at: "2026-08-01T00:00:00Z", ...overrides,
  };
}

const placements = [
  placement({ id: "placement-a-v1", version: 1, rationale: "Old rationale that must not render.", reviewer: "Reviewer One" }),
  placement(),
  placement({
    id: "placement-b-v1", rule_id: "rule-b", version: 1, destinations: ["unsupported", "human_review"], scope_slug: null,
    transform_kind: "verbatim", disposition: "unsupported", rationale: "The runtime cannot evaluate this exception deterministically.", review_status: "needs_review", reviewer: "Policy Owner",
  }),
  placement({
    id: "placement-d-v1", rule_id: "rule-d", version: 1, destinations: ["human_review"], scope_slug: null,
    transform_kind: "verbatim", disposition: "retired", rationale: "The superseded clause remains visible as losing authority evidence.", review_status: "approved", reviewer: "Policy Owner",
  }),
];

function renderWorkbench() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><PlacementWorkbench projectId="project-1" /></QueryClientProvider>);
}

beforeEach(() => {
  apiMock.mockReset().mockImplementation(async (path: string, init?: RequestInit) => {
    if (path.endsWith("/rules")) return rules;
    if (path.endsWith("/documents")) return documents;
    if (path.endsWith("/placement-decisions") && !init?.method) return placements;
    throw new Error(`Unexpected API call: ${path}`);
  });
});

afterEach(cleanup);

describe("placement workbench", () => {
  it("shows every ledger clause without treating reviewed retired history as attention", async () => {
    renderWorkbench();

    expect(await screen.findByText("Verify the requested change")).toBeInTheDocument();
    expect(screen.getByText("Escalate an unsupported exception")).toBeInTheDocument();
    expect(screen.getByText("Record downstream notification")).toBeInTheDocument();
    expect(screen.getByText("Reviewer Two")).toBeInTheDocument();
    expect(screen.queryByText("Old rationale that must not render.")).not.toBeInTheDocument();
    expect(screen.getAllByText("Current").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Superseded").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Unsupported").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Human review").length).toBeGreaterThan(0);
    expect(screen.getByText("Placement missing")).toBeInTheDocument();
    expect(screen.getByText("No source anchor is declared for this rule revision.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Scheduling Policy · lines 4–5/i })).toHaveAttribute("href", "/projects/project-1/sources?document=document-current#line-4");
    expect(screen.getByRole("region", { name: "Rule placement ledger" })).toBeInTheDocument();

    const ledgerStat = screen.getByText("Ledger clauses").closest(".stat-card")!;
    const routedStat = screen.getByText("Routed / retired").closest(".stat-card")!;
    const attentionStat = screen.getByText("Needs attention").closest(".stat-card")!;
    expect(ledgerStat).toHaveTextContent("4");
    expect(routedStat).toHaveTextContent("1 / 1");
    expect(attentionStat).toHaveTextContent("2");

    const retiredCard = screen.getByText("Retain withdrawn language as historical evidence").closest("article")!;
    expect(within(retiredCard).getByText("Rejected")).toBeInTheDocument();
    expect(within(retiredCard).getByText("Retired")).toBeInTheDocument();
    expect(retiredCard).toHaveClass("is-retired");
    expect(retiredCard).not.toHaveClass("needs-attention");
    expect(screen.queryByText(/active rules?/i)).not.toBeInTheDocument();
  });

  it("stores an edited placement against the visible version and appends the returned revision", async () => {
    const revised = placement({ id: "placement-a-v3", version: 3, reviewer: "Release Reviewer", updated_at: "2026-08-02T00:00:00Z" });
    apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.endsWith("/rules")) return rules;
      if (path.endsWith("/documents")) return documents;
      if (path.endsWith("/placement-decisions") && !init?.method) return placements;
      if (path === "/api/v1/placement-decisions/placement-a-v2" && init?.method === "PATCH") return revised;
      throw new Error(`Unexpected API call: ${path}`);
    });
    renderWorkbench();

    const article = (await screen.findByText("Verify the requested change")).closest("article")!;
    fireEvent.click(within(article).getByRole("button", { name: "Review placement" }));
    fireEvent.change(screen.getByLabelText("Reviewer"), { target: { value: "Release Reviewer" } });
    fireEvent.click(screen.getByRole("button", { name: "Save as version 3" }));

    await waitFor(() => expect(apiMock).toHaveBeenCalledWith(
      "/api/v1/placement-decisions/placement-a-v2",
      expect.objectContaining({ method: "PATCH" }),
    ));
    const patchCall = apiMock.mock.calls.find(([path, init]) => path === "/api/v1/placement-decisions/placement-a-v2" && init?.method === "PATCH")!;
    expect(JSON.parse(patchCall[1].body)).toEqual(expect.objectContaining({ expected_version: 2, reviewer: "Release Reviewer", disposition: "routed" }));
    expect(await screen.findByText(/placement version 3 was stored/i)).toBeInTheDocument();
  });

  it("surfaces an optimistic version conflict and offers an explicit refresh", async () => {
    apiMock.mockImplementation(async (path: string, init?: RequestInit) => {
      if (path.endsWith("/rules")) return rules;
      if (path.endsWith("/documents")) return documents;
      if (path.endsWith("/placement-decisions") && !init?.method) return placements;
      if (path === "/api/v1/placement-decisions/placement-a-v2" && init?.method === "PATCH") throw new RequestError({
        code: "placement_version_conflict",
        message: "This placement changed after you opened it. Refresh before reviewing it again.",
        details: { expected_version: 2, current_version: 3 },
        request_id: "request-conflict",
      }, 409);
      throw new Error(`Unexpected API call: ${path}`);
    });
    renderWorkbench();

    const article = (await screen.findByText("Verify the requested change")).closest("article")!;
    fireEvent.click(within(article).getByRole("button", { name: "Review placement" }));
    fireEvent.change(screen.getByLabelText("Reviewer"), { target: { value: "Another Reviewer" } });
    fireEvent.click(screen.getByRole("button", { name: "Save as version 3" }));

    expect(await screen.findByText("This placement has a newer version.")).toBeInTheDocument();
    expect(screen.getByText(/Refresh before reviewing it again/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh current version" }));
    await waitFor(() => expect(apiMock.mock.calls.filter(([path, init]) => path.endsWith("/placement-decisions") && !init?.method).length).toBeGreaterThan(1));
  });

  it("keeps keyboard focus inside the placement dialog and restores it on Escape", async () => {
    renderWorkbench();

    const article = (await screen.findByText("Verify the requested change")).closest("article")!;
    const trigger = within(article).getByRole("button", { name: "Review placement" });
    trigger.focus();
    fireEvent.click(trigger);

    const dialog = screen.getByRole("dialog", { name: "Verify the requested change" });
    await waitFor(() => expect(within(dialog).getByRole("button", { name: "Close placement editor" })).toHaveFocus());
    fireEvent.keyDown(document, { key: "Escape" });

    expect(screen.queryByRole("dialog", { name: "Verify the requested change" })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
