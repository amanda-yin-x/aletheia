export interface ConditionRow { fact: string; op: string; value: string }

export function conditionRows(condition: Record<string, unknown>): ConditionRow[] {
  if (condition.kind === "predicate") return [{ fact: String(condition.fact), op: String(condition.op), value: JSON.stringify(condition.value) }];
  if (Array.isArray(condition.conditions)) return condition.conditions.flatMap((child) => conditionRows(child as Record<string, unknown>));
  if (condition.kind === "not" && typeof condition.condition === "object" && condition.condition) return conditionRows(condition.condition as Record<string, unknown>);
  return [];
}

export function updateConditionValue(condition: Record<string, unknown>, targetIndex: number, rawValue: string): Record<string, unknown> {
  let predicateIndex = 0;
  let parsedValue: unknown;
  try { parsedValue = JSON.parse(rawValue); } catch { parsedValue = rawValue; }

  const visit = (node: Record<string, unknown>): Record<string, unknown> => {
    if (node.kind === "predicate") {
      const currentIndex = predicateIndex++;
      return currentIndex === targetIndex ? { ...node, value: parsedValue } : { ...node };
    }
    if (Array.isArray(node.conditions)) {
      return { ...node, conditions: node.conditions.map((child) => visit(child as Record<string, unknown>)) };
    }
    if (node.kind === "not" && typeof node.condition === "object" && node.condition) {
      return { ...node, condition: visit(node.condition as Record<string, unknown>) };
    }
    return { ...node };
  };

  return visit(condition);
}

export const traceEventClass = (type: string) => type === "tool_proposed" ? "proposed" : type === "tool_executed" || type === "state_changed" ? "executed" : type === "tool_blocked" || type === "approval_required" ? "blocked" : "";

export function traceEventSummary(type: string, payload: Record<string, unknown>): string {
  if (type.startsWith("tool_")) return `${String(payload.name || "Tool")} · ${String(payload.status || payload.decision || "recorded")}`;
  if (type === "policy_evaluated") return `${String(payload.decision).replaceAll("_", " ")} · ${String(payload.reason_code)}`;
  if (type === "approval_required") return "Proposal intercepted; approval route returned; state not mutated.";
  if (type === "state_changed") return "State changed after execution.";
  return String(payload.verdict || payload.arm || payload.content || "Recorded evidence event");
}
