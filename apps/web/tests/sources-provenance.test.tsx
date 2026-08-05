import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Document, Rule } from "@/lib/types";

const apiMock = vi.hoisted(() => vi.fn());
const searchParamsMock = vi.hoisted(() => new URLSearchParams("document=document-policy"));

vi.mock("next/navigation", () => ({
  useParams: () => ({ projectId: "project-1" }),
  useSearchParams: () => searchParamsMock,
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: apiMock };
});

import SourcesPage from "@/app/projects/[projectId]/sources/page";

const documentRecord: Document = {
  id: "document-policy",
  project_id: "project-1",
  kind: "current_policy",
  name: "Booking Policy v4",
  version: 4,
  version_label: "Policy v4",
  original_sha256: "a".repeat(64),
  normalized_sha256: "b".repeat(64),
  normalized_text: "Scheduling policy\nVerify identity before changing a booking.\nEnd.",
  mime_type: "text/markdown",
  line_count: 3,
  token_estimate: 14,
  owner: "Care Operations",
  authority_status: "current",
  effective_at: "2026-07-24T00:00:00Z",
  jurisdictions: ["US", "Canada"],
  scopes: ["booking changes"],
  parser: "checked_in_utf8",
  parser_version: "1.2.0",
  normalizer: "aletheia_text",
  normalizer_version: "1.1.0",
  origin: { type: "fixture_authored" },
  created_at: "2026-07-24T00:00:00Z",
};

const rule: Rule = {
  id: "rule-1",
  project_id: "project-1",
  stable_key: "rule.booking.identity",
  revision: 1,
  title: "Verify identity",
  normative_text: "Verify identity before changing a booking.",
  category: "hard_constraint",
  effect: "deny",
  severity: "critical",
  status: "approved",
  confidence: 1,
  scope: {},
  condition: {},
  enforcement: "guard",
  decidability: "machine_decidable",
  source_refs: [{
    document_id: documentRecord.id,
    document_name: documentRecord.name,
    line_start: 2,
    line_end: 2,
    quote: "Verify identity before changing a booking.",
    source_sha256: documentRecord.original_sha256,
  }],
  target_tools: ["reschedule_appointment"],
  reviewer_note: "",
};

beforeEach(() => {
  window.history.replaceState(null, "", "/projects/project-1/sources?document=document-policy#line-2");
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", { configurable: true, value: vi.fn() });
  apiMock.mockReset().mockImplementation(async (path: string) => {
    if (path.endsWith("/documents")) return [documentRecord];
    if (path.endsWith("/rules")) return [rule];
    if (path.endsWith("/findings")) return [];
    throw new Error(`Unexpected API call: ${path}`);
  });
});

afterEach(cleanup);

describe("source authority and provenance", () => {
  it("labels only supplied authority metadata, shows both hashes, and focuses an async deep-linked line", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><SourcesPage /></QueryClientProvider>);

    expect(await screen.findByText("Care Operations")).toBeInTheDocument();
    expect(screen.getByText("Jul 24, 2026")).toBeInTheDocument();
    expect(screen.getByText("US · Canada")).toBeInTheDocument();
    expect(screen.getByText("checked_in_utf8 · 1.2.0")).toBeInTheDocument();
    expect(screen.getByText("aletheia_text · 1.1.0")).toBeInTheDocument();
    expect(screen.getByLabelText("Document hashes")).toHaveTextContent("Original SHA-256 aaaaaaaa…aaaa");
    expect(screen.getByLabelText("Document hashes")).toHaveTextContent("Normalized SHA-256 bbbbbbbb…bbbb");

    const line = document.getElementById("line-2")!;
    await waitFor(() => expect(line).toHaveFocus());
    expect(line.scrollIntoView).toHaveBeenCalledWith({ block: "center", behavior: "auto" });
  });

  it("marks absent authority and normalized provenance as unavailable", async () => {
    const minimalDocument: Document = {
      ...documentRecord,
      normalized_sha256: null,
      owner: null,
      authority_status: null,
      effective_at: null,
      jurisdictions: null,
      scopes: null,
      parser: null,
      parser_version: null,
      normalizer: null,
      normalizer_version: null,
      origin: {},
    };
    apiMock.mockImplementation(async (path: string) => {
      if (path.endsWith("/documents")) return [minimalDocument];
      if (path.endsWith("/rules")) return [rule];
      if (path.endsWith("/findings")) return [];
      throw new Error(`Unexpected API call: ${path}`);
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><SourcesPage /></QueryClientProvider>);

    expect(await screen.findByText("Authority unavailable")).toBeInTheDocument();
    expect(screen.getByLabelText("Document hashes")).toHaveTextContent("Normalized SHA-256 Unavailable");
    expect(screen.getAllByText("Not provided")).toHaveLength(2);
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThanOrEqual(3);
  });
});
