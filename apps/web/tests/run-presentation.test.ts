import { describe, expect, it } from "vitest";
import { armChartName, armMetrics, armName, caseArmSummary, configuredBuildArms, evidenceValue, normalizeArms, releaseCoverageReady } from "@/lib/run-presentation";
import type { Build } from "@/lib/types";

describe("run presentation", () => {
  it("derives comparison arms from persisted API payloads", () => {
    const build = { input_manifest: { runtime: { arms: ["baseline_unenforced", "candidate_guarded", "candidate_guarded"] } } } as unknown as Build;
    expect(configuredBuildArms(build)).toEqual(["baseline_unenforced", "candidate_guarded"]);
    expect(normalizeArms(["first", "", null, "second"])).toEqual(["first", "second"]);
  });

  it("builds count and label copy from the supplied suite", () => {
    expect(caseArmSummary(1, ["guarded"])).toBe("1 case × 1 labelled arm");
    expect(caseArmSummary(24, ["first", "second", "third", "fourth"])).toBe("24 cases × 4 labelled arms");
    expect(armName("baseline_unenforced")).toBe("Original · observe");
    expect(armName("candidate_guarded")).toBe("Candidate Guarded");
    expect(armChartName("candidate_guarded")).toBe("Candidate Guarded");
  });

  it("accepts complete arm metrics and rejects coverage records", () => {
    const metrics = {
      guarded: {
        cases: 2,
        task_success_rate: 1,
        attempted_violation_rate: 0,
        executed_violation_rate: 0,
        false_block_rate: 0,
        tool_validation_error_rate: 0,
        input_tokens: null,
        output_tokens: null,
        cost: null,
      },
      coverage: { test_count: 2 },
    };
    expect(armMetrics(metrics, "guarded")?.cases).toBe(2);
    expect(armMetrics(metrics, "coverage")).toBeNull();
  });

  it("renders nested evidence values without passing objects to React", () => {
    expect(evidenceValue({ artifacts: ["manifest.json"] })).toBe('{"artifacts":["manifest.json"]}');
    expect(evidenceValue(null)).toBe("Not recorded");
  });

  it("requires complete rule, source, and boundary coverage for a release verdict", () => {
    const coverage = {
      test_count: 24,
      explicit_assertion_coverage: 1,
      compiler_assertion_coverage: 1,
      positive_negative_boundary: true,
      declared_rule_linkage: { ratio: 1 },
      declared_source_linkage: { ratio: 1 },
      declared_boundary_linkage: { ratio: 1 },
      critical_unclassified_rules: [],
    };
    expect(releaseCoverageReady(coverage, 24)).toBe(true);
    expect(releaseCoverageReady({ ...coverage, declared_boundary_linkage: { ratio: 0.75 } }, 24)).toBe(false);
    expect(releaseCoverageReady({ ...coverage, critical_unclassified_rules: ["rule.critical"] }, 24)).toBe(false);
  });
});
