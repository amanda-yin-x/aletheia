import { label } from "./api";
import type { Document } from "./types";

function originString(document: Document | undefined, key: string): string | null {
  const value = document?.origin?.[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function originStrings(document: Document | undefined, key: string): string[] {
  const value = document?.origin?.[key];
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && Boolean(item.trim()))
    : [];
}

export interface DocumentPresentation {
  owner: string | null;
  authorityStatus: string | null;
  effectiveAt: string | null;
  versionLabel: string;
  jurisdictions: string[];
  scopes: string[];
  parser: string | null;
  parserVersion: string | null;
  normalizer: string | null;
  normalizerVersion: string | null;
  originType: string | null;
}

export function documentPresentation(document: Document | undefined): DocumentPresentation {
  const jurisdictions = document?.jurisdictions?.filter(Boolean) || [];
  const scopes = document?.scopes?.filter(Boolean) || document?.authority_scopes?.filter(Boolean) || [];
  return {
    owner: document?.owner?.trim() || document?.authority_owner?.trim() || originString(document, "owner"),
    authorityStatus: document?.authority_status?.trim() || originString(document, "authority_status"),
    effectiveAt: document?.effective_at?.trim() || originString(document, "effective_at"),
    versionLabel: document?.version_label?.trim() || (document ? `v${document.version}` : "Version unavailable"),
    jurisdictions: jurisdictions.length ? jurisdictions : originStrings(document, "jurisdictions"),
    scopes: scopes.length ? scopes : originStrings(document, "scopes"),
    parser: document?.parser?.trim() || originString(document, "parser"),
    parserVersion: document?.parser_version?.trim() || originString(document, "parser_version"),
    normalizer: document?.normalizer?.trim() || originString(document, "normalizer"),
    normalizerVersion: document?.normalizer_version?.trim() || originString(document, "normalizer_version"),
    originType: originString(document, "type"),
  };
}

export function authorityTone(status: string | null): "neutral" | "teal" | "amber" | "red" {
  const normalized = status?.toLocaleLowerCase();
  if (normalized && ["current", "active", "authoritative", "approved"].includes(normalized)) return "teal";
  if (normalized && ["superseded", "stale", "retired"].includes(normalized)) return "amber";
  if (normalized && ["revoked", "rejected"].includes(normalized)) return "red";
  return "neutral";
}

export function metadataLabel(value: string | null): string {
  return value ? label(value) : "Unavailable";
}

export function formattedEffectiveDate(value: string | null): string {
  if (!value) return "Not provided";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return value;
  return new Intl.DateTimeFormat("en", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" }).format(parsed);
}
