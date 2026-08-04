import { describe, expect, it, vi } from "vitest";
import { OperationFailedError, OPERATION_FAILURE_STATUSES, operationIsTerminal, operationStatusFailed, operationStatusIsTerminal, pollOperation } from "@/lib/operations";
import type { Operation, OperationStatus } from "@/lib/types";

function operation(status: OperationStatus, progress = 0): Operation {
  return { id: "job_123", kind: "compile", status, progress, resource_type: status === "succeeded" ? "build" : null, resource_id: status === "succeeded" ? "build_123" : null, attempt_count: 1, error: status === "failed" ? { code: "compile_failed", message: "Compilation failed." } : null, updated_at: "2026-08-03T00:00:00Z" };
}

describe("operation polling", () => {
  it("polls queued and running states through success", async () => {
    const states = [operation("running", 45), operation("succeeded", 100)];
    const fetchOperation = vi.fn(async () => states.shift()!);
    const onProgress = vi.fn();
    const result = await pollOperation(operation("queued"), { fetchOperation, onProgress, sleep: async () => {} });
    expect(result.status).toBe("succeeded");
    expect(fetchOperation).toHaveBeenCalledTimes(2);
    expect(onProgress).toHaveBeenLastCalledWith(expect.objectContaining({ progress: 100 }));
  });

  it.each([...OPERATION_FAILURE_STATUSES])("treats %s as a terminal failure", async (status) => {
    const value = operation(status);
    expect(operationIsTerminal(value)).toBe(true);
    expect(operationStatusIsTerminal(status)).toBe(true);
    expect(operationStatusFailed(status)).toBe(true);
    await expect(pollOperation(value, { sleep: async () => {} })).rejects.toBeInstanceOf(OperationFailedError);
  });

  it("recognizes success as terminal without treating it as a failure", () => {
    expect(operationStatusIsTerminal("succeeded")).toBe(true);
    expect(operationStatusFailed("succeeded")).toBe(false);
  });

  it("keeps an unknown state nonterminal for forward compatibility", () => {
    expect(operationIsTerminal(operation("waiting_for_capacity"))).toBe(false);
  });
});
