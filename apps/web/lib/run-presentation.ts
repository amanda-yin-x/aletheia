import type { ArmMetrics, Build } from "./types";

const ARM_NAMES: Record<string, string> = {
  baseline_unenforced: "Original · observe",
  compiled_unenforced: "Compiled · observe",
  compiled_enforced: "Compiled · enforced",
};

const ARM_CHART_NAMES: Record<string, string> = {
  baseline_unenforced: "Original",
  compiled_unenforced: "Compiled",
  compiled_enforced: "Guarded",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

export function normalizeArms(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.filter((arm): arm is string => typeof arm === "string" && arm.trim().length > 0))];
}

export function configuredBuildArms(build: Build | null | undefined): string[] {
  const runtime = build && isRecord(build.input_manifest.runtime) ? build.input_manifest.runtime : null;
  return normalizeArms(runtime?.arms);
}

function titleCaseIdentifier(value: string): string {
  return value
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

export function armName(arm: string): string {
  return ARM_NAMES[arm] || titleCaseIdentifier(arm) || "Unnamed arm";
}

export function armChartName(arm: string): string {
  return ARM_CHART_NAMES[arm] || titleCaseIdentifier(arm) || "Arm";
}

export function caseArmSummary(caseCount: number, arms: readonly string[]): string {
  const safeCases = Number.isFinite(caseCount) && caseCount >= 0 ? caseCount : 0;
  return `${safeCases} ${safeCases === 1 ? "case" : "cases"} × ${arms.length} labelled ${arms.length === 1 ? "arm" : "arms"}`;
}

export function armMetrics(
  metrics: Record<string, ArmMetrics | Record<string, unknown>>,
  arm: string | undefined,
): ArmMetrics | null {
  if (!arm) return null;
  const value = metrics[arm];
  if (!isRecord(value)) return null;
  const numericKeys = [
    "cases",
    "task_success_rate",
    "attempted_violation_rate",
    "executed_violation_rate",
    "false_block_rate",
    "tool_validation_error_rate",
  ] as const;
  if (numericKeys.some((key) => typeof value[key] !== "number")) return null;
  return value as unknown as ArmMetrics;
}

export function recordMetric(
  metrics: Record<string, ArmMetrics | Record<string, unknown>>,
  name: string,
): Record<string, unknown> {
  const value = metrics[name];
  return isRecord(value) ? value : {};
}

export function releaseCoverageReady(coverage: Record<string, unknown>, expectedCases: number): boolean {
  const fullCoverage = (name: string) => {
    const value = coverage[name];
    return isRecord(value) && value.ratio === 1;
  };
  return expectedCases > 0
    && coverage.test_count === expectedCases
    && coverage.explicit_assertion_coverage === 1
    && coverage.compiler_assertion_coverage === 1
    && coverage.positive_negative_boundary === true
    && fullCoverage("declared_rule_linkage")
    && fullCoverage("declared_source_linkage")
    && fullCoverage("declared_boundary_linkage")
    && Array.isArray(coverage.critical_unclassified_rules)
    && coverage.critical_unclassified_rules.length === 0;
}

export function evidenceValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Not recorded";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return "Unserializable value";
  }
}
