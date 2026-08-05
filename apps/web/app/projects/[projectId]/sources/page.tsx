"use client";

import { FileJson2, FileText, Search } from "lucide-react";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, shortHash } from "@/lib/api";
import { authorityTone, documentPresentation, formattedEffectiveDate, metadataLabel } from "@/lib/document-presentation";
import type { Document, Finding, Rule } from "@/lib/types";
import { Badge, EmptyState, ErrorState, PageLoading, PageTitle } from "@/components/ui";

function hashLine(): number | null {
  if (typeof window === "undefined") return null;
  const match = window.location.hash.match(/^#line-(\d+)$/);
  if (!match) return null;
  const value = Number(match[1]);
  return Number.isSafeInteger(value) && value > 0 ? value : null;
}

function metadataList(values: string[]): string {
  return values.length ? values.join(" · ") : "Not declared";
}

export default function SourcesPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const searchParams = useSearchParams();
  const documents = useQuery({ queryKey: ["documents", projectId], queryFn: () => api<Document[]>(`/api/v1/projects/${projectId}/documents`) });
  const rules = useQuery({ queryKey: ["rules", projectId], queryFn: () => api<Rule[]>(`/api/v1/projects/${projectId}/rules`) });
  const findings = useQuery({ queryKey: ["findings", projectId], queryFn: () => api<Finding[]>(`/api/v1/projects/${projectId}/findings`) });
  const requestedDocumentId = searchParams.get("document") || undefined;
  const [selection, setSelection] = useState(() => ({ request: requestedDocumentId, selected: requestedDocumentId }));
  const selectedId = selection.request === requestedDocumentId ? selection.selected : requestedDocumentId;
  const [requestedLine, setRequestedLine] = useState<number | null>(hashLine);
  const [search, setSearch] = useState("");
  const selected = documents.data?.find((doc) => doc.id === selectedId) || documents.data?.[1] || documents.data?.[0];
  const selectedMetadata = documentPresentation(selected);
  const supersededDocument = documents.data?.find((doc) => doc.id === selected?.supersedes_document_id);
  const supersedingDocument = documents.data?.find((doc) => doc.supersedes_document_id === selected?.id);
  const linkedRules = useMemo(() => (rules.data || []).filter((rule) => rule.source_refs.some((ref) => ref.document_id === selected?.id)), [rules.data, selected?.id]);
  const highlighted = new Set(linkedRules.flatMap((rule) => rule.source_refs.filter((ref) => ref.document_id === selected?.id).flatMap((ref) => Array.from({ length: ref.line_end - ref.line_start + 1 }, (_, i) => ref.line_start + i))));
  useEffect(() => {
    const readLine = () => setRequestedLine(hashLine());
    readLine();
    window.addEventListener("hashchange", readLine);
    return () => window.removeEventListener("hashchange", readLine);
  }, []);
  useEffect(() => {
    if (!requestedLine || !selected || (requestedDocumentId && requestedDocumentId !== selected.id)) return;
    const frame = window.requestAnimationFrame(() => {
      const target = document.getElementById(`line-${requestedLine}`);
      if (!target) return;
      target.focus({ preventScroll: true });
      target.scrollIntoView({ block: "center", behavior: "auto" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [requestedDocumentId, requestedLine, selected]);
  if (documents.isLoading || rules.isLoading || findings.isLoading) return <PageLoading label="Loading source provenance" />;
  if (documents.error || rules.error || findings.error) return <ErrorState error={documents.error || rules.error || findings.error} onRetry={() => { documents.refetch(); rules.refetch(); findings.refetch(); }} />;
  if (!documents.data!.length) return <div className="content-wrap"><PageTitle eyebrow="Versioned ingest" title="Sources" detail="Exact text, hashes, and line spans stay attached to every reviewed rule." /><EmptyState title="No source documents" detail="This project does not have a versioned source corpus yet." /></div>;
  return <div className="content-wrap">
    <PageTitle eyebrow="Versioned ingest" title="Sources" detail="Exact text, hashes, and line spans stay attached to every reviewed rule." actions={<Badge tone="amber">Evaluation data — no customer records</Badge>} />
    <div className="toolbar">
      <div style={{ position: "relative" }}><Search size={15} style={{ position: "absolute", left: 10, top: 10, color: "#94a3b8" }} /><input className="search" style={{ paddingLeft: 32 }} aria-label="Search exact source text" placeholder="Search exact text" value={search} onChange={(event) => setSearch(event.target.value)} /></div>
      <Badge>{documents.data!.length} documents</Badge><span style={{ color: "var(--muted)", fontSize: 11 }}>Uploads are disabled in this release workspace.</span>
    </div>
    <section className="panel source-layout">
      <div className="source-list" aria-label="Source documents">
        {documents.data!.map((doc) => { const metadata = documentPresentation(doc); return <button className={`source-item ${doc.id === selected?.id ? "active" : ""}`} key={doc.id} onClick={() => setSelection({ request: requestedDocumentId, selected: doc.id })}>
          {doc.mime_type.includes("json") ? <FileJson2 size={15} /> : <FileText size={15} />}
          <strong>{doc.name}</strong><small>{doc.kind.replaceAll("_", " ")} · {metadata.versionLabel} · {doc.line_count} lines</small>
          {metadata.authorityStatus && <span className={`source-authority source-authority-${authorityTone(metadata.authorityStatus)}`}>{metadataLabel(metadata.authorityStatus)}</span>}
        </button>; })}
      </div>
      <div className="source-viewer">
        <div className="source-viewer-head">
          <div className="source-viewer-title"><strong>{selected?.name}</strong><span className="source-viewer-badges"><Badge tone="blue">{selected ? metadataLabel(selected.kind) : "Kind unavailable"}</Badge><Badge>{selectedMetadata.versionLabel}</Badge><Badge tone={authorityTone(selectedMetadata.authorityStatus)}>{selectedMetadata.authorityStatus ? metadataLabel(selectedMetadata.authorityStatus) : "Authority unavailable"}</Badge><Badge tone={selectedMetadata.effectiveAt ? "teal" : "neutral"}>Effective {formattedEffectiveDate(selectedMetadata.effectiveAt)}</Badge>{selectedMetadata.originType && <Badge tone="blue">{metadataLabel(selectedMetadata.originType)}</Badge>}</span></div>
          <div className="source-hashes" aria-label="Document hashes">
            <span>Original SHA-256 <code title={selected?.original_sha256}>{shortHash(selected?.original_sha256)}</code></span>
            <span>Normalized SHA-256 <code title={selected?.normalized_sha256 || undefined}>{selected?.normalized_sha256 ? shortHash(selected.normalized_sha256) : "Unavailable"}</code></span>
          </div>
        </div>
        <div className="source-code" role="region" aria-label={`Numbered source for ${selected?.name}`}>
          {selected?.normalized_text.split("\n").map((line, index) => {
            const match = search && line.toLowerCase().includes(search.toLowerCase());
            const lineNumber = index + 1;
            return <div id={`line-${lineNumber}`} key={index} tabIndex={requestedLine === lineNumber ? -1 : undefined} className={`source-line ${highlighted.has(lineNumber) || match || requestedLine === lineNumber ? "highlight" : ""}`}><span className="line-no">{lineNumber}</span><span className="line-text">{line || " "}</span></div>;
          })}
        </div>
      </div>
      <aside className="source-side">
        <h3>Authority &amp; provenance</h3>
        <dl className="source-metadata">
          <div><dt>Owner</dt><dd>{selectedMetadata.owner || "Not provided"}</dd></div>
          <div><dt>Status</dt><dd>{selectedMetadata.authorityStatus ? metadataLabel(selectedMetadata.authorityStatus) : "Unavailable"}</dd></div>
          <div><dt>Effective</dt><dd>{formattedEffectiveDate(selectedMetadata.effectiveAt)}</dd></div>
          <div><dt>Version</dt><dd>{selectedMetadata.versionLabel}</dd></div>
          <div><dt>Supersedes</dt><dd>{supersededDocument ? `${supersededDocument.name} · ${documentPresentation(supersededDocument).versionLabel}` : "No earlier source declared"}</dd></div>
          <div><dt>Superseded by</dt><dd>{supersedingDocument ? `${supersedingDocument.name} · ${documentPresentation(supersedingDocument).versionLabel}` : "No later authority declared"}</dd></div>
          <div><dt>Jurisdiction</dt><dd>{metadataList(selectedMetadata.jurisdictions)}</dd></div>
          <div><dt>Scope</dt><dd>{metadataList(selectedMetadata.scopes)}</dd></div>
          <div><dt>Parser</dt><dd>{selectedMetadata.parser ? `${selectedMetadata.parser}${selectedMetadata.parserVersion ? ` · ${selectedMetadata.parserVersion}` : ""}` : "Unavailable"}</dd></div>
          <div><dt>Normalizer</dt><dd>{selectedMetadata.normalizer ? `${selectedMetadata.normalizer}${selectedMetadata.normalizerVersion ? ` · ${selectedMetadata.normalizerVersion}` : ""}` : "Unavailable"}</dd></div>
        </dl>
        <h3>Linked rules · {linkedRules.length}</h3>
        {linkedRules.map((rule) => { const reference = rule.source_refs.find((item) => item.document_id === selected?.id); return <div className="linked-card" key={rule.id}><Badge tone={rule.status === "approved" ? "teal" : "amber"}>{rule.status.replaceAll("_", " ")}</Badge><strong>{rule.title}</strong><p>Lines {reference?.line_start}–{reference?.line_end} · {rule.enforcement}</p></div>; })}
        <h3 style={{ marginTop: 20 }}>Document findings</h3>
        {(findings.data || []).filter((finding) => finding.related_rule_ids.some((id) => linkedRules.some((rule) => rule.id === id))).map((finding) => <div className="linked-card" key={finding.id}><Badge tone={finding.severity === "critical" ? "red" : "amber"}>{finding.type}</Badge><p>{finding.message}</p></div>)}
      </aside>
    </section>
  </div>;
}
