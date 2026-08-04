"use client";

import { FileJson2, FileText, Search } from "lucide-react";
import { useParams, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, shortHash } from "@/lib/api";
import type { Document, Finding, Rule } from "@/lib/types";
import { Badge, ErrorState, PageLoading, PageTitle } from "@/components/ui";

export default function SourcesPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const searchParams = useSearchParams();
  const documents = useQuery({ queryKey: ["documents", projectId], queryFn: () => api<Document[]>(`/api/v1/projects/${projectId}/documents`) });
  const rules = useQuery({ queryKey: ["rules", projectId], queryFn: () => api<Rule[]>(`/api/v1/projects/${projectId}/rules`) });
  const findings = useQuery({ queryKey: ["findings", projectId], queryFn: () => api<Finding[]>(`/api/v1/projects/${projectId}/findings`) });
  const [selectedId, setSelectedId] = useState<string | undefined>(searchParams.get("document") || undefined);
  const [search, setSearch] = useState("");
  const selected = documents.data?.find((doc) => doc.id === selectedId) || documents.data?.[1] || documents.data?.[0];
  const linkedRules = useMemo(() => (rules.data || []).filter((rule) => rule.source_refs.some((ref) => ref.document_id === selected?.id)), [rules.data, selected?.id]);
  const highlighted = new Set(linkedRules.flatMap((rule) => rule.source_refs.filter((ref) => ref.document_id === selected?.id).flatMap((ref) => Array.from({ length: ref.line_end - ref.line_start + 1 }, (_, i) => ref.line_start + i))));
  if (documents.isLoading || rules.isLoading || findings.isLoading) return <PageLoading label="Loading source provenance" />;
  if (documents.error || rules.error || findings.error) return <ErrorState error={documents.error || rules.error || findings.error} onRetry={() => { documents.refetch(); rules.refetch(); findings.refetch(); }} />;
  return <div className="content-wrap">
    <PageTitle eyebrow="Versioned ingest" title="Sources" detail="Exact text, hashes, and line spans stay attached to every reviewed rule." actions={<Badge tone="amber">Evaluation data — no customer records</Badge>} />
    <div className="toolbar">
      <div style={{ position: "relative" }}><Search size={15} style={{ position: "absolute", left: 10, top: 10, color: "#94a3b8" }} /><input className="search" style={{ paddingLeft: 32 }} aria-label="Search exact source text" placeholder="Search exact text" value={search} onChange={(event) => setSearch(event.target.value)} /></div>
      <Badge>{documents.data!.length} documents</Badge><span style={{ color: "var(--muted)", fontSize: 11 }}>Uploads are disabled in this release workspace.</span>
    </div>
    <section className="panel source-layout">
      <div className="source-list" aria-label="Source documents">
        {documents.data!.map((doc) => <button className={`source-item ${doc.id === selected?.id ? "active" : ""}`} key={doc.id} onClick={() => setSelectedId(doc.id)}>
          {doc.mime_type.includes("json") ? <FileJson2 size={15} /> : <FileText size={15} />}
          <strong>{doc.name}</strong><small>{doc.kind.replaceAll("_", " ")} · v{doc.version} · {doc.line_count} lines</small>
        </button>)}
      </div>
      <div className="source-viewer">
        <div className="source-viewer-head"><div><strong>{selected?.name}</strong> <Badge tone="blue">Aletheia-authored</Badge></div><span className="hash-line">SHA-256 {shortHash(selected?.original_sha256)}</span></div>
        <div className="source-code" role="region" aria-label={`Numbered source for ${selected?.name}`}>
          {selected?.normalized_text.split("\n").map((line, index) => {
            const match = search && line.toLowerCase().includes(search.toLowerCase());
            return <div id={`line-${index + 1}`} key={index} className={`source-line ${highlighted.has(index + 1) || match ? "highlight" : ""}`}><span className="line-no">{index + 1}</span><span className="line-text">{line || " "}</span></div>;
          })}
        </div>
      </div>
      <aside className="source-side">
        <h3>Linked rules · {linkedRules.length}</h3>
        {linkedRules.map((rule) => { const reference = rule.source_refs.find((item) => item.document_id === selected?.id); return <div className="linked-card" key={rule.id}><Badge tone={rule.status === "approved" ? "teal" : "amber"}>{rule.status.replaceAll("_", " ")}</Badge><strong>{rule.title}</strong><p>Lines {reference?.line_start}–{reference?.line_end} · {rule.enforcement}</p></div>; })}
        <h3 style={{ marginTop: 20 }}>Document findings</h3>
        {(findings.data || []).filter((finding) => finding.related_rule_ids.some((id) => linkedRules.some((rule) => rule.id === id))).map((finding) => <div className="linked-card" key={finding.id}><Badge tone={finding.severity === "critical" ? "red" : "amber"}>{finding.type}</Badge><p>{finding.message}</p></div>)}
      </aside>
    </section>
  </div>;
}
