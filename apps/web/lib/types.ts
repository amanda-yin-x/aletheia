export interface Project { id: string; workspace_id: string; slug: string; name: string; domain: string; description: string; mode: string; created_at: string }
export interface Workspace { id: string; slug: string; name: string; role: string; created_at: string }
export interface BootstrapResult { workspace: Workspace; project: Project; created: boolean; project_id?: string }
export interface Account { id: string; email: string | null; is_anonymous: boolean; workspaces: Workspace[] }
export type OperationStatus = "queued" | "running" | "succeeded" | "failed" | "dead_lettered" | "cancelled" | "canceled" | "expired" | "timed_out" | "stale" | "aborted" | (string & {});
export interface OperationErrorPayload { code: string; message: string }
export interface Operation {
  id: string;
  workspace_id?: string;
  kind: string;
  status: OperationStatus;
  progress: number;
  resource_type: string | null;
  resource_id: string | null;
  attempt_count: number;
  max_attempts?: number;
  error: OperationErrorPayload | null;
  created_at?: string;
  updated_at: string;
}
export interface Summary { sources: number; approved_rules: number; critical_findings: number; tests: number; current_build: Build | null; last_run: Run | null }
export interface SourceRef { document_id: string; document_name: string; line_start: number; line_end: number; quote: string; source_sha256: string }
export interface Document {
  id: string;
  project_id: string;
  kind: string;
  name: string;
  version: number;
  version_label?: string | null;
  original_sha256: string;
  normalized_sha256?: string | null;
  normalized_text: string;
  mime_type: string;
  line_count: number;
  token_estimate: number;
  origin: Record<string, unknown>;
  owner?: string | null;
  authority_owner?: string | null;
  authority_status?: string | null;
  effective_at?: string | null;
  jurisdictions?: string[] | null;
  scopes?: string[] | null;
  authority_scopes?: string[] | null;
  parser?: string | null;
  parser_version?: string | null;
  normalizer?: string | null;
  normalizer_version?: string | null;
  created_at: string;
}
export interface Rule { id: string; project_id: string; stable_key: string; revision: number; title: string; normative_text: string; category: string; effect: string; severity: string; status: string; confidence: number; scope: Record<string, unknown>; condition: Record<string, unknown>; enforcement: string; decidability: string; source_refs: SourceRef[]; target_tools: string[]; reviewer_note: string }
export type FindingResolutionState = "open" | "resolved" | "accepted_risk";
export interface Finding { id: string; project_id: string; type: string; severity: string; related_rule_ids: string[]; proof_status: string; message: string; witness: Record<string, unknown>; resolution_state: FindingResolutionState; resolution_note: string }
export type PlacementDestination = "prompt_kernel" | "skill" | "knowledge" | "pre_tool_policy" | "test" | "human_review" | "unsupported";
export type PlacementTransformKind = "verbatim" | "reviewed_normalization" | "reviewer_authored_guidance" | "compiler_scaffold";
export type PlacementDisposition = "routed" | "blocked" | "unsupported" | "retired";
export type PlacementReviewStatus = "approved" | "needs_review";
export type AuthorityStatus = "current" | "superseded" | "draft" | "reference";

export interface PlacementDecision {
  schema_version: "1.0";
  id: string;
  project_id: string;
  rule_id: string;
  version: number;
  profile_name: string;
  profile_version: string;
  destinations: PlacementDestination[];
  scope_slug: string | null;
  rendering: string | null;
  transform_kind: PlacementTransformKind;
  disposition: PlacementDisposition;
  rationale: string;
  review_status: PlacementReviewStatus;
  reviewer: string;
  created_at: string;
  updated_at: string;
}

export interface SourceAnchor {
  source_anchor_id: string;
  document_key: string;
  document_name: string;
  document_version: number;
  version_label: string;
  authority_owner: string;
  authority_status: AuthorityStatus;
  original_sha256: string;
  normalized_sha256: string;
  line_start: number;
  line_end: number;
  utf8_byte_start: number;
  utf8_byte_end: number;
  quote: string;
  quote_sha256: string;
  parser: string;
  parser_version: string;
  normalizer: string;
  normalizer_version: string;
}

export interface GeneratedSpan {
  id: string;
  build_id: string;
  created_at: string;
  artifact_path: string;
  artifact_sha256: string;
  rule_id: string | null;
  rule_stable_key: string | null;
  rule_revision: number | null;
  placement_decision_id: string | null;
  placement_version: number | null;
  line_start: number;
  line_end: number;
  utf8_byte_start: number;
  utf8_byte_end: number;
  transform_kind: PlacementTransformKind;
  text_sha256: string;
  source_refs: SourceAnchor[];
}

export interface BuildInspection {
  build_id: string;
  project_id: string;
  status: string;
  input_hash: string;
  compiler_version: string;
  content_hash: string;
  artifacts: Array<{ path: string; sha256: string }>;
  source_map: Record<string, unknown>;
  stats: Record<string, unknown>;
  generated_spans: GeneratedSpan[];
}

export interface ContentSizeMetric {
  lines: number;
  characters: number;
  utf8_bytes: number;
  estimated_tokens: number;
}

export interface PreservationCheck {
  rule_key: string;
  artifact_paths: string[];
  literals: Array<{ kind: string; value: string }>;
  missing: Array<{ kind: string; value: string }>;
  preserved: boolean;
}

export interface PreservationReport {
  schema_version: "1.0";
  checks: PreservationCheck[];
  behavioral_fidelity: "not_measured";
  interpretation: string;
}

export interface RoutingReportEntry {
  rule_key: string;
  rule_stable_key: string;
  rule_revision: number;
  title: string;
  rule_status: string;
  severity: string;
  category: string;
  provenance_kind: "source_anchored" | "reviewer_authored_guidance";
  provenance_metadata?: {
    reviewer?: string | null;
    rationale?: string | null;
    reviewed_at?: string | null;
  };
  verified_source_anchors: number;
  source_anchors: SourceAnchor[];
  placement: {
    placement_key: string;
    rule_key: string;
    rule_stable_key: string;
    rule_revision: number;
    version: number;
    profile_name: string;
    profile_version: string;
    destinations: PlacementDestination[];
    scope_slug: string | null;
    rendering: string | null;
    transform_kind: PlacementTransformKind;
    disposition: PlacementDisposition;
    rationale: string;
    review_status: PlacementReviewStatus;
    reviewer: string;
  };
  destinations: PlacementDestination[];
  disposition: PlacementDisposition;
  rationale: string;
}

export interface RoutingReport {
  schema_version: "1.0";
  profile: { name: string; version: string; sha256: string };
  entries: RoutingReportEntry[];
  counts: { active: number; routed: number; blocked: number; unsupported: number };
}

export interface CompilationMetrics {
  schema_version: "1.0";
  estimator: { name: string; version: string };
  baseline_always_loaded: ContentSizeMetric;
  compiled_kernel: ContentSizeMetric;
  skills: Record<string, ContentSizeMetric>;
  knowledge: Record<string, ContentSizeMetric>;
  machine_enforced: Record<string, ContentSizeMetric>;
  total_bundle_without_manifest: ContentSizeMetric;
  expected_per_task_context: ContentSizeMetric & { artifact_paths: string[] };
  routing: {
    active_normative_clauses: number;
    explicit_dispositions: number;
    routing_coverage: number;
    verified_source_anchor_coverage: number;
    approved_preservation: number;
    severity_weighted_approved_preservation: number;
    high_critical_guard_and_test_placement: number;
    blocked_count: number;
    unsupported_count: number;
    unrouted_count: number;
    unresolved_count: number;
  };
  protected_literals: PreservationCheck[];
  behavioral_fidelity: "not_measured";
  interpretation: string;
}

interface LegacyBuildStat { lines: number; characters: number; tokens: number }
export interface Build {
  id: string;
  project_id: string;
  status: string;
  input_manifest: Record<string, unknown>;
  input_hash: string;
  compiler_version: string;
  artifacts: Record<string, unknown>;
  source_map: Record<string, unknown>;
  stats: {
    original: LegacyBuildStat;
    candidate: LegacyBuildStat;
    reduction: { lines: number; characters: number; estimated_tokens: number; label: string };
    routing: Record<string, number>;
    compilation?: CompilationMetrics;
  };
  content_hash: string;
  created_at: string;
}
export interface TestCase { id: string; project_id: string; stable_key: string; title: string; provenance: string; spec: { rule_ids: string[]; tags: string[]; expected: Record<string, unknown>; initial_state: Record<string, unknown> }; review_status: string }
export interface TestSnapshot { stable_key: string; title: string; rule_ids: string[]; tags: string[]; provenance: string; spec_digest?: string }
export interface ArmMetrics { cases: number; task_success_rate: number; attempted_violation_rate: number; executed_violation_rate: number; false_block_rate: number; tool_validation_error_rate: number; input_tokens: number | null; output_tokens: number | null; cost: number | null }
export interface Run { id: string; project_id: string; build_id: string; requested_arms: string[]; adapter: string; model: string | null; dataset_manifest: { name: string; version: string; data_scope: string; test_count: number; hash: string; [key: string]: unknown }; status: OperationStatus; metrics: Record<string, ArmMetrics | Record<string, unknown>>; started_at: string; finished_at: string | null }
export interface Result { id: string; run_id: string; test_case_id: string; arm: string; verdict: string; metrics: Record<string, unknown>; final_state_hash: string; first_divergence: string; trace_id: string; test: TestSnapshot }
export interface Trace { result: Result; test: TestSnapshot; events: Array<{ id: string; sequence: number; type: string; payload: Record<string, unknown>; rule_ids: string[]; duration_ms: number; created_at: string }> }
export interface Report { id: string; run_id: string; verdict: string; evidence: { evidence_boundary: string; deterministic_runtime_boundary: string; provenance: Record<string, unknown>; hashes: Record<string, unknown>; comparison_arms: string[]; test_count: number; metrics: Record<string, ArmMetrics | Record<string, unknown>>; top_failures: Array<Record<string, unknown>>; limitations: string[]; report_digest?: string; [key: string]: unknown }; rendered_markdown: string; content_hash: string; created_at: string }
export interface APIError { code: string; message: string; details: Record<string, unknown>; request_id: string }
