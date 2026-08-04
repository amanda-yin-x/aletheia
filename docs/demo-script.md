# 90-second product walkthrough

**0:00–0:12 — Context.** Open Northstar Retail. “This refund agent's rules are
spread across its baseline prompt, current policy, and stale SOP.”

**0:12–0:30 — Review.** Open Rules. Point to the source-linked 30/60-day conflict, the
$200/$250 approval conflict, and “daylight hours,” which lacks a measurable
range and trusted timezone fact. Resolve only the critical conflicts using the
current policy.

**0:30–0:42 — Approve.** Open “Approval above $200.” Show the exact source line
and the form condition `tool.arguments.amount > 200`. Approve its new revision.

**0:42–0:56 — Compile.** Open Build and create the snapshot. Show measured
original/candidate lines and estimated tokens, then the prompt, workflow, JSON
tool policy, tests, source map, and manifest hashes.

**0:56–1:16 — Compare.** Open Tests and run the bundled cases across original
observe-only, compiled observe-only, and compiled enforced arms. Emphasize that
the arms start from identical initial-state hashes.

**1:16–1:25 — Trace.** Open `$200.01 without approval`. The same refund call is
proposed; the guarded arm produces `require_approval`, does not execute the
refund tool, and shows no unauthorized state mutation.

**1:25–1:30 — Evidence.** Create the report. Point to scope, evaluation provenance,
build/run/dataset hashes, comparison metrics, limitations, and Markdown/JSON
exports. Say “fixture suite passed,” never “safe,” “certified,” or “ready for a controlled pilot.”
