# Aletheia — independent product and engineering review v2

**Version:** 2.0  
**Reconciliation date:** 2026-08-04  
**Repository inspected:** local Gate 1 implementation `d10af278f785be76a8232589b4d0264792147a17`, based on `91055f6043edfd7f0cb171eac0bd04c611f2d509`  
**Predecessor:** `aletheia_independent_review_and_product_decision (1).md`, version 1.0, retained unchanged as historical input  
**Predecessor SHA-256:** `60b2cb7445f24965a485aadcbda54dfca15b38a971c418d7fe4a1a5c07ac6e53`

## 1. Decision

Continue Aletheia as a **source-aware policy refactoring and compilation
workbench for AI agents**.

The Northstar fixture established a trustworthy deterministic foundation. The
Gate 1 implementation now introduces a domain-neutral compiler profile,
explicit placement decisions, exact generated-span provenance, honest
preservation/context metrics, and an Acme appointment-scheduling source pack.
Those changes now pass the complete local Gate 1 checkpoint: two-domain and
fresh-process compilation, API/contracts, SQLite/PostgreSQL migrations,
frontend, Cloudflare packaging, and browser E2E. This is completion only in the
verified local deterministic fixture scope; it is not a hosted/deployed claim.

The product hypothesis remains narrower than a generic guard proxy:

> Aletheia helps a team refactor reviewed prompts, skills, SOPs, policies, and
> tool schemas into a smaller always-loaded kernel plus scoped skills,
> knowledge, deterministic guards, tests, and explicit pending material—while
> retaining a verifiable source-to-generated-span chain.

This is not automatic understanding of arbitrary policies, formal verification,
or proof that a model behaves better after compilation.

## 2. Evidence precedence

When claims disagree, use this order:

1. current code, migrations, generated contracts, and tests run against the
   inspected working tree;
2. `docs/capabilities.json` and the canonical current-state/build-plan docs once
   reconciled to those results;
3. the Gate 1 execution brief and its successor handoff;
4. this product review;
5. the research map;
6. the original v1 review and v2 handoff;
7. root greenfield prompt/specification, which remain historical.

External sources establish technical patterns, adjacent positioning, or
reported research. Vendor feature pages and practitioner threads do not prove
customer adoption, product quality, or willingness to pay.

## 3. Current feature status

| Feature track | Current evidence-backed status |
|---|---|
| Gate 0 — Local deterministic foundation | Complete in the tested Northstar fixture/local scope. |
| Gate 0H — Hosted verification and release hardening | In progress. Supabase, Render, staging, and canonical Cloudflare are provisioned; the permanent-user staging lifecycle passed. Anonymous Turnstile redemption and the complete guest lifecycle remain unverified. |
| Gate 1 — Source-aware policy refactoring and prompt/skill compilation | Complete in the verified local two-domain deterministic fixture scope; not deployed. |
| Gates 2–8 | Not implemented as product capabilities. Existing provider interfaces and tau data sync do not count as those gates. |

Confirmed local Gate 1 checkpoint evidence: the default API suite passed 139
tests with one skipped; the focused regenerated-contract/Gate 1 suite passed 31;
Ruff, mypy, SQLite Alembic upgrade/drift through `0006`, and one fresh real
PostgreSQL migration integration passed (four deselected, temporary database
removed). Frontend ESLint, strict type checking, all 84 Vitest tests across 22
files, and the production Next.js build passed. OpenNext at compatibility date
`2026-08-04`, Wrangler `4.118.0` type generation, root/staging dry-runs (53
assets; 8,019.91 KiB / 1,665.20 KiB gzip), and local startup check (34.0 ms)
also passed. The focused two-domain E2E passed 1/1 in 15.2 seconds and the full
fresh-isolated Playwright suite passed 6/6 in 1.3 minutes. `pip-audit` and the
production high-severity `pnpm audit` found no known vulnerabilities. Dry-run
size/startup observations are not deployment or production-performance claims.

These are local working-tree results. The deployed public Workers remain the
separately recorded `147448a` release; this review does not imply Gate 1 was
deployed.

The exact checkpoint evidence is in
[`gate-1-verification-report.md`](gate-1-verification-report.md).

### Gate 0 foundation retained

The repository already provides:

- explicit Alembic migrations and SQLite/PostgreSQL paths;
- application-scoped authenticated workspaces;
- exact raw-byte and normalized-text document hashes;
- source-linked, versioned Rule IR and atomic authority review;
- build-pinned deterministic policy, tests, tools, facts, runs, and reports;
- strict tool proposal validation and no mutation after a blocked or malformed
  proposal;
- idempotent HTTP `202` operations, polling, leases, recovery, and a local
  worker path;
- a no-key Northstar workflow with fixture traces and evidence exports.

### Gate 0H boundary

The hosted architecture is real, not merely configuration:

- Supabase Auth/Postgres, Render FastAPI, and Cloudflare/OpenNext are
  provisioned;
- the permanent-account staging path passed bootstrap, two-user isolation,
  Northstar build/run/trace/report/download, Data API denial, and direct-origin
  rejection;
- the current public bundle is deployed to named staging and canonical Workers;
- the Turnstile widget renders on both public Workers.

It is still not production-ready:

- anonymous CAPTCHA redemption and full guest E2E are not verified;
- custom SMTP and GitHub OAuth are not enabled/verified;
- tenant isolation is application-enforced; database RLS/private-schema
  isolation is absent;
- the free topology has no separately deployed worker;
- bundles are not signed or promoted through an append-only release system;
- load, backup/restore, fault, accessibility, privacy, and independent security
  exercises remain undone.

## 4. What Gate 1 changes

The verified local Gate 1 implementation adds the missing generic compilation seam:

- a pinned `source-aware` compiler profile with allowed destinations,
  transforms, category/enforcement routes, and fail-closed validation;
- document authority owner/status/effective/supersession/scope metadata;
- rule provenance typed as source-anchored or reviewer-authored guidance, with
  reviewer, rationale, and offset-aware `reviewed_at` required for the latter;
- exact verification of source quote, line range, UTF-8 byte range, document
  hashes, parser, and normalizer identity;
- append-only versioned placement decisions with optimistic updates;
- destinations for prompt kernel, skill, knowledge, pre-tool policy, tests,
  human review, and unsupported material;
- generated spans linked to rule revision, placement version, source anchors,
  artifact hash, and exact line/byte ranges;
- `skills/<scope>/SKILL.md` as a primary compiled artifact;
- routing, preservation, unsupported, compilation-metric, source-map, and pinned
  input artifacts;
- separate measurements for baseline always-loaded context, compiled kernel,
  skills, knowledge, machine-enforced artifacts, expected task context, and
  total bundle size;
- protected-literal checks for negations, thresholds/durations, quoted values,
  tool names, and boundary/exception language;
- `behavioral_fidelity: not_measured` in both preservation and metric contracts;
- an Acme appointment source pack using the same schemas/compiler path as
  Northstar.

The Acme pack includes a substantial source `SKILL.md`, current policy, stale
SOP, baseline prompt, style and knowledge references, strict tool schemas, and
synthetic state. Its current policy requires verified identity, a trusted IANA
timezone, a weekday `[09:00, 17:00)` customer-local window, and exact
confirmation for cancellations or fee-bearing changes. Maximum reschedule count
and cooldown remain pending/test-only; undefined “daylight hours” remains
unsupported.

## 5. What Gate 1 still does not prove

- No arbitrary-document or model-driven extraction operates.
- Conflicts in the fixtures are manually asserted and human-resolved, not
  discovered by Z3.
- Structural preservation checks are not semantic equivalence or behavioral
  fidelity.
- The appointment runner is still deterministic fixture evaluation, not a live
  scheduling integration.
- Temporal count/cooldown declarations are not executable temporal monitors.
- No Qwen/Ollama/vLLM path or live model/tool loop operates.
- No policy mutation score exists.
- Tau data sync does not execute the upstream benchmark.
- No customer-facing `aletheia check` contract or production dispatcher SDK is
  claimed unless separately verified after this review.
- The complete local browser checkpoint passed; no hosted Gate 1 deployment is
  implied.

## 6. Current residual risks

1. The generic compiler must remain free of Northstar/refund/appointment
   semantic branches; fixture content belongs in domain packs and seed code.
2. Every active clause needs one explicit disposition. Missing or unknown
   placement/profile values must fail compilation.
3. Approved source-anchored rules must fail closed on missing, shifted, or
   forged anchors. Reviewer-authored guidance needs named reviewer and rationale.
4. High/critical machine-decidable rules need both guard and approved test
   placement or a precise build failure.
5. Generated scaffold must remain distinguishable from rule-derived spans;
   test-generated span markers are explicitly `compiler_scaffold`.
6. Legacy declarative `rule/source/boundary coverage` must not be represented as
   observed evaluator coverage; use `declared_*_linkage` unless actual runtime
   rule telemetry is added.
7. Old builds and runs must remain immutable when sources, rules, placements,
   profiles, or current tests change.
8. Documentation must keep local Gate 1 completion separate from the deployed
   `147448a` public site and from behavioral/production claims.

## 7. Product assessment

### Demonstrated value

- A reviewer can inspect exact source evidence and choose an authority winner.
- A deterministic build can route reviewed clauses into explicit artifacts.
- A covered tool proposal can be blocked before fixture mutation.
- The build and evidence records are content-digested and inspectable.

### Product hypothesis under test

- Teams have sufficiently fragmented or bloated instruction sources for
  refactoring and authority review to matter.
- A routing/provenance ledger saves material engineering or policy-owner time.
- A smaller always-loaded kernel plus scoped content improves cost or behavior in
  actual agents.
- Buyers value a release report enough to adopt a PR/CI gate.

These hypotheses require interviews, redacted customer artifacts, workflow
observation, and later controlled evaluations. The current mentor evidence is a
strong anecdotal signal, not market validation.

## 8. Go/no-go decision

**Accept Gate 1 as locally complete. Stop before Gate 2.**

The recorded local checkpoint satisfies the following ongoing regression
contract: Northstar and Acme both pass the same generic compile path;
deterministic cross-process reproduction, exact
source-span resolution, placement/disposition invariants, stale-source
exclusion, ambiguous-clause exclusion, protected-literal checks, UI inspection,
migrations, generated contracts, and the complete existing Gate 0 regression
suite all pass.

After that checkpoint, the next decision is whether bounded Z3 analysis is the
highest-value Gate 2 experiment. Do not make temporal monitors, mutation
testing, local models, live evaluation, tau execution, or enterprise control
planes part of the Gate 1 completion claim.

## 9. Changelog from v1

- Replaced repository-unavailable/self-reported language with an inspected
  repository and explicit working-tree boundary.
- Replaced obsolete “no auth/tenancy/deployment” claims with the exact Gate 0H
  status.
- Removed repaired Gate 0 defects from the active blocker list.
- Corrected the frontend/hosting stack: the product uses its existing custom
  design system and intentionally uses Supabase Auth/Postgres while preserving
  SQLAlchemy/service boundaries.
- Reframed the product around source-aware refactoring and prompt/skill
  compilation.
- Moved Gates 2–8 out of immediate implementation scope.
- Added the Acme second-domain and honest structural-preservation boundary.
