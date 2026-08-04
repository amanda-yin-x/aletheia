"use client";

import { useState, type CSSProperties, type KeyboardEvent as ReactKeyboardEvent } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Check,
  FileCheck2,
  FileWarning,
  GitCompareArrows,
  LockKeyhole,
  Play,
  ScanSearch,
  ShieldCheck,
} from "lucide-react";

const typedDecision = "decision = require_approval";

const workflow = [
  {
    number: "1.0",
    verb: "Read",
    title: "Bring the policy record into one release context.",
    copy: "Aletheia preserves each source version, exact quote, line range, and content hash. The original instruction stays attached to the rule it becomes.",
    proof: "6 versioned Northstar sources",
    detail: "prompt · policy v3 · legacy SOP · style · tools · orders",
    icon: ScanSearch,
    route: "sources",
  },
  {
    number: "2.0",
    verb: "Resolve",
    title: "Make disagreement visible before it reaches an agent.",
    copy: "Reviewers see source-linked conflicts, ambiguity, missing facts, and the exact evidence behind each finding. Critical conflicts stop the build.",
    proof: "30 / 60 days · $200 / $250",
    detail: "human decision required · rationale retained",
    icon: GitCompareArrows,
    route: "rules",
  },
  {
    number: "3.0",
    verb: "Compile",
    title: "Turn reviewed intent into release artifacts.",
    copy: "Approved rules compile into a prompt kernel, workflow, deterministic tool policy, regression suite, source map, and manifest.",
    proof: "7 machine-decidable guards",
    detail: "bounded AST · stored snapshot · source-linked output",
    icon: LockKeyhole,
    route: "build",
  },
  {
    number: "4.0",
    verb: "Test",
    title: "Compare behavior before the candidate ships.",
    copy: "Run the same deep-copied cases across baseline, compiled, and guarded arms. Trace proposals separately from executions and state changes.",
    proof: "Reviewed suite × labelled comparison arms",
    detail: "trace · metrics · Markdown / JSON evidence",
    icon: FileCheck2,
    route: "tests",
  },
] as const;

const outputs = [
  ["Source record", "Exact quote, line span, and source hash"],
  ["Prompt + workflow", "Reviewed instructions routed by purpose"],
  ["Tool policy", "A bounded decision contract before side effects"],
  ["Regression suite", "Positive, negative, and boundary scenarios"],
  ["Evidence report", "Build, run, dataset, metrics, and limitations"],
] as const;

export function MarketingLanding() {
  const [scenario, setScenario] = useState<"without" | "with">("with");
  const workspaceHref = "/demo";
  const handleScenarioKeyDown = (event: ReactKeyboardEvent<HTMLButtonElement>) => {
    const order = ["without", "with"] as const;
    const current = order.indexOf(scenario);
    let next: (typeof order)[number] | undefined;
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = order[(current - 1 + order.length) % order.length];
    if (event.key === "ArrowRight" || event.key === "ArrowDown") next = order[(current + 1) % order.length];
    if (event.key === "Home") next = order[0];
    if (event.key === "End") next = order[order.length - 1];
    if (!next) return;
    event.preventDefault();
    setScenario(next);
    window.requestAnimationFrame(() => document.getElementById(`scenario-tab-${next}`)?.focus());
  };

  return (
    <main className="marketing-landing">
      <section className="marketing-hero" aria-labelledby="hero-title">
        <div className="marketing-hero-copy">
          <p className="hero-category marketing-intro" style={{ "--intro-order": 0 } as CSSProperties}>Source-linked policy enforcement</p>
          <h1 id="hero-title" className="marketing-intro" style={{ "--intro-order": 1 } as CSSProperties}>The policy CI for AI agents.</h1>
          <p className="hero-lede marketing-intro" style={{ "--intro-order": 2 } as CSSProperties}>
            Turn scattered instructions into reviewed rules, enforceable tool guards, and repeatable release tests — before customer-facing actions ship.
          </p>
          <div className="marketing-hero-actions marketing-intro" style={{ "--intro-order": 3 } as CSSProperties}>
            <Link className="marketing-button marketing-button-primary" href={workspaceHref}>Run the refund scenario <ArrowRight size={16} aria-hidden="true" /></Link>
            <a className="marketing-text-link" href="#why">See the failure path <ArrowRight size={15} aria-hidden="true" /></a>
          </div>
          <dl className="hero-facts marketing-intro" style={{ "--intro-order": 4 } as CSSProperties} aria-label="Bundled Northstar fixture targets">
            <div><dt>Sources</dt><dd>6</dd></div>
            <div><dt>Suite</dt><dd>Reviewed</dd></div>
            <div><dt>Critical open</dt><dd>2</dd></div>
          </dl>
          <p className="hero-boundary marketing-intro" style={{ "--intro-order": 5 } as CSSProperties}>
            <ShieldCheck size={15} aria-hidden="true" /> <span>Bundled Northstar fixture · deterministic evaluation · no customer records · scoped evidence</span>
          </p>
        </div>

        <div className="policy-console marketing-intro" style={{ "--intro-order": 3 } as CSSProperties} role="group" aria-label="Aletheia policy decision preview">
          <div className="policy-console-head">
            <div><span>POLICY RUN</span><strong>NORTHSTAR / REFUND-BOUNDARY</strong></div>
            <span className="console-status"><span aria-hidden="true" /> CASE READY</span>
          </div>
          <div className="console-rule">
            <span>reviewed guard</span>
            <code>issue_refund.amount &gt; 200</code>
          </div>
          <ol className="console-trace">
            <li><span>01</span><div><small>tool.proposed</small><strong>issue_refund($200.01)</strong></div><em>seen</em></li>
            <li><span>02</span><div><small>policy.evaluated</small><strong>rule.refund.approval_threshold</strong></div><em>match</em></li>
            <li className="console-trace-active"><span>03</span><div><small><span className="typed-decision-visual" aria-hidden="true"><span className="typed-decision-text">{typedDecision}</span><i /></span><span className="sr-only">{typedDecision}</span></small><strong>Approval must exist first</strong></div><em>hold</em></li>
            <li><span>04</span><div><small>state.compared</small><strong>No refund mutation recorded</strong></div><em>held</em></li>
          </ol>
          <div className="console-foot"><span>proposal ≠ execution</span><span>source-linked decision</span></div>
        </div>
      </section>

      <section id="why" className="incident-section" aria-labelledby="incident-title">
        <div className="incident-heading">
          <div>
            <p className="incident-scenario-label">Refund policy failure scenario</p>
            <h2 id="incident-title">One refund. Three documents. Two answers.</h2>
          </div>
          <p>A current policy says 30 days and approval above $200. A legacy SOP says 60 days and allows up to $250. Both look authoritative when they are flattened into one prompt.</p>
        </div>

        <div className="incident-workbench">
          <div className="incident-inputs" role="group" aria-label="Conflicting policy inputs">
            <article><span>REFUND POLICY V3</span><strong>30 days</strong><p>Approval required above $200.</p></article>
            <article><span>LEGACY REFUND SOP</span><strong>60 days</strong><p>Automatic refund allowed up to $250.</p></article>
            <div className="incident-call"><FileWarning size={18} aria-hidden="true" /><span><small>AGENT PROPOSAL</small><strong>Refund $200.01 without prior approval</strong></span></div>
          </div>

          <div className="scenario-result">
            <div className="scenario-tabs" role="tablist" aria-label="Compare release behavior">
              <button id="scenario-tab-without" type="button" role="tab" aria-selected={scenario === "without"} aria-controls="scenario-panel" tabIndex={scenario === "without" ? 0 : -1} onKeyDown={handleScenarioKeyDown} onClick={() => setScenario("without")}>Without a gate</button>
              <button id="scenario-tab-with" type="button" role="tab" aria-selected={scenario === "with"} aria-controls="scenario-panel" tabIndex={scenario === "with" ? 0 : -1} onKeyDown={handleScenarioKeyDown} onClick={() => setScenario("with")}>With Aletheia</button>
            </div>
            {scenario === "without" ? (
              <div id="scenario-panel" className="scenario-panel" role="tabpanel" aria-labelledby="scenario-tab-without" aria-live="polite">
                <p className="scenario-verdict scenario-verdict-danger"><span aria-hidden="true">×</span> Without the gate, the refund executes.</p>
                <ol>
                  <li><span>tool.proposed</span><strong>$200.01 refund</strong></li>
                  <li><span>tool.executed</span><strong>Refund operation executes</strong></li>
                  <li><span>state.changed</span><strong>Refund record created</strong></li>
                </ol>
                <small>Observation arrives after the side effect.</small>
              </div>
            ) : (
              <div id="scenario-panel" className="scenario-panel" role="tabpanel" aria-labelledby="scenario-tab-with" aria-live="polite">
                <p className="scenario-verdict scenario-verdict-safe"><Check size={17} aria-hidden="true" /> The guard intercepts before execution.</p>
                <ol>
                  <li><span>tool.proposed</span><strong>$200.01 refund</strong></li>
                  <li><span>approval.required</span><strong>Rule + source returned</strong></li>
                  <li><span>state.unchanged</span><strong>No execution event</strong></li>
                </ol>
                <small>The proposal remains visible; the mutation does not occur.</small>
              </div>
            )}
          </div>
        </div>

        <p className="incident-thesis">Logs tell you what happened. A release gate decides whether it can happen.</p>
      </section>

      <section id="workflow" className="narrative-workflow" aria-labelledby="workflow-title">
        <header className="workflow-heading">
          <h2 id="workflow-title">Policy becomes a release process.</h2>
          <p>Not another prompt editor. Aletheia keeps source evidence, human review, executable boundaries, and regression results in one inspectable path.</p>
        </header>
        <ol className="workflow-list">
          {workflow.map((stage) => {
            const Icon = stage.icon;
            return (
              <li key={stage.number}>
                <div className="workflow-copy"><div className="workflow-number"><span>{stage.number}</span><small>{stage.verb}</small></div><h3>{stage.title}</h3><p>{stage.copy}</p><Link href="/demo">Inspect {stage.verb.toLocaleLowerCase()} stage <ArrowRight size={14} aria-hidden="true" /></Link></div>
                <div className="workflow-proof"><Icon size={18} aria-hidden="true" /><strong>{stage.proof}</strong><small>{stage.detail}</small></div>
              </li>
            );
          })}
        </ol>
      </section>

      <section id="evidence" className="evidence-section" aria-labelledby="evidence-title">
        <div className="evidence-thesis">
          <h2 id="evidence-title">A reviewed change leaves artifacts—not vibes.</h2>
          <p>Each output has a job in the release decision. The bundle can be inspected by the policy owner, the agent engineer, and the person reviewing evidence.</p>
          <Link className="marketing-text-link" href="/demo">Inspect a compiled build <ArrowRight size={15} aria-hidden="true" /></Link>
        </div>
        <dl className="evidence-spec">
          {outputs.map(([name, detail]) => <div key={name}><dt>{name}</dt><dd>{detail}</dd><Check size={15} aria-hidden="true" /></div>)}
        </dl>
        <aside className="evidence-boundary">
          <ShieldCheck size={20} aria-hidden="true" />
          <div><strong>Evidence with a stated boundary.</strong><p>This evidence establishes deterministic behavior for the reviewed rules and covered tool calls. Its scope is explicit: one versioned build, one evaluation suite, and the calls routed through the policy adapter.</p></div>
        </aside>
      </section>

      <section className="closing-cta" aria-labelledby="closing-title">
        <div>
          <h2 id="closing-title">Put the next policy change through a release gate.</h2>
          <p>Resolve the 30/60-day conflict, approve the $200 boundary, compile the candidate, and inspect the blocked $200.01 trace.</p>
        </div>
        <Link className="marketing-button marketing-button-primary" href={workspaceHref}><Play size={16} aria-hidden="true" /> Open Northstar workspace</Link>
      </section>

      <footer className="marketing-footer">
        <p>Policies deserve a release gate.</p>
        <div>
          <span className="marketing-wordmark">Aletheia</span>
          <nav aria-label="Footer navigation">
            <a href="https://github.com/amanda-yin-x/aletheia">GitHub</a>
            <a href="https://github.com/amanda-yin-x/aletheia/blob/main/docs/current-state-and-production-roadmap.md">Roadmap</a>
            <a href="https://github.com/amanda-yin-x/aletheia/blob/main/LICENSE">MIT License</a>
          </nav>
          <small>Open source · deterministic fixture evaluation · 2026</small>
        </div>
      </footer>
    </main>
  );
}
