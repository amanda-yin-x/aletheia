import type { APIError } from "./types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class RequestError extends Error {
  constructor(public payload: APIError, public status: number) { super(payload.message); }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ code: "request_failed", message: "Request failed.", details: {}, request_id: response.headers.get("x-request-id") || "unknown" }));
    throw new RequestError(payload, response.status);
  }
  return response.json() as Promise<T>;
}

export const shortHash = (value?: string) => value ? `${value.slice(0, 8)}…${value.slice(-4)}` : "N/A";
export const pct = (value: number | undefined) => typeof value === "number" ? `${Math.round(value * 100)}%` : "N/A";
export const label = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());

