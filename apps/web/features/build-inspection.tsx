"use client";

import Link from "next/link";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  FileCode2,
  Folder,
  GitBranch,
  Link2,
  Route,
  ShieldCheck,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Badge, EmptyState, StatCard } from "@/components/ui";
import { authorityTone, metadataLabel } from "@/lib/document-presentation";
import {
  artifactDisplay,
  compilationMetrics,
  destinationLabel,
  dispositionLabel,
  dispositionTone,
  formatBytes,
  formatRatio,
  preservationReport,
  routingReport,
  sourceAnchorHref,
  sumContentMetrics,
  transformLabel,
} from "@/lib/compilation-presentation";
import { shortHash } from "@/lib/api";
import type {
  Build,
  BuildInspection,
  ContentSizeMetric,
  Document,
  GeneratedSpan,
} from "@/lib/types";

interface ArtifactTreeNode {
  name: string;
  path?: string;
  children: ArtifactTreeNode[];
}

function sortedArtifactPaths(paths: string[]): string[] {
  return [...paths].sort((left, right) => {
    if (left === "manifest.json") return -1;
    if (right === "manifest.json") return 1;
    return left.localeCompare(right);
  });
}

function artifactTree(paths: string[]): ArtifactTreeNode[] {
  const root: ArtifactTreeNode = { name: "", children: [] };
  for (const path of sortedArtifactPaths(paths)) {
    const parts = path.split("/");
    let current = root;
    parts.forEach((part, index) => {
      let child = current.children.find((item) => item.name === part);
      if (!child) {
        child = { name: part, children: [] };
        current.children.push(child);
      }
      if (index === parts.length - 1) child.path = path;
      current = child;
    });
  }
  const sort = (nodes: ArtifactTreeNode[]): ArtifactTreeNode[] => nodes
    .map((node) => ({ ...node, children: sort(node.children) }))
    .sort((left, right) => {
      if (left.path && !right.path) return 1;
      if (!left.path && right.path) return -1;
      if (left.path === "manifest.json") return -1;
      if (right.path === "manifest.json") return 1;
      return left.name.localeCompare(right.name);
    });
  return sort(root.children);
}

function ArtifactTree({ nodes, selected, onSelect, depth = 0 }: { nodes: ArtifactTreeNode[]; selected: string; onSelect: (path: string) => void; depth?: number }) {
  return <ul className="artifact-tree-level">{nodes.map((node) => <li key={`${depth}:${node.name}`}>
    {node.path ? <button type="button" className={node.path === selected ? "active" : undefined} aria-current={node.path === selected ? "true" : undefined} onClick={() => onSelect(node.path!)}><FileCode2 size={13} /><span>{node.name}</span></button> : <details open><summary><Folder size={13} /> {node.name}</summary><ArtifactTree nodes={node.children} selected={selected} onSelect={onSelect} depth={depth + 1} /></details>}
  </li>)}</ul>;
}

function lineRange(start: number, end: number): string {
  return start === end ? `line ${start}` : `lines ${start}–${end}`;
}

function ArtifactLines({ content, spans, onSelectSpan }: { content: string; spans: GeneratedSpan[]; onSelectSpan: (span: GeneratedSpan) => void }) {
  const lines = content.split("\n");
  return <div className="artifact-line-viewer" role="region" aria-label="Numbered artifact content">
    {lines.map((line, index) => {
      const lineNumber = index + 1;
      const mappings = spans.filter((span) => span.line_start <= lineNumber && span.line_end >= lineNumber);
      return <div className={`artifact-output-line ${mappings.length ? "mapped" : ""}`} key={lineNumber}>
        {mappings.length ? <button type="button" className="artifact-output-line-number" aria-label={`Inspect ${mappings.length} source ${mappings.length === 1 ? "mapping" : "mappings"} for line ${lineNumber}`} onClick={() => onSelectSpan(mappings[0])}>{lineNumber}<Link2 size={9} /></button> : <span className="artifact-output-line-number">{lineNumber}</span>}
        <span className="artifact-output-line-text">{line || " "}</span>
      </div>;
    })}
  </div>;
}

function SpanInspector({ projectId, spans, documents, selectedSpan, onSelect }: { projectId: string; spans: GeneratedSpan[]; documents: Document[]; selectedSpan?: GeneratedSpan; onSelect: (span: GeneratedSpan) => void }) {
  if (!spans.length) return <div className="artifact-span-empty"><GitBranch size={17} /><div><strong>No generated span is recorded for this artifact.</strong><p>A missing mapping is shown as missing; it is not treated as provenance.</p></div></div>;
  const span = selectedSpan || spans[0];
  return <div className="artifact-provenance">
    <div className="artifact-span-list" aria-label="Generated spans">{spans.map((item) => <button type="button" key={item.id} className={item.id === span.id ? "active" : undefined} onClick={() => onSelect(item)}><span>{lineRange(item.line_start, item.line_end)}</span><strong>{item.rule_stable_key ? `${item.rule_stable_key}@${item.rule_revision}` : "Compiler scaffold"}</strong></button>)}</div>
    <div className="artifact-span-detail">
      <div className="artifact-span-head"><div><span className="eyebrow">Generated span</span><h3>{span.rule_stable_key ? `${span.rule_stable_key}@${span.rule_revision}` : "Compiler-generated scaffold"}</h3></div><Badge tone={span.transform_kind === "compiler_scaffold" ? "neutral" : "blue"}>{transformLabel(span.transform_kind)}</Badge></div>
      <dl className="artifact-span-metadata">
        <div><dt>Artifact range</dt><dd>{lineRange(span.line_start, span.line_end)} (1-based) · UTF-8 bytes [{span.utf8_byte_start}, {span.utf8_byte_end})</dd></div>
        <div><dt>Text digest</dt><dd><code title={span.text_sha256}>{shortHash(span.text_sha256)}</code></dd></div>
        <div><dt>Placement</dt><dd>{span.placement_decision_id ? `version ${span.placement_version}` : "No placement record"}</dd></div>
      </dl>
      {span.transform_kind === "compiler_scaffold" ? <div className="artifact-scaffold-note"><AlertTriangle size={15} /><span>Compiler scaffold has no source-anchor claim.</span></div> : span.transform_kind === "reviewer_authored_guidance" && !span.source_refs.length ? <div className="artifact-guidance-note"><ShieldCheck size={15} /><span>Reviewer-authored guidance has no source-anchor claim. Reviewer attribution is pinned in the routing report below.</span></div> : span.source_refs.length ? <div className="artifact-source-anchors"><strong>Exact source anchors</strong>{span.source_refs.map((anchor) => {
        const href = sourceAnchorHref(projectId, anchor, documents);
        return <article key={anchor.source_anchor_id}>
          <div><span>{anchor.document_name} · {anchor.version_label}</span><Badge tone={authorityTone(anchor.authority_status)}>{metadataLabel(anchor.authority_status)}</Badge></div>
          <blockquote>{anchor.quote}</blockquote>
          <p>{anchor.authority_owner} · {lineRange(anchor.line_start, anchor.line_end)} · normalized <code title={anchor.normalized_sha256}>{shortHash(anchor.normalized_sha256)}</code></p>
          {href ? <Link href={href}><Link2 size={12} /> Open exact source {lineRange(anchor.line_start, anchor.line_end)}</Link> : <span className="artifact-source-unavailable">The pinned source version is not available in this project response.</span>}
        </article>;
      })}</div> : <div className="artifact-scaffold-note"><AlertTriangle size={15} /><span>This source-derived span has no source anchor in the inspection response.</span></div>}
    </div>
  </div>;
}

function MetricRow({ name, scope, metric }: { name: string; scope: string; metric: ContentSizeMetric }) {
  return <tr><th scope="row"><strong>{name}</strong><small>{scope}</small></th><td>{metric.lines}</td><td>{formatBytes(metric.characters)}</td><td>{formatBytes(metric.utf8_bytes)}</td><td>{formatBytes(metric.estimated_tokens)}</td></tr>;
}

export function BuildInspectionView({ projectId, build, inspection, documents }: { projectId: string; build: Build; inspection: BuildInspection; documents: Document[] }) {
  const paths = inspection.artifacts.map((artifact) => artifact.path);
  const initialPath = paths.includes("prompt-kernel.md") ? "prompt-kernel.md" : sortedArtifactPaths(paths)[0] || "";
  const [selectedPath, setSelectedPath] = useState(initialPath);
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);
  const selectedArtifact = paths.includes(selectedPath) ? selectedPath : initialPath;
  const artifact = build.artifacts[selectedArtifact];
  const display = artifactDisplay(artifact);
  const spans = inspection.generated_spans.filter((span) => span.artifact_path === selectedArtifact);
  const selectedSpan = spans.find((span) => span.id === selectedSpanId);
  const hashes = new Map(inspection.artifacts.map((item) => [item.path, item.sha256]));
  const tree = useMemo(() => artifactTree(paths), [paths]);
  const metrics = compilationMetrics(build, inspection.stats);
  const routing = routingReport(build);
  const preservation = preservationReport(build);

  const onDemand = metrics ? sumContentMetrics(Object.fromEntries([
    ...Object.entries(metrics.skills).map(([path, value]) => [`skill:${path}`, value]),
    ...Object.entries(metrics.knowledge).map(([path, value]) => [`knowledge:${path}`, value]),
  ])) : null;
  const machine = metrics ? sumContentMetrics(metrics.machine_enforced) : null;
  const preservedCount = preservation?.checks.filter((check) => check.preserved).length || 0;

  return <>
    <section className="panel build-snapshot-panel">
      <div className="panel-header"><div><h2>Build snapshot <Badge tone="teal"><CheckCircle2 size={11} /> Stored</Badge></h2><p className="hash-line">Manifest {shortHash(build.content_hash)} · input {shortHash(build.input_hash)} · compiler {build.compiler_version}</p></div><Badge tone="blue">{new Date(build.created_at).toLocaleString()}</Badge></div>
      <div className="bundle-layout">
        <nav className="artifact-tree" aria-label="Compiled bundle tree"><div className="artifact-tree-title"><Folder size={14} /><strong>Compiled bundle</strong><span>{paths.length} files</span></div>{paths.length ? <ArtifactTree nodes={tree} selected={selectedArtifact} onSelect={(path) => { setSelectedPath(path); setSelectedSpanId(null); }} /> : <p>No artifact paths were returned.</p>}</nav>
        <div className="artifact-inspector">
          <div className="panel-body artifact-detail">
            <div><strong>{selectedArtifact || "No artifact selected"}</strong><p className="hash-line">SHA-256 {hashes.get(selectedArtifact) || "Digest unavailable"}</p></div>
            {selectedArtifact && <a className="button button-secondary" href={`/api/v1/builds/${encodeURIComponent(build.id)}/artifacts/${selectedArtifact.split("/").map(encodeURIComponent).join("/")}`} download><Download size={14} /> Download exact bytes</a>}
          </div>
          {selectedArtifact && artifact !== undefined ? <ArtifactLines content={display} spans={spans} onSelectSpan={(span) => setSelectedSpanId(span.id)} /> : <div className="artifact-content-missing" role="status">Artifact content is not present in this build response.</div>}
          <SpanInspector projectId={projectId} spans={spans} documents={documents} selectedSpan={selectedSpan} onSelect={(span) => setSelectedSpanId(span.id)} />
        </div>
      </div>
    </section>

    <section className="panel compilation-metrics-panel">
      <div className="panel-header"><div><h2>Compilation metrics</h2><p>Exact stored sizes with the named deterministic estimator.</p></div>{metrics && <Badge>{metrics.estimator.name} · {metrics.estimator.version}</Badge>}</div>
      {!metrics ? <div className="panel-body"><EmptyState title="Compilation metrics unavailable" detail="This stored build does not contain a valid Gate 1 compilation-metrics contract." /></div> : <>
        <div className="metric-table-wrap"><table className="metric-table"><thead><tr><th>Context layer</th><th>Lines</th><th>Characters</th><th>UTF-8 bytes</th><th>Estimated tokens</th></tr></thead><tbody>
          <MetricRow name="Baseline always-loaded" scope="Pinned compiler input" metric={metrics.baseline_always_loaded} />
          <MetricRow name="Compiled kernel" scope="Always loaded" metric={metrics.compiled_kernel} />
          <MetricRow name="Skills + knowledge" scope={`${Object.keys(metrics.skills).length + Object.keys(metrics.knowledge).length} on-demand artifacts`} metric={onDemand!} />
          <MetricRow name="Machine-enforced" scope={`${Object.keys(metrics.machine_enforced).length} guard/test artifacts`} metric={machine!} />
          <MetricRow name="Expected task context" scope={metrics.expected_per_task_context.artifact_paths.join(" · ") || "No paths declared"} metric={metrics.expected_per_task_context} />
          <MetricRow name="Total bundle without manifest" scope="Stored compiler metric" metric={metrics.total_bundle_without_manifest} />
        </tbody></table></div>
        <div className="panel-body metric-routing-grid">
          <StatCard label="Routing coverage" value={formatRatio(metrics.routing.routing_coverage)} note={`${metrics.routing.explicit_dispositions} of ${metrics.routing.active_normative_clauses} explicit dispositions`} tone={metrics.routing.routing_coverage === 1 ? "teal" : "amber"} />
          <StatCard label="Verified anchors" value={formatRatio(metrics.routing.verified_source_anchor_coverage)} note="Source-anchored or reviewed guidance" tone={metrics.routing.verified_source_anchor_coverage === 1 ? "teal" : "amber"} />
          <StatCard label="Approved preservation" value={formatRatio(metrics.routing.approved_preservation)} note="Exact renderings + protected literals" tone={metrics.routing.approved_preservation === 1 ? "teal" : "amber"} />
          <StatCard label="Guard + test placement" value={formatRatio(metrics.routing.high_critical_guard_and_test_placement)} note="Approved high/critical clauses" tone={metrics.routing.high_critical_guard_and_test_placement === 1 ? "teal" : "amber"} />
        </div>
        <div className="behavioral-boundary"><AlertTriangle size={18} /><div><strong>Behavioral fidelity: Not measured</strong><p>{metrics.interpretation}</p></div></div>
      </>}
    </section>

    <section className="panel routing-report-panel">
      <div className="panel-header"><div><h2><Route size={15} /> Routing report</h2><p>Build-pinned dispositions and destinations for every active clause.</p></div>{routing && <div className="routing-count-badges"><Badge tone="teal">{routing.counts.routed} routed</Badge><Badge tone={routing.counts.blocked ? "red" : "neutral"}>{routing.counts.blocked} blocked</Badge><Badge tone={routing.counts.unsupported ? "red" : "neutral"}>{routing.counts.unsupported} unsupported</Badge></div>}</div>
      {!routing ? <div className="panel-body"><EmptyState title="Routing report unavailable" detail="This stored build does not contain a valid routing-report contract." /></div> : <>
        <div className="routing-profile">Profile <strong>{routing.profile.name} {routing.profile.version}</strong> · <code title={routing.profile.sha256}>{shortHash(routing.profile.sha256)}</code> · {routing.counts.active} active clauses</div>
        <div className="routing-report-list">{routing.entries.map((entry) => <article key={entry.rule_key}>
          <div className="routing-report-heading"><div><span>{entry.rule_key}</span><strong>{entry.title}</strong></div><Badge tone={dispositionTone(entry.disposition)}>{dispositionLabel(entry.disposition)}</Badge></div>
          <div className="routing-report-tags"><Badge>{transformLabel(entry.placement.transform_kind)}</Badge>{entry.destinations.map((destination) => <Badge key={destination} tone={destination === "unsupported" ? "red" : destination === "human_review" ? "amber" : "blue"}>{destinationLabel(destination)}</Badge>)}</div>
          <p>{entry.rationale}</p><small>{entry.verified_source_anchors} verified source {entry.verified_source_anchors === 1 ? "anchor" : "anchors"} · {entry.provenance_kind.replaceAll("_", " ")}</small>
          {entry.provenance_kind === "reviewer_authored_guidance" && <div className="routing-reviewer-attribution"><strong>Reviewer attribution</strong><span>{entry.provenance_metadata?.reviewer || "Reviewer unavailable"}</span><p>{entry.provenance_metadata?.rationale || "Reviewer rationale unavailable in this stored report."}{entry.provenance_metadata?.reviewed_at ? ` · ${new Date(entry.provenance_metadata.reviewed_at).toLocaleString()}` : ""}</p></div>}
        </article>)}</div>
      </>}
    </section>

    <section className="panel preservation-report-panel">
      <div className="panel-header"><div><h2><ShieldCheck size={15} /> Preservation report</h2><p>Deterministic rendering and protected-literal conformance checks.</p></div>{preservation && <Badge tone={preservedCount === preservation.checks.length ? "teal" : "red"}>{preservedCount} / {preservation.checks.length} preserved</Badge>}</div>
      {!preservation ? <div className="panel-body"><EmptyState title="Preservation report unavailable" detail="This stored build does not contain a valid preservation-report contract." /></div> : <>
        <div className="preservation-list">{preservation.checks.map((check) => <details key={check.rule_key}>
          <summary><span><strong>{check.rule_key}</strong><small>{check.artifact_paths.join(" · ") || "No output artifact"}</small></span><Badge tone={check.preserved ? "teal" : "red"}>{check.preserved ? "Preserved" : `${check.missing.length} missing`}</Badge></summary>
          <div><strong>Protected literals</strong>{check.literals.length ? <ul>{check.literals.map((literal, index) => <li key={`${literal.kind}:${literal.value}:${index}`} className={check.missing.some((missing) => missing.kind === literal.kind && missing.value === literal.value) ? "missing" : undefined}><code>{literal.value}</code><span>{literal.kind.replaceAll("_", " ")}</span></li>)}</ul> : <p>No protected literal was extracted for this rendering.</p>}</div>
        </details>)}</div>
        <p className="preservation-interpretation"><strong>Evidence boundary:</strong> {preservation.interpretation}</p>
      </>}
    </section>
  </>;
}
