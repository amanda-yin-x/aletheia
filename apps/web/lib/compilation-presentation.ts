import type {
  Build,
  CompilationMetrics,
  ContentSizeMetric,
  Document,
  PlacementDecision,
  PlacementDestination,
  PlacementDisposition,
  PlacementTransformKind,
  PreservationReport,
  RoutingReport,
  SourceAnchor,
} from "@/lib/types";

export const PLACEMENT_DESTINATIONS: PlacementDestination[] = [
  "prompt_kernel",
  "skill",
  "knowledge",
  "pre_tool_policy",
  "test",
  "human_review",
  "unsupported",
];

const destinationLabels: Record<PlacementDestination, string> = {
  prompt_kernel: "Prompt kernel",
  skill: "Scoped skill",
  knowledge: "Knowledge",
  pre_tool_policy: "Pre-tool guard",
  test: "Regression test",
  human_review: "Human review",
  unsupported: "Unsupported",
};

const transformLabels: Record<PlacementTransformKind, string> = {
  verbatim: "Verbatim",
  reviewed_normalization: "Reviewed normalization",
  reviewer_authored_guidance: "Reviewer-authored guidance",
  compiler_scaffold: "Compiler scaffold",
};

const dispositionLabels: Record<PlacementDisposition, string> = {
  routed: "Routed",
  blocked: "Blocked",
  unsupported: "Unsupported",
  retired: "Retired",
};

export function destinationLabel(value: PlacementDestination): string {
  return destinationLabels[value];
}

export function transformLabel(value: PlacementTransformKind): string {
  return transformLabels[value];
}

export function dispositionLabel(value: PlacementDisposition): string {
  return dispositionLabels[value];
}

export function dispositionTone(value: PlacementDisposition): "teal" | "amber" | "red" | "neutral" {
  if (value === "routed") return "teal";
  if (value === "blocked" || value === "unsupported") return "red";
  return "neutral";
}

export function latestPlacementsByRule(decisions: PlacementDecision[]): Map<string, PlacementDecision> {
  const latest = new Map<string, PlacementDecision>();
  for (const decision of decisions) {
    const current = latest.get(decision.rule_id);
    if (!current || decision.version > current.version || (decision.version === current.version && decision.id > current.id)) {
      latest.set(decision.rule_id, decision);
    }
  }
  return latest;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isContentSizeMetric(value: unknown): value is ContentSizeMetric {
  if (!isRecord(value)) return false;
  return isNumber(value.lines)
    && isNumber(value.characters)
    && isNumber(value.utf8_bytes)
    && isNumber(value.estimated_tokens);
}

function isMetricMap(value: unknown): value is Record<string, ContentSizeMetric> {
  return isRecord(value) && Object.values(value).every(isContentSizeMetric);
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isExpectedContextMetric(value: unknown): value is ContentSizeMetric & { artifact_paths: string[] } {
  return isContentSizeMetric(value) && isRecord(value) && isStringArray(value.artifact_paths);
}

function isProtectedLiteral(value: unknown): value is { kind: string; value: string } {
  return isRecord(value) && typeof value.kind === "string" && typeof value.value === "string";
}

function isPreservationCheck(value: unknown): boolean {
  return isRecord(value)
    && typeof value.rule_key === "string"
    && isStringArray(value.artifact_paths)
    && Array.isArray(value.literals)
    && value.literals.every(isProtectedLiteral)
    && Array.isArray(value.missing)
    && value.missing.every(isProtectedLiteral)
    && typeof value.preserved === "boolean";
}

export function parseArtifactJson(build: Build, path: string): unknown {
  const value = build.artifacts[path];
  if (typeof value !== "string") return value;
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return undefined;
  }
}

export function compilationMetrics(build: Build, inspectionStats?: Record<string, unknown>): CompilationMetrics | null {
  const candidates: unknown[] = [
    build.stats.compilation,
    inspectionStats?.compilation,
    parseArtifactJson(build, "compilation-metrics.json"),
  ];
  for (const value of candidates) {
    if (!isRecord(value)
      || value.schema_version !== "1.0"
      || !isRecord(value.estimator)
      || typeof value.estimator.name !== "string"
      || typeof value.estimator.version !== "string"
      || !isContentSizeMetric(value.baseline_always_loaded)
      || !isContentSizeMetric(value.compiled_kernel)
      || !isMetricMap(value.skills)
      || !isMetricMap(value.knowledge)
      || !isMetricMap(value.machine_enforced)
      || !isContentSizeMetric(value.total_bundle_without_manifest)
      || !isExpectedContextMetric(value.expected_per_task_context)
      || !isRecord(value.routing)
      || !isNumber(value.routing.active_normative_clauses)
      || !isNumber(value.routing.explicit_dispositions)
      || !isNumber(value.routing.routing_coverage)
      || !isNumber(value.routing.verified_source_anchor_coverage)
      || !isNumber(value.routing.approved_preservation)
      || !isNumber(value.routing.severity_weighted_approved_preservation)
      || !isNumber(value.routing.high_critical_guard_and_test_placement)
      || !isNumber(value.routing.blocked_count)
      || !isNumber(value.routing.unsupported_count)
      || !isNumber(value.routing.unrouted_count)
      || !isNumber(value.routing.unresolved_count)
      || !Array.isArray(value.protected_literals)
      || !value.protected_literals.every(isPreservationCheck)
      || value.behavioral_fidelity !== "not_measured"
      || typeof value.interpretation !== "string") continue;
    return value as unknown as CompilationMetrics;
  }
  return null;
}

export function routingReport(build: Build): RoutingReport | null {
  const value = parseArtifactJson(build, "routing-report.json");
  if (!isRecord(value)
    || value.schema_version !== "1.0"
    || !isRecord(value.profile)
    || typeof value.profile.name !== "string"
    || typeof value.profile.version !== "string"
    || typeof value.profile.sha256 !== "string"
    || !Array.isArray(value.entries)
    || !value.entries.every((entry) => isRecord(entry)
      && typeof entry.rule_key === "string"
      && typeof entry.rule_stable_key === "string"
      && isNumber(entry.rule_revision)
      && typeof entry.title === "string"
      && typeof entry.disposition === "string"
      && isStringArray(entry.destinations)
      && typeof entry.rationale === "string"
      && isNumber(entry.verified_source_anchors)
      && typeof entry.provenance_kind === "string"
      && (entry.provenance_metadata === undefined || (isRecord(entry.provenance_metadata)
        && (entry.provenance_metadata.reviewer === undefined || entry.provenance_metadata.reviewer === null || typeof entry.provenance_metadata.reviewer === "string")
        && (entry.provenance_metadata.rationale === undefined || entry.provenance_metadata.rationale === null || typeof entry.provenance_metadata.rationale === "string")
        && (entry.provenance_metadata.reviewed_at === undefined || entry.provenance_metadata.reviewed_at === null || typeof entry.provenance_metadata.reviewed_at === "string")))
      && isRecord(entry.placement)
      && typeof entry.placement.transform_kind === "string")
    || !isRecord(value.counts)
    || !isNumber(value.counts.active)
    || !isNumber(value.counts.routed)
    || !isNumber(value.counts.blocked)
    || !isNumber(value.counts.unsupported)) return null;
  return value as unknown as RoutingReport;
}

export function preservationReport(build: Build): PreservationReport | null {
  const value = parseArtifactJson(build, "preservation-report.json");
  if (!isRecord(value)
    || value.schema_version !== "1.0"
    || !Array.isArray(value.checks)
    || !value.checks.every(isPreservationCheck)
    || value.behavioral_fidelity !== "not_measured"
    || typeof value.interpretation !== "string") return null;
  return value as unknown as PreservationReport;
}

export function sumContentMetrics(values: Record<string, ContentSizeMetric>): ContentSizeMetric {
  return Object.values(values).reduce<ContentSizeMetric>((total, item) => ({
    lines: total.lines + item.lines,
    characters: total.characters + item.characters,
    utf8_bytes: total.utf8_bytes + item.utf8_bytes,
    estimated_tokens: total.estimated_tokens + item.estimated_tokens,
  }), { lines: 0, characters: 0, utf8_bytes: 0, estimated_tokens: 0 });
}

export function sourceDocument(anchor: SourceAnchor, documents: Document[]): Document | undefined {
  return documents.find((document) => document.name === anchor.document_name && document.version === anchor.document_version);
}

export function sourceAnchorHref(projectId: string, anchor: SourceAnchor, documents: Document[]): string | null {
  const document = sourceDocument(anchor, documents);
  if (!document) return null;
  return `/projects/${encodeURIComponent(projectId)}/sources?document=${encodeURIComponent(document.id)}#line-${anchor.line_start}`;
}

export function artifactDisplay(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === undefined) return "";
  return JSON.stringify(value, null, 2);
}

export function formatRatio(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatBytes(value: number): string {
  return new Intl.NumberFormat("en-US").format(value);
}
