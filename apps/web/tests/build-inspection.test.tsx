import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { BuildInspectionView } from "@/features/build-inspection";
import type { Build, BuildInspection, CompilationMetrics, Document, PreservationReport, RoutingReport, SourceAnchor } from "@/lib/types";

const documentRecord: Document = {
  id: "document-policy", project_id: "project-1", kind: "policy", name: "Scheduling Policy", version: 4, version_label: "Policy v4",
  original_sha256: "a".repeat(64), normalized_sha256: "b".repeat(64), normalized_text: "Header\nSource clause\n", mime_type: "text/markdown", line_count: 2, token_estimate: 5,
  owner: "Care Operations", authority_status: "current", origin: {}, created_at: "2026-08-01T00:00:00Z",
};

const anchor: SourceAnchor = {
  source_anchor_id: "c".repeat(64), document_key: "Scheduling Policy@4", document_name: "Scheduling Policy", document_version: 4, version_label: "Policy v4",
  authority_owner: "Care Operations", authority_status: "current", original_sha256: "a".repeat(64), normalized_sha256: "b".repeat(64),
  line_start: 2, line_end: 2, utf8_byte_start: 7, utf8_byte_end: 20, quote: "Source clause", quote_sha256: "d".repeat(64),
  parser: "checked_in_utf8", parser_version: "1.0.0", normalizer: "aletheia_text", normalizer_version: "1.0.0",
};

const metrics: CompilationMetrics = {
  schema_version: "1.0", estimator: { name: "char_div_4", version: "1.0.0" },
  baseline_always_loaded: { lines: 80, characters: 960, utf8_bytes: 960, estimated_tokens: 240 },
  compiled_kernel: { lines: 2, characters: 72, utf8_bytes: 72, estimated_tokens: 18 },
  skills: { "skills/change-review/SKILL.md": { lines: 12, characters: 320, utf8_bytes: 320, estimated_tokens: 80 } },
  knowledge: { "skills/change-review/references/policy.md": { lines: 8, characters: 160, utf8_bytes: 160, estimated_tokens: 40 } },
  machine_enforced: { "policies/tool-policy.json": { lines: 1, characters: 200, utf8_bytes: 200, estimated_tokens: 50 }, "tests/regression.yaml": { lines: 15, characters: 400, utf8_bytes: 400, estimated_tokens: 100 } },
  total_bundle_without_manifest: { lines: 100, characters: 3000, utf8_bytes: 3000, estimated_tokens: 750 },
  expected_per_task_context: { lines: 22, characters: 552, utf8_bytes: 552, estimated_tokens: 138, artifact_paths: ["prompt-kernel.md", "skills/change-review/SKILL.md"] },
  routing: { active_normative_clauses: 2, explicit_dispositions: 2, routing_coverage: 1, verified_source_anchor_coverage: 1, approved_preservation: 1, severity_weighted_approved_preservation: 1, high_critical_guard_and_test_placement: 1, blocked_count: 0, unsupported_count: 0, unrouted_count: 0, unresolved_count: 0 },
  protected_literals: [{ rule_key: "rule.change.verify@1", artifact_paths: ["prompt-kernel.md"], literals: [{ kind: "tool_name", value: "update_record" }], missing: [], preserved: true }],
  behavioral_fidelity: "not_measured", interpretation: "Deterministic routing, source-anchor verification, and literal checks are conformance evidence; they do not measure behavioral fidelity.",
};

const routing: RoutingReport = {
  schema_version: "1.0", profile: { name: "default", version: "1.0.0", sha256: "e".repeat(64) }, counts: { active: 2, routed: 2, blocked: 0, unsupported: 0 },
  entries: [{
    rule_key: "rule.change.verify@1", rule_stable_key: "rule.change.verify", rule_revision: 1, title: "Verify requested changes", rule_status: "approved", severity: "critical", category: "hard_constraint",
    provenance_kind: "source_anchored", provenance_metadata: {}, verified_source_anchors: 1, source_anchors: [anchor], destinations: ["prompt_kernel", "pre_tool_policy", "test"], disposition: "routed", rationale: "Keep the invariant visible and machine enforced.",
    placement: { placement_key: "rule.change.verify@1:placement:2", rule_key: "rule.change.verify@1", rule_stable_key: "rule.change.verify", rule_revision: 1, version: 2, profile_name: "default", profile_version: "1.0.0", destinations: ["prompt_kernel", "pre_tool_policy", "test"], scope_slug: "change-review", rendering: null, transform_kind: "reviewed_normalization", disposition: "routed", rationale: "Keep the invariant visible and machine enforced.", review_status: "approved", reviewer: "Release Reviewer" },
  }, {
    rule_key: "rule.guidance@1", rule_stable_key: "rule.guidance", rule_revision: 1, title: "Escalation context", rule_status: "approved", severity: "medium", category: "handoff",
    provenance_kind: "reviewer_authored_guidance", provenance_metadata: { reviewer: "Policy Lead", rationale: "Clarifies the reviewed handoff boundary.", reviewed_at: "2026-08-02T10:00:00Z" }, verified_source_anchors: 0, source_anchors: [], destinations: ["knowledge", "human_review"], disposition: "routed", rationale: "Route reviewed handoff context to the scoped reference.",
    placement: { placement_key: "rule.guidance@1:placement:1", rule_key: "rule.guidance@1", rule_stable_key: "rule.guidance", rule_revision: 1, version: 1, profile_name: "default", profile_version: "1.0.0", destinations: ["knowledge", "human_review"], scope_slug: "change-review", rendering: "Escalate ambiguous cases to a policy owner.", transform_kind: "reviewer_authored_guidance", disposition: "routed", rationale: "Route reviewed handoff context to the scoped reference.", review_status: "approved", reviewer: "Policy Lead" },
  }],
};

const preservation: PreservationReport = {
  schema_version: "1.0", checks: [{ rule_key: "rule.change.verify@1", artifact_paths: ["prompt-kernel.md", "policies/tool-policy.json"], literals: [{ kind: "tool_name", value: "update_record" }], missing: [], preserved: true }],
  behavioral_fidelity: "not_measured", interpretation: "Exact rendering and protected-literal checks are deterministic conformance checks, not a behavioral-fidelity claim.",
};

const artifacts: Record<string, unknown> = {
  "manifest.json": "{\"schema_version\":\"1.0\"}\n",
  "prompt-kernel.md": "# Reviewed policy\nVerify the requested change before `update_record`.\n",
  "policies/tool-policy.json": "{\"tool\":\"update_record\"}\n",
  "routing-report.json": JSON.stringify(routing),
  "preservation-report.json": JSON.stringify(preservation),
  "compilation-metrics.json": JSON.stringify(metrics),
};

const build: Build = {
  id: "build-1", project_id: "project-1", status: "succeeded", input_manifest: {}, input_hash: "1".repeat(64), compiler_version: "1.0.0", artifacts, source_map: {},
  stats: { original: { lines: 80, characters: 960, tokens: 240 }, candidate: { lines: 2, characters: 72, tokens: 18 }, reduction: { lines: 78, characters: 888, estimated_tokens: 222, label: "char_div_4_v1" }, routing: { guarded: 1, tested: 1 }, compilation: metrics },
  content_hash: "2".repeat(64), created_at: "2026-08-02T12:00:00Z",
};

const inspection: BuildInspection = {
  build_id: build.id, project_id: build.project_id, status: "succeeded", input_hash: build.input_hash, compiler_version: build.compiler_version, content_hash: build.content_hash,
  artifacts: Object.keys(artifacts).map((path) => ({ path, sha256: path === "prompt-kernel.md" ? "3".repeat(64) : "4".repeat(64) })), source_map: {}, stats: { compilation: metrics },
  generated_spans: [
    { id: "span-scaffold", build_id: build.id, created_at: build.created_at, artifact_path: "prompt-kernel.md", artifact_sha256: "3".repeat(64), rule_id: null, rule_stable_key: null, rule_revision: null, placement_decision_id: null, placement_version: null, line_start: 1, line_end: 1, utf8_byte_start: 0, utf8_byte_end: 17, transform_kind: "compiler_scaffold", text_sha256: "5".repeat(64), source_refs: [] },
    { id: "span-rule", build_id: build.id, created_at: build.created_at, artifact_path: "prompt-kernel.md", artifact_sha256: "3".repeat(64), rule_id: "rule-1", rule_stable_key: "rule.change.verify", rule_revision: 1, placement_decision_id: "placement-2", placement_version: 2, line_start: 2, line_end: 2, utf8_byte_start: 18, utf8_byte_end: 72, transform_kind: "reviewed_normalization", text_sha256: "6".repeat(64), source_refs: [anchor] },
    { id: "span-guidance", build_id: build.id, created_at: build.created_at, artifact_path: "prompt-kernel.md", artifact_sha256: "3".repeat(64), rule_id: "rule-2", rule_stable_key: "rule.guidance", rule_revision: 1, placement_decision_id: "placement-guidance", placement_version: 1, line_start: 3, line_end: 3, utf8_byte_start: 72, utf8_byte_end: 72, transform_kind: "reviewer_authored_guidance", text_sha256: "7".repeat(64), source_refs: [] },
  ],
};

afterEach(cleanup);

describe("build inspection", () => {
  it("renders the bundle tree, exact metrics, routing and preservation contracts, and the honest evidence boundary", () => {
    const view = render(<BuildInspectionView projectId="project-1" build={build} inspection={inspection} documents={[documentRecord]} />);

    expect(screen.getByRole("navigation", { name: "Compiled bundle tree" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "prompt-kernel.md" })).toHaveAttribute("aria-current", "true");
    const baselineRow = screen.getByText("Baseline always-loaded").closest("tr")!;
    expect(within(baselineRow).getByText("80")).toBeInTheDocument();
    expect(within(baselineRow).getAllByText("960")).toHaveLength(2);
    expect(within(baselineRow).getByText("240")).toBeInTheDocument();
    expect(screen.getByText("char_div_4 · 1.0.0")).toBeInTheDocument();
    expect(screen.getByText("Behavioral fidelity: Not measured")).toBeInTheDocument();
    expect(screen.getByText("Verify requested changes")).toBeInTheDocument();
    expect(screen.queryByText("Routing report unavailable")).not.toBeInTheDocument();
    expect(screen.getByText("Reviewer attribution")).toBeInTheDocument();
    expect(screen.getByText("Policy Lead")).toBeInTheDocument();
    expect(screen.getByText(/Clarifies the reviewed handoff boundary/)).toBeInTheDocument();
    expect(screen.getByText("1 / 1 preserved")).toBeInTheDocument();
    expect(view.container).toHaveTextContent("conformance evidence");
    expect(screen.getByText("Compiler scaffold has no source-anchor claim.")).toBeInTheDocument();
  });

  it("clicks from an exact generated range through its pinned source anchor", () => {
    render(<BuildInspectionView projectId="project-1" build={build} inspection={inspection} documents={[documentRecord]} />);

    fireEvent.click(screen.getByRole("button", { name: "Inspect 1 source mapping for line 2" }));
    expect(screen.getByRole("heading", { name: "rule.change.verify@1" })).toBeInTheDocument();
    expect(screen.getByText("Source clause")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open exact source line 2" })).toHaveAttribute("href", "/projects/project-1/sources?document=document-policy#line-2");

    fireEvent.click(screen.getByRole("button", { name: /line 3 rule\.guidance@1/i }));
    expect(screen.getByText("Reviewer-authored guidance has no source-anchor claim. Reviewer attribution is pinned in the routing report below.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "routing-report.json" }));
    expect(screen.getByText("No generated span is recorded for this artifact.")).toBeInTheDocument();
  });
});
