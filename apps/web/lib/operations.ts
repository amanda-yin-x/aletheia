import { api, apiWithResponse, type ApiRequestInit } from "./api";
import type { Operation, OperationStatus } from "./types";

export const OPERATION_FAILURE_STATUSES = new Set<OperationStatus>([
  "failed", "dead_lettered", "cancelled", "canceled", "expired", "timed_out", "stale", "aborted",
]);

export class OperationFailedError extends Error {
  constructor(public operation: Operation) {
    super(operation.error?.message || `The ${operation.kind} operation ended with status ${operation.status}.`);
    this.name = "OperationFailedError";
  }
}

export class OperationProtocolError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "OperationProtocolError";
  }
}

export function operationStatusFailed(status: OperationStatus | null | undefined): boolean {
  return Boolean(status && OPERATION_FAILURE_STATUSES.has(status));
}

export function operationStatusIsTerminal(status: OperationStatus | null | undefined): boolean {
  return status === "succeeded" || operationStatusFailed(status);
}

export function operationIsTerminal(operation: Operation): boolean {
  return operationStatusIsTerminal(operation.status);
}

export function operationSucceeded(operation: Operation): boolean {
  return operation.status === "succeeded";
}

function isOperation(value: unknown): value is Operation {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<Operation> & { job_id?: unknown };
  return typeof candidate.id === "string" && typeof candidate.status === "string" && typeof candidate.kind === "string" && typeof candidate.progress === "number";
}

function normalizeOperation(value: unknown, fallbackKind: string): Operation | null {
  if (isOperation(value)) return value;
  if (!value || typeof value !== "object") return null;
  const legacy = value as Record<string, unknown>;
  if (typeof legacy.job_id !== "string" || typeof legacy.status !== "string") return null;
  return {
    id: legacy.job_id,
    kind: typeof legacy.kind === "string" ? legacy.kind : fallbackKind,
    status: legacy.status,
    progress: typeof legacy.progress === "number" ? legacy.progress : 0,
    resource_type: typeof legacy.resource_type === "string" ? legacy.resource_type : null,
    resource_id: typeof legacy.resource_id === "string" ? legacy.resource_id : null,
    attempt_count: typeof legacy.attempt_count === "number" ? legacy.attempt_count : 0,
    error: legacy.error && typeof legacy.error === "object" ? legacy.error as Operation["error"] : null,
    updated_at: typeof legacy.updated_at === "string" ? legacy.updated_at : new Date().toISOString(),
  };
}

function delay(milliseconds: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(signal.reason || new DOMException("Aborted", "AbortError"));
    const timer = setTimeout(resolve, milliseconds);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(signal.reason || new DOMException("Aborted", "AbortError"));
    }, { once: true });
  });
}

export async function pollOperation(
  initial: Operation,
  options: {
    signal?: AbortSignal;
    onProgress?: (operation: Operation) => void;
    timeoutMs?: number;
    intervalMs?: number;
    fetchOperation?: (id: string) => Promise<Operation>;
    sleep?: (milliseconds: number, signal?: AbortSignal) => Promise<void>;
  } = {},
): Promise<Operation> {
  const timeoutMs = options.timeoutMs ?? 120_000;
  const intervalMs = options.intervalMs ?? 750;
  const fetchOperation = options.fetchOperation || ((id: string) => api<Operation>(`/api/v1/jobs/${encodeURIComponent(id)}`, { signal: options.signal }));
  const sleep = options.sleep || delay;
  const startedAt = Date.now();
  let operation = initial;
  options.onProgress?.(operation);

  while (!operationIsTerminal(operation)) {
    if (Date.now() - startedAt >= timeoutMs) throw new OperationProtocolError(`The ${operation.kind} operation did not finish within ${Math.ceil(timeoutMs / 1_000)} seconds.`);
    await sleep(intervalMs, options.signal);
    operation = await fetchOperation(operation.id);
    options.onProgress?.(operation);
  }
  if (!operationSucceeded(operation)) throw new OperationFailedError(operation);
  return operation;
}

function validResourceId(value: string | null): value is string {
  return Boolean(value && value.length <= 128 && /^[a-zA-Z0-9_-]+$/.test(value));
}

export async function startOperationAndLoadResource<T extends { id: string }>(options: {
  path: string;
  init: ApiRequestInit;
  operationKind: string;
  resourceType: string;
  resourcePath: (resourceId: string) => string;
  validateResource?: (resource: T) => boolean;
  onProgress?: (operation: Operation) => void;
  signal?: AbortSignal;
}): Promise<T> {
  const { data, response } = await apiWithResponse<Operation | T | { job_id: string; status: string }>(options.path, { ...options.init, signal: options.signal });
  const operation = normalizeOperation(data, options.operationKind);

  // Local inline mode can still return the completed resource directly.
  if (response.status !== 202 && !operation && data && typeof data === "object" && typeof (data as T).id === "string") {
    const resource = data as T;
    if (options.validateResource && !options.validateResource(resource)) throw new OperationProtocolError("The API returned a resource outside the requested project.");
    return resource;
  }
  if (!operation) throw new OperationProtocolError("The API did not return a valid operation.");

  const completed = await pollOperation(operation, { signal: options.signal, onProgress: options.onProgress });
  if (completed.resource_type !== options.resourceType) {
    throw new OperationProtocolError(`The completed operation returned ${completed.resource_type || "no resource type"}; expected ${options.resourceType}.`);
  }
  if (!validResourceId(completed.resource_id)) throw new OperationProtocolError("The completed operation did not return a valid resource identifier.");
  const resource = await api<T>(options.resourcePath(completed.resource_id), { signal: options.signal });
  if (resource.id !== completed.resource_id || (options.validateResource && !options.validateResource(resource))) {
    throw new OperationProtocolError("The completed operation returned a resource outside the requested project.");
  }
  return resource;
}
