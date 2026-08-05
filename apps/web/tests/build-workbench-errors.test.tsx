import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BuildWorkbench } from "@/features/build-workbench";
import type { Build, BuildInspection, Summary } from "@/lib/types";

const apiMock = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));
vi.mock("@/lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/lib/api")>();
  return { ...original, api: apiMock };
});

const build: Build = {
  id: "build-current", project_id: "project-1", status: "succeeded", input_manifest: {}, input_hash: "1".repeat(64), compiler_version: "1.0.0", artifacts: {}, source_map: {},
  stats: { original: { lines: 0, characters: 0, tokens: 0 }, candidate: { lines: 0, characters: 0, tokens: 0 }, reduction: { lines: 0, characters: 0, estimated_tokens: 0, label: "char_div_4_v1" }, routing: {} },
  content_hash: "2".repeat(64), created_at: "2026-08-02T12:00:00Z",
};
const summary: Summary = { sources: 0, approved_rules: 0, critical_findings: 0, tests: 0, current_build: build, last_run: null };
const inspection: BuildInspection = { build_id: build.id, project_id: build.project_id, status: "succeeded", input_hash: build.input_hash, compiler_version: build.compiler_version, content_hash: build.content_hash, artifacts: [], source_map: {}, stats: {}, generated_spans: [] };

function renderWorkbench(requestedBuildId?: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><BuildWorkbench projectId="project-1" requestedBuildId={requestedBuildId} /></QueryClientProvider>);
}

beforeEach(() => {
  apiMock.mockReset();
});

afterEach(cleanup);

describe("build workbench boundaries", () => {
  it("does not silently replace an unavailable requested snapshot with the latest build", async () => {
    apiMock.mockImplementation(async (path: string) => {
      if (path.endsWith("/builds")) return [build];
      if (path.endsWith("/summary")) return summary;
      if (path.endsWith("/documents")) return [];
      throw new Error(`Unexpected API call: ${path}`);
    });
    renderWorkbench("build-missing");

    expect(await screen.findByRole("heading", { name: "Build snapshot not found" })).toBeInTheDocument();
    expect(screen.getByText("Open the current build list instead of substituting a different snapshot.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open current build" })).toHaveAttribute("href", "/projects/project-1/build");
    expect(apiMock).not.toHaveBeenCalledWith("/api/v1/builds/build-current/inspection");
  });

  it("surfaces an inspection failure and retries the exact build", async () => {
    let inspectionAttempts = 0;
    apiMock.mockImplementation(async (path: string) => {
      if (path.endsWith("/builds")) return [build];
      if (path.endsWith("/summary")) return summary;
      if (path.endsWith("/documents")) return [];
      if (path === "/api/v1/builds/build-current/inspection") {
        inspectionAttempts += 1;
        if (inspectionAttempts === 1) throw new Error("Build inspection is temporarily unavailable.");
        return inspection;
      }
      throw new Error(`Unexpected API call: ${path}`);
    });
    renderWorkbench();

    expect(await screen.findByRole("alert")).toHaveTextContent("Build inspection is temporarily unavailable.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.getByRole("navigation", { name: "Compiled bundle tree" })).toBeInTheDocument());
    expect(inspectionAttempts).toBe(2);
  });
});
