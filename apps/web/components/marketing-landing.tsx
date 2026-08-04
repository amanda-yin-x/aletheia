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

const typedDecision = "decision = deny";

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
            <Link className="marketing-button marketing-button-primary" href={workspaceHref}>Inspect the refund decision <ArrowRight size={16} aria-hidden="true" /></Link>
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
            <div><span>POLICY RUN</span><strong>NORTHSTAR / COMPOSITE-REFUND</strong></div>
            <span className="console-status"><span aria-hidden="true" /> CASE READY</span>
          </div>
          <div className="console-rule">
            <span>proposed mutation</span>
            <code>issue_refund(N-1099, $249, gift_card)</code>
          </div>
          <ol className="console-trace">
            <li><span>01</span><div><small>tool.proposed</small><strong>$249 → gift card</strong></div><em>seen</em></li>
            <li><span>02</span><div><small>policy.evaluated</small><strong>Returnability + destination</strong></div><em>2 match</em></li>
            <li className="console-trace-active"><span>03</span><div><small><span className="typed-decision-visual" aria-hidden="true"><span className="typed-decision-text">{typedDecision}</span><i /></span><span className="sr-only">{typedDecision}</span></small><strong>Standard refund path blocked</strong></div><em>deny</em></li>
            <li><span>04</span><div><small>state.compared</small><strong>No refund mutation recorded</strong></div><em>held</em></li>
          </ol>
          <div className="console-foot"><span>proposal ≠ execution</span><span>source-linked decision</span></div>
        </div>
      </section>

      <section id="why" className="incident-section" aria-labelledby="incident-title">
        <div className="incident-heading">
          <div>
            <p className="incident-scenario-label">Composite support-automation scenario</p>
            <h2 id="incident-title">The agent’s plan looks valid. The action is not.</h2>
          </div>
          <p>After identity verification, a customer asks for gift-card credit on a $249 order. It is only nine days old, so the retained desk SOP appears to authorize it. But the item is non-returnable, the destination is forbidden, and no matching approval exists.</p>
        </div>

        <div className="incident-workbench">
          <div className="incident-inputs" role="group" aria-label="Order state and conflicting policy inputs">
            <article className="incident-source-current"><span>CURRENT POLICY · V3</span><strong>3 controls</strong><p>Non-returnable items escalate. Refunds use the original payment method. Amounts above $200 need matching approval.</p></article>
            <article className="incident-source-legacy"><span>RETAINED DESK SOP · V1.4</span><strong>60 days · $250</strong><p>Agents may auto-refund through $250 and use the customer-requested payment option.</p></article>
            <article className="incident-source-state"><span>RUNTIME ORDER + REQUEST</span><strong>N-1099 · day 9 · $249</strong><p>Item I-99 is marked non-returnable. The customer requests gift-card credit; no approval event exists.</p></article>
            <div className="incident-call"><FileWarning size={18} aria-hidden="true" /><span><small>AGENT TOOL PROPOSAL</small><strong><code>issue_refund</code> · N-1099 · $249 → gift card</strong></span></div>
          </div>

          <div className="scenario-result">
            <div className="scenario-tabs" role="tablist" aria-label="Compare release behavior">
              <button id="scenario-tab-without" type="button" role="tab" aria-selected={scenario === "without"} aria-controls="scenario-panel" tabIndex={scenario === "without" ? 0 : -1} onKeyDown={handleScenarioKeyDown} onClick={() => setScenario("without")}>Without a gate</button>
              <button id="scenario-tab-with" type="button" role="tab" aria-selected={scenario === "with"} aria-controls="scenario-panel" tabIndex={scenario === "with" ? 0 : -1} onKeyDown={handleScenarioKeyDown} onClick={() => setScenario("with")}>With Aletheia</button>
            </div>
            {scenario === "without" ? (
              <div id="scenario-panel" className="scenario-panel" role="tabpanel" aria-labelledby="scenario-tab-without" aria-live="polite">
                <p className="scenario-verdict scenario-verdict-danger"><span aria-hidden="true">×</span> A plausible plan becomes a forbidden mutation.</p>
                <ol>
                  <li><span>tool.proposed</span><strong>$249 → gift card</strong></li>
                  <li><span>policy.evaluated</span><strong>Deny · not enforced</strong></li>
                  <li><span>tool.executed</span><strong><code>issue_refund</code></strong></li>
                  <li><span>state.changed</span><strong>Refund record created</strong></li>
                </ol>
                <small>The policy match is recorded but not enforced; the side effect still occurs.</small>
              </div>
            ) : (
              <div id="scenario-panel" className="scenario-panel" role="tabpanel" aria-labelledby="scenario-tab-with" aria-live="polite">
                <p className="scenario-verdict scenario-verdict-safe"><Check size={17} aria-hidden="true" /> The current policy stops the mutation.</p>
                <ol>
                  <li><span>tool.proposed</span><strong>$249 → gift card</strong></li>
                  <li><span>policy.denied</span><strong>2 current rules matched</strong></li>
                  <li><span>decision.recorded</span><strong>Rule IDs + facts + hash</strong></li>
                  <li><span>state.unchanged</span><strong>No <code>tool_executed</code> event</strong></li>
                </ol>
                <small>The proposal remains inspectable. Deny takes precedence; approval cannot override a forbidden destination or non-returnable item.</small>
              </div>
            )}
          </div>
        </div>

        <p className="incident-thesis">The risk is not an absurd prompt. It is a defensible-looking action assembled from stale authority, runtime state, and real tool access.</p>
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
          <p>Resolve conflicting authority, compile the reviewed rules, and inspect why the N-1099 refund proposal never becomes an execution event.</p>
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
