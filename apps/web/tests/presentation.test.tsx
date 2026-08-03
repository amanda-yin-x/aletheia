import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge, Button, PageTitle } from "@/components/ui";
import { label, pct, shortHash } from "@/lib/api";
import { conditionRows, traceEventClass, traceEventSummary, updateConditionValue } from "@/lib/presentation";

describe("policy workbench presentation", () => {
  it("renders key controls with accessible button names", () => {
    render(<><PageTitle title="Rules and findings" detail="Review source-linked rules." actions={<Button>Build candidate</Button>} /><Badge tone="red">Critical</Badge></>);
    expect(screen.getByRole("heading", { name: "Rules and findings" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Build candidate" })).toBeEnabled();
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });

  it("flattens a safe condition form without raw-code editing", () => {
    const rows = conditionRows({ kind: "all", conditions: [
      { kind: "predicate", fact: "tool.name", op: "eq", value: "issue_refund" },
      { kind: "predicate", fact: "tool.arguments.amount", op: "gt", value: 200 },
    ] });
    expect(rows).toEqual([
      { fact: "tool.name", op: "eq", value: '"issue_refund"' },
      { fact: "tool.arguments.amount", op: "gt", value: "200" },
    ]);
  });

  it("updates only the selected predicate in the bounded condition editor", () => {
    const condition = { kind: "all", conditions: [
      { kind: "predicate", fact: "tool.name", op: "eq", value: "issue_refund" },
      { kind: "predicate", fact: "tool.arguments.amount", op: "gt", value: 200 },
    ] };
    expect(conditionRows(updateConditionValue(condition, 1, "250"))[1]).toEqual({ fact: "tool.arguments.amount", op: "gt", value: "250" });
    expect(conditionRows(condition)[1].value).toBe("200");
  });

  it("distinguishes proposed, executed, and blocked trace events", () => {
    expect(traceEventClass("tool_proposed")).toBe("proposed");
    expect(traceEventClass("tool_executed")).toBe("executed");
    expect(traceEventClass("approval_required")).toBe("blocked");
    expect(traceEventSummary("approval_required", {})).toContain("state not mutated");
  });

  it("uses honest N/A and deterministic display helpers", () => {
    expect(pct(undefined)).toBe("N/A");
    expect(pct(0.625)).toBe("63%");
    expect(label("require_approval")).toBe("Require Approval");
    expect(shortHash("1234567890abcdef")).toBe("12345678…cdef");
  });
});
