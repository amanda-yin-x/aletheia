"use client";

import { ArrowLeft, Ban, CheckCircle2, CircleDot, PlayCircle, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, label, shortHash } from "@/lib/api";
import type { Trace } from "@/lib/types";
import { traceEventClass, traceEventSummary } from "@/lib/presentation";
import { Badge, ErrorState, PageLoading, PageTitle } from "@/components/ui";

export default function TracePage() {
  const { resultId } = useParams<{ resultId: string }>();
  const trace = useQuery({ queryKey: ["trace", resultId], queryFn: () => api<Trace>(`/api/v1/scenario-results/${resultId}/trace`) });
  const [selectedIndex, setSelectedIndex] = useState(3);
  if (trace.isLoading) return <main className="landing"><PageLoading label="Loading source-linked trace" /></main>;
  if (trace.error) return <main className="landing"><ErrorState error={trace.error} onRetry={() => trace.refetch()} /></main>;
  const data = trace.data!;
  const selected = data.events[selectedIndex] || data.events[0];
  const firstHash = String(data.test.spec.initial_state ? data.events[0]?.payload.initial_state_hash : "");
  return <main className="landing" style={{ maxWidth: 1320, paddingTop: 34 }}>
    <div style={{ marginBottom: 18 }}><Link className="arrow-label" href={`/runs/${data.result.run_id}`}><ArrowLeft size={14} /> Back to run comparison</Link></div>
    <PageTitle eyebrow={`${label(data.result.arm)} · ${data.test.provenance}`} title={data.test.title} detail="The trace separates a proposed call, deterministic policy decision, execution status, and sandbox state change." actions={<Badge tone={data.result.verdict === "passed" ? "teal" : "red"}>{label(data.result.verdict)}</Badge>} />
    {data.result.first_divergence && <div className="divergence"><strong>First divergence</strong><br />{data.result.first_divergence}</div>}
    <section className="panel trace-layout">
      <aside className="trace-summary"><h3>Case evidence</h3><div className="definition"><span>Expected decision</span><strong>{label(String(data.test.spec.expected.guarded_decision))}</strong></div><div className="definition"><span>Initial state</span><strong className="mono">{shortHash(firstHash)}</strong></div><div className="definition"><span>Final state</span><strong className="mono">{shortHash(data.result.final_state_hash)}</strong></div><div className="definition"><span>Linked rules</span>{data.test.spec.rule_ids.map((rule) => <Badge key={rule}>{rule}</Badge>)}</div><div className="definition"><span>Adapter</span><strong>Fixture agent · no model</strong></div></aside>
      <div className="timeline" aria-label="Ordered trace events">
        {data.events.map((event, index) => <div key={event.id} className={`timeline-event ${traceEventClass(event.type)} ${index === selectedIndex ? "selected" : ""}`} onClick={() => setSelectedIndex(index)} onKeyDown={(input) => { if (input.key === "Enter") setSelectedIndex(index); }} tabIndex={0}>
          <div className="event-head">{event.type === "tool_proposed" ? <CircleDot size={14} /> : event.type === "tool_executed" ? <PlayCircle size={14} /> : event.type === "approval_required" || event.type === "tool_blocked" ? <Ban size={14} /> : event.type === "policy_evaluated" ? <ShieldAlert size={14} /> : <CheckCircle2 size={14} />}<strong>{label(event.type)}</strong><span>#{event.sequence}</span>{event.type === "tool_proposed" && <Badge tone="amber">Proposed</Badge>}{event.type === "tool_executed" && <Badge tone="teal">Executed</Badge>}</div>
          <p className="event-summary">{traceEventSummary(event.type, event.payload)}</p>
        </div>)}
      </div>
      <aside className="trace-detail"><h3>Selected event</h3><Badge tone={selected.type === "tool_blocked" || selected.type === "approval_required" ? "red" : selected.type === "tool_executed" ? "teal" : "blue"}>{label(selected.type)}</Badge>{selected.rule_ids.length > 0 && <div className="definition" style={{ marginTop: 14 }}><span>Contributing rule revisions</span>{selected.rule_ids.map((rule) => <strong key={rule}>{rule}</strong>)}</div>}<div className="definition" style={{ marginTop: 14 }}><span>Evidence payload</span><pre className="json-view">{JSON.stringify(selected.payload, null, 2)}</pre></div></aside>
    </section>
  </main>;
}
