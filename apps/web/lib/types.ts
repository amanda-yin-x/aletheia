import type { components } from "@aletheia/api-client/schema";

type ApiSchemas = components["schemas"];

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
  supersedes_document_id?: string | null;
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
export type PlacementDecision = ApiSchemas["PlacementDecisionOut"];
export type PlacementDestination = PlacementDecision["destinations"][number];
export type PlacementTransformKind = PlacementDecision["transform_kind"];
export type PlacementDisposition = PlacementDecision["disposition"];
export type PlacementReviewStatus = PlacementDecision["review_status"];
export type SourceAnchor = ApiSchemas["SourceAnchor"];
export type AuthorityStatus = SourceAnchor["authority_status"];
export type GeneratedSpan = ApiSchemas["GeneratedSpanOut"];

// Gate 1 response contracts are generated from FastAPI's OpenAPI document.
// Keeping these as aliases makes schema drift a CI failure instead of creating
// a second, handwritten frontend contract.
export type ContentSizeMetric = ApiSchemas["ContentSizeMetric"];
export type PreservationCheck = ApiSchemas["PreservationCheck"];
export type PreservationReport = ApiSchemas["PreservationReport"];
export type RoutingReportEntry = ApiSchemas["RoutingReportEntry"];
export type RoutingReport = ApiSchemas["RoutingReport"];
export type CompilationMetrics = ApiSchemas["CompilationMetrics"];
export type BuildStats = ApiSchemas["BuildStats"];
export type BuildInspection = ApiSchemas["BuildInspectionOut"];

export interface Build {
  id: string;
  project_id: string;
  status: string;
  input_manifest: Record<string, unknown>;
  input_hash: string;
  compiler_version: string;
  artifacts: Record<string, unknown>;
  source_map: Record<string, unknown>;
  stats: BuildStats | null;
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
