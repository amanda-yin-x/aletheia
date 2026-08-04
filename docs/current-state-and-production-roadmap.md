# Aletheia current state and production roadmap

**Snapshot date:** 2026-08-03  
**Audience:** product, engineering, security reviewers, design partners, and contributors  
**Scope:** what is built, what has been verified, what still needs hosted
verification, and what remains for a production-capable system

This is an engineering assessment, not launch copy. It does not turn fixture
results into claims about live models, customer traffic, security
certification, regulatory compliance, uptime, or market validation.

## 1. Status vocabulary

| Status | Meaning |
|---|---|
| **Operating** | A connected path works in the stated environment and is more than a class, endpoint, or deployment seam. |
| **Fixture** | A connected path works only with bundled deterministic/synthetic data, scripted trajectories, or in-memory evaluation tools. |
| **Interface only** | A protocol, class, command shape, or explicit failure seam exists, but the named integration does not operate. |
| **Configuration only** | Deployment/configuration exists, but the external service or complete integration is not provisioned and verified. |
| **Unverified** | Implementation exists, but the final verification gate or required external end-to-end check has not passed. |
| **Absent** | No operating implementation exists. |

These are the canonical statuses used by `docs/capabilities.json`. Focused test
results are supplementary evidence; they do not create a second status
vocabulary or make hosted/deployment gates pass.

## 2. Executive assessment

Aletheia is now two substantial pieces joined in one repository:

1. A polished, deterministic policy-CI workflow for the Northstar Retail
   refund domain.
2. An implemented hosted control-plane path using Supabase Auth, a Cloudflare
   same-origin web boundary, authenticated FastAPI tenancy, PostgreSQL
   migrations, and durable operation contracts.

The deterministic product slice can:

- preserve controlled source documents, exact source spans, and hashes;
- represent source-linked, versioned policy rules;
- surface known conflicts and ambiguity for human review;
- block compilation while critical findings remain unresolved;
- compile approved rules into prompt, workflow, knowledge, tool-policy, test,
  source-map, and manifest artifacts;
- pin the runtime domain/lifecycle and validate proposed tools against complete
  Draft 2020-12 schemas before evaluation or execution;
- evaluate bounded scope, requirements, correlated approvals, exceptions, and
  exact USD minor-unit thresholds with fail-closed unknowns;
- execute the bundled fixture suite across baseline, compiled, and guarded arms;
- compute rule, normative-source, and guarded-boundary coverage and reject
  unclassified critical rules at the release gate;
- distinguish tool proposal, policy decision, execution, result, and state
  mutation in traces;
- demonstrate that the covered `$200.01` refund is routed for approval before
  state mutation;
- export a limitation-aware Markdown/JSON evidence report.

The hosted control plane can:

- keep the landing page public while protecting product routes;
- authenticate by email magic link, email OTP, or GitHub through Supabase;
- accept only browser-bound PKCE authorization codes at the Auth callback and
  reject portable raw token-hash links;
- send a Turnstile token on email auth and prevent token reuse;
- refresh session cookies before protected rendering;
- send browser API calls only through a same-origin Cloudflare route;
- enforce exact mutation Origin and double-submit CSRF validation;
- add a verified Supabase bearer JWT and server-only origin token to Render
  requests;
- validate JWT algorithm, key ID, issuer, audience, expiry, subject, role, and
  anonymous-user status in FastAPI;
- default the API to fail-closed production settings and reject hosted document
  uploads before route dispatch or multipart body parsing;
- provision a personal workspace/project idempotently for each authenticated
  subject;
- scope projects and all dependent resources through workspace membership;
- submit build/run work through an idempotent `OperationOut` contract;
- poll operation status and navigate only after validating the returned
  resource type, identifier, and project relationship;
- recover expired worker leases and dead-letter exhausted work.

The repository also defines separate production and staging Cloudflare Worker
bindings with deployment preview URLs disabled. Its Postgres migration revokes
table privileges from the Supabase `anon` and `authenticated` roles; a real
local PostgreSQL 14 test passed that current/default privilege boundary and the
queued operation lifecycle. Neither configuration is evidence that the current
Workers or target Supabase database have been deployed or verified.

That is a credible hosted architecture, but not yet a hosted product. The new
external Supabase, Render, and Cloudflare configuration has not been provisioned
and verified together. There is also a meaningful difference between tenant
aware and production multi-tenant: the former is implemented in FastAPI query
scopes; the latter still needs database isolation, team administration,
operational controls, security testing, and a complete audit model.

## 3. Current system map

```text
                             public landing
Browser ─────────────────────────────────────────► Cloudflare Next.js
   │                                                    │
   └─ protected route ─► Supabase Auth ─► session ──────┤
                                                        │
                             same-origin /api/v1/* ─────┘
                                      │ JWT + origin token
                                      ▼
                                  Render FastAPI
                                      │ membership-scoped SQL
                                      ▼
                                Supabase Postgres

FastAPI / Typer CLI / worker
              │
              └─ shared domain services
                    ├─ source + rule review
                    ├─ deterministic compiler
                    ├─ fixture policy interpreter
                    ├─ labelled-arm runner
                    └─ evidence reporting
```

## 4. Detailed capability inventory

### 4.1 Public landing and product explanation

**Status:** Operating locally; current hosted revision unverified

The public landing page explains the user pain through one refund scenario. It
contains a source-linked policy trace, with/without-gate comparison, four-stage
workflow, evidence boundary, responsive navigation, keyboard command palette,
reduced-motion behavior, and CTA into `/demo`.

It no longer reads protected project data. Every product CTA enters the
authenticated bootstrap path.

Remaining work:

- deploy the current revision to the canonical hostname;
- test real conversion and comprehension with design partners;
- add privacy, terms, security contact, and service-status links before a broad
  launch;
- instrument consent-aware product analytics.

### 4.2 Authentication and session lifecycle

**Status:** Unverified hosted integration; focused local component checks exist

Implemented web paths:

- `/login` with GitHub and email;
- Supabase PKCE callback at `/auth/callback` that accepts only an authorization
  `code` and rejects a portable raw `token_hash` callback;
- email magic link and manually entered OTP;
- Turnstile token forwarding for email requests;
- mandatory Turnstile reset/remount after every attempt because tokens are
  single-use;
- safe relative return-path validation;
- session-cookie refresh before protected rendering;
- protected layouts for demo, projects, runs, reports, and scenario results;
- logout with local Supabase sign-out and browser cache clearing;
- account display through `GET /api/v1/me`.

Security properties:

- protected server rendering calls `getClaims()`, not an unverified cookie
  decode;
- refreshed cookies are written to both the current request and browser
  response;
- explicit local bypass is loopback-only; the no-configuration fallback exists
  only in a non-production development server;
- production fails closed when Supabase configuration is incomplete;
- production requires HTTPS Supabase and site URLs plus Turnstile, while the API
  proxy also requires an HTTPS origin and server-only origin credential;
- auth responses use private/no-store caching.

Remaining work:

- provision Supabase Auth, GitHub OAuth, Turnstile, and custom SMTP;
- verify enterprise email scanners and link-tracking do not consume or rewrite
  single-use links;
- add MFA or step-up authentication for high-risk administration;
- add session/device management, forced revocation, account deletion, and
  recovery UX;
- define user lifecycle, support, abuse, and privacy processes.

### 4.3 Same-origin web security boundary

**Status:** Unverified hosted integration; focused local route checks exist

The catch-all Cloudflare route proxies `/api/v1/*` to the configured FastAPI
origin. It:

- rejects absolute or invalid traversal paths;
- ignores client-supplied Authorization and origin-token headers;
- verifies the Supabase user before reading the access token;
- injects `Authorization: Bearer ...` and `X-Aletheia-Origin-Token` server-side;
- requires exact Origin, double-submit CSRF, and acceptable Fetch Metadata for
  browser mutations;
- strips hop-by-hop and upstream cookie headers;
- streams response bodies, including report downloads;
- rewrites unsafe upstream `Location` origins;
- uses private/no-store caching;
- retries transient gateway failures only within bounded rules.

The browser therefore sees one application origin. FastAPI remains reachable
on its Render hostname, but a production caller still needs both the shared
origin token and a valid user JWT.

Remaining work:

- rotate the origin token through a rehearsed process;
- add Web Application Firewall/rate-limit rules at Cloudflare and application
  quotas in FastAPI;
- verify request IDs and redaction across both services;
- perform independent CSRF, SSRF, request-smuggling, cache, redirect, and
  authentication tests.

### 4.4 Accounts, workspaces, and tenancy

**Status:** Locally verified application boundary; hosted two-user and database
enforcement unverified

The schema now includes:

- `user_accounts` keyed by the Supabase subject;
- `workspaces` with a globally unique slug and creator;
- `workspace_members` with owner/admin/editor/viewer roles;
- `workspace_id` on projects;
- workspace/project/requester ownership on jobs;
- per-project uniqueness for project slugs, build hashes, and operation keys.

`POST /api/v1/workspaces/bootstrap` creates or reuses the subject's first
workspace and seeds one personal Northstar project. The derived workspace slug
includes a subject hash; it is not a shared fixed slug. Repeated bootstrap is
idempotent.

Every resource lookup joins back to workspace membership. Unauthorized IDs are
returned as not found to reduce enumeration. Write routes require owner, admin,
or editor; workspace reset requires owner/admin.

Migration `0002` conditionally revokes every current table privilege and the
migration user's default table privileges in `public` from Supabase's `anon`
and `authenticated` roles. A real local PostgreSQL 14 integration test creates
those roles, checks each current table/privilege, and verifies a
post-migration probe table inherits the denial. This is useful coarse Data API
denial evidence, but it is not per-tenant isolation and does not establish the
actual target Supabase grants, ownership, exposed schemas, or API behavior.

Remaining work:

- PostgreSQL RLS or a hardened private-schema/grant model. Current tenant
  isolation is application-enforced, not database-enforced;
- apply the migration to the target Supabase database, inspect its actual roles
  and grants, and prove the Data API cannot expose application tables before
  relying on the configured revocations;
- invitation, membership, role-change, removal, ownership transfer, and
  workspace deletion flows;
- organization/domain policy, SSO/SAML, SCIM, service accounts, and API keys;
- tenant-aware quotas, retention, encryption-key strategy, export, deletion,
  and legal holds;
- adversarial hosted tests using two real Supabase users.

### 4.5 Source records and ingestion

**Status:** Fixture viewer; local ingestion API operating; hosted ingestion absent

Working today:

- normalized UTF-8 text records with separate original-byte and normalized-text
  SHA-256 digests;
- name, MIME type, version, line count, token estimate, parser/normalizer name
  and version, locator strategy, and origin metadata;
- exact line-span and quote verification;
- plain-text/Markdown/JSON/YAML and text-based PDF parsing with size limits in
  local non-demo mode;
- source viewer with linked rules/findings.

Hosted mode intentionally keeps uploads disabled through `DEMO_MODE=true`.
FastAPI's production request middleware also recognizes the document-upload
path and rejects it after the origin credential and bearer-header checks but
before route dispatch or multipart body parsing. The local oversized-stream
test confirms that none of those rejection paths consume the request body.

Not implemented:

- production upload UI and object storage;
- malware scanning, DLP, PII classification, OCR/scanned-PDF or DOCX extraction, URLs,
  crawling, SaaS connectors, sync jobs, deduplication, or deletion/retention;
- general source trust, effective-date, jurisdiction, and ownership model.

### 4.6 Rule review and findings

**Status:** Fixture; no general analyzer

The UI/API support source-linked rules, exact evidence, bounded condition edits,
approve/reject, finding resolution notes, and a critical finding build gate.
The seed contains source-linked fixture assertions for 30/60-day and `$200`/`$250`
conflicts plus duplicate,
ambiguity, and missing-fact examples.

Not implemented:

- general contradiction, overlap, duplicate, missing-fact, temporal, and
  reachability analysis for arbitrary documents;
- reviewer assignment, comments, notifications, escalation, two-person
  approval, appeals, effective dates, policy ownership, and separation of duty;
- model-backed extraction. The live extractor class remains an explicit stub.

### 4.7 Deterministic compiler

**Status:** Fixture

Compilation currently produces:

- `prompt-kernel.md`;
- `workflows/refunds.md`;
- `knowledge/refund-reference.md`;
- `policies/tool-policy.json`;
- `tests/regression.yaml`;
- pinned tool and fact fixtures;
- pinned source, rule, and finding inputs;
- `source-map.json`;
- `manifest.json`;
- bundle `README.md`.

The manifest records exact source hashes and versions, rule revisions, test
digests, compiler/runtime versions, pinned tool/fact digests, findings,
serialization rules, artifact hashes, and limitations. Its exact canonical
bytes are the build root; it hashes every other emitted artifact and documents
why it excludes itself. Focused tests reproduce equivalent roots byte-for-byte.
Build submission also captures an input fingerprint and fails if mutable inputs
change before the operation executes.

`InputManifest`, `BuildManifest`, `TestCaseSpec`, policy, dataset, trace, and
evidence-report models now validate the emitted build/evidence schema v0.3
structures before they are stored or consumed. The exporter produces their
JSON Schemas for the CI drift check.

Correctness gaps:

- prompt/workflow/knowledge templates contain Northstar-specific prose;
- source maps identify contributing rules but do not map every output span to an
  exact source anchor;
- artifacts are JSON columns, not append-only content-addressed objects;
- content hashes prove identity, not publisher authenticity; bundles are not
  signed or transparency-logged;
- no environment promotion, activation, canary, rollback, compatibility, or
  runtime distribution protocol exists.

### 4.8 Tests, runner, traces, and reports

**Status:** Fixture

The build-pinned Aletheia-authored refund cases run across:

1. `baseline_unenforced`;
2. `compiled_unenforced`;
3. `compiled_enforced`.

Each case starts from deep-copied state. Traces separate proposal, policy
evaluation, block/approval, execution, result, and state change. Metrics include
task success, attempted/executed violations, false blocks, exact assertion
coverage, computed rule/source/boundary coverage, unclassified critical rules,
and final state hashes. Tokens and cost correctly remain unavailable in fixture
mode.

The runner verifies the build root and every stored artifact digest before it
loads the build-pinned policy, test specifications and trajectories, tool
registry, and fact metadata. Scenario results store stable test snapshots.
Reports use schema v0.3 and retain exact source/test/tool/fact/build/run hashes,
fixture provenance, arms, metrics, limitations, and a self-verifying report
digest in Markdown/JSON exports.

The pinned runtime manifest also fixes the domain and lifecycle used for policy
evaluation. Before a fixture adapter can run, each proposed tool call is
validated against its pinned Draft 2020-12 JSON Schema, including nested value
types and `additionalProperties: false`. Northstar amounts are represented as
exact `{currency: "USD", minor_units}` objects. The bounded interpreter handles
tool/domain/lifecycle scope, fact and prior-event requirements, correlated
approvals, exceptions, `not_applicable`, and fail-closed `indeterminate`
decisions.

Correctness and product gaps:

- trajectories are checked-in scripts, not live model behavior;
- covered tools are in-memory evaluation functions, not transactional staging
  integrations;
- a live `TestCase` row is still used as relational FK mapping; run, trace, and
  report evidence labels come from `test_snapshot`;
- operation fingerprints detect changed inputs, but compile capture/execution
  still need a complete transaction boundary against TOCTOU races;
- schema and policy validation are bounded to the build-pinned fixture runner;
  no customer dispatcher or production enforcement SDK consumes these bundles;
- fact values do not yet come from a typed fact catalog, money is currently
  USD-only, and generic timezone, operating-window, cooldown, or persisted
  temporal-monitor semantics are absent;
- the compatibility approval path is still Northstar-shaped: it correlates
  exact order/amount values, but older fixture approvals need not carry a
  mandatory tool/rule identity;
- no repeated stochastic trials, uncertainty, calibrated judges, human labels,
  challenge-set lifecycle, or incident-to-regression workflow exists;
- reports are unsigned and lack a trusted timestamp, actor identities, runtime
  deployment receipt, dependency provenance, retention, revocation, and
  auditor/SIEM integrations.

### 4.9 Operations and worker

**Status:** Locally verified; hosted topology uses inline work

Build and run submission return HTTP `202`, `Location`, and:

```text
OperationOut
  id, workspace_id, kind, status, progress
  resource_type, resource_id
  attempt_count, max_attempts
  error, created_at, updated_at
```

Modeled states are `queued`, `running`, `succeeded`, `failed`,
`dead_lettered`, and `cancelled`. The frontend also fails safely for compatible
future terminal states such as expired/timed-out.

Implemented reliability controls:

- idempotency keys and request fingerprints;
- operation input fingerprints;
- one running operation per project;
- PostgreSQL `FOR UPDATE SKIP LOCKED` claims;
- owner and lease expiry;
- lease heartbeat while an owned worker job is executing;
- expired lease recovery;
- maximum attempts and dead-lettering;
- retry on unexpected worker exceptions;
- graceful worker shutdown;
- typed frontend polling and resource validation;
- an 85-second wake/retry window for only idempotent bootstrap/build/run calls.

Remaining work:

- Render Free is configured with `DEMO_INLINE_JOBS=true`; a separate production
  worker is not deployed;
- there is no cancel endpoint despite the modeled cancelled state;
- retry backoff/scheduling is polling-based rather than a queue scheduler;
- no dead-letter administration, replay UI, operation logs, alerts, or SLOs;
- analysis and test-generation operations remain placeholders.

### 4.10 API, CLI, migrations, and packaging

**Status:** Mixed — local paths operating, hosted integrations unverified/configuration only

Implemented qualities:

- FastAPI `/api/v1` resources and stable error envelopes;
- health/readiness probes and request IDs;
- `ENVIRONMENT=production` as the API default, with explicit local/test opt-in;
- fail-closed production PostgreSQL/TLS, Supabase, web-origin, JWT, and
  origin-secret requirements on the product boundary;
- pre-routing origin/bearer checks and hosted document-upload rejection;
- local OpenAPI and production docs shutdown;
- Alembic baseline plus tenancy/operation, evidence, and document-provenance
  migrations;
- PostgreSQL advisory lock helper for controlled migrations;
- async runtime URL and synchronous migration URL normalization;
- bounded SQLAlchemy pool settings;
- Typer local workflow and worker commands;
- locked Python and Node dependencies;
- Dockerfiles, Compose, Render blueprint, Wrangler/OpenNext, and GitHub Actions;
- a PostgreSQL CI job that upgrades an empty database and exercises bootstrap,
  build, run, operation polling, current/default privilege denial for the
  `anon`/`authenticated` roles, and downgrade cleanup;
- explicit production and named staging Worker environments with deployment
  preview URLs disabled.

Remaining work:

- a trusted migration step for the actual Supabase database. Render Free does
  not provide the paid pre-deploy command path used for migrations;
- clean-image Compose and Render container smoke tests;
- pagination, stable cursors, quotas, request-size budgets per endpoint, and
  webhook/event delivery;
- structured telemetry, exception reporting, traces, metrics, dashboards,
  alerting, runbooks, backups, restore drills, and disaster recovery;
- a complete CSP review for the Next.js application and any future third-party
  integrations. FastAPI already separates a strict hosted API policy from its
  localhost development policy.

### 4.11 Optional live adapters and tau2

**Status:** Live adapters interface only; tau sync operating; tau execution absent

`RuleExtractor` and `AgentAdapter` boundaries exist, but live classes fail
explicitly rather than silently falling back. The tau2 sync verifies pinned
source data and provenance; it does not execute or score the benchmark.

No live quality, latency, token, cost, safety, or benchmark claim is supported.

## 5. Verification snapshot

### Locally verified for the current web implementation

- ESLint passed.
- Strict TypeScript passed.
- Vitest passed 32 tests across ten files.
- Next.js 16 production build passed.
- Cloudflare binding type generation passed without a committed diff.
- OpenNext Cloudflare bundle generation passed.
- Wrangler dry-runs passed for both the production and named staging Workers.
- Playwright passed all five Chromium flows against a dedicated migrated and
  reset SQLite database, covering landing/CTA, reduced motion, responsive
  widths, conflict choice, compile, run, trace, report, and export.
- Focused tests cover session-cookie propagation, mutation security, safe
  redirects, code-only PKCE exchange/raw-token rejection, API proxy credential
  filtering, every modeled Operation terminal state, conflict payloads,
  API-derived run presentation, and Turnstile token reset.

### Locally verified backend and configured CI coverage

- byte-reproducible manifest roots and complete non-root artifact hashing;
- build-pinned policy/test/tool/fact execution and stable test snapshots;
- strict Draft 2020-12 proposal validation before policy evaluation or
  execution, including wrong types and unexpected nested fields;
- exact USD minor-unit fixture arithmetic and predicates;
- pinned runtime domain/lifecycle scope, requirements, correlated approvals,
  exceptions, and fail-closed outcomes;
- explicit assertions for previously vacuous fixture cases;
- computed rule/source/boundary coverage and critical-unclassified gates;
- aligned build/evidence schema v0.3 contracts, report provenance hashes, and self-verifying
  digest;
- worker lease heartbeat;
- hosted JWT validation, fail-closed configuration, and pre-routing upload
  rejection paths;
- bootstrap idempotency and reset;
- tenant scoping and cross-project rejection;
- operation idempotency, status, resource contract, input staleness, per-project
  concurrency, lease recovery, and dead-lettering;
- empty SQLite migration lifecycle;
- configured GitHub Actions PostgreSQL integration job.

The settled backend tree passed Ruff, strict mypy over 28 source files, and all
111 backend tests across two local runs: 110 passed with the Postgres-marked
case skipped in the default run, and that real PostgreSQL 14 case passed
separately. The settled web, build, production/staging Worker dry-run, and clean
five-flow browser checks also passed locally. The repository quality,
secret-scan, and PostgreSQL 17 jobs then passed in [GitHub Actions run
#30867243068](https://github.com/amanda-yin-x/aletheia/actions/runs/30867243068)
on implementation commit `5d45a776407955f86227e1890900d9857196a007`.

The focused evidence-correctness gate passed Ruff, strict mypy, 33 targeted
tests, and the SQLite `0003` upgrade/downgrade/backfill/Alembic-check lifecycle.
That is narrower than the final repository-wide CI claim.

### Locally verified PostgreSQL integration

The real PostgreSQL 14 marker passed against an empty database. It migrated
through head, verified current and default table-privilege revocation for
locally created `anon` and `authenticated` roles, bootstrapped a workspace,
processed queued build and run operations through the worker, polled their
results, and cleaned up through downgrade. The GitHub Actions equivalent also
passed against PostgreSQL 17. Neither result implies that the migration or
privilege boundary has run successfully on the target Supabase database.

### Pending hosted verification

- external Supabase, Render, Turnstile, OAuth, and SMTP provisioning;
- target Postgres migration and restore test;
- real Supabase role/grant inspection and Data API denial testing;
- current Cloudflare revision deployment;
- named staging Worker deployment and smoke test;
- real email, OTP, OAuth, refresh, and logout flows;
- real two-user tenant isolation;
- Render sleep/wake recovery;
- report streaming through both network hops;
- end-to-end browser suite through the hosted Cloudflare/Render/Supabase path;
- load, soak, fault-injection, security, privacy, and accessibility audits.

Playwright now starts the API against a dedicated SQLite database after an
Alembic upgrade and reset seed. All five local Chromium flows pass. This is
strong local integration evidence, but it is not evidence of hosted success.

## 6. Free-tier operating boundary

The target free topology is an evaluation environment:

- Render can sleep after 15 idle minutes and take about a minute to wake;
- Render's filesystem is ephemeral and the Free service cannot scale;
- Cloudflare Workers Free has a small CPU budget for dynamic SSR/auth work;
- Supabase Free can pause for inactivity and has limited database and backup
  characteristics;
- auth email delivery needs custom SMTP for real users;
- combined Supabase and Render cold starts can exceed one service's advertised
  wake time.

The UI's “Waking your workspace…” state and bounded retry are honest recovery
UX, not an availability guarantee. See [deployment.md](deployment.md) for
current official platform links and the exact limits.

## 7. Priority roadmap to a production-capable system

### P0 — Complete and verify the hosted foundation

1. Provision separate development/staging Supabase projects and a Render API.
2. Configure custom SMTP, GitHub OAuth, Turnstile, exact redirect URLs, and
   restrictive Auth settings.
3. Decide and implement the database boundary: RLS on every exposed table or a
   private non-exposed schema with least-privilege database roles. Verify it
   independently of FastAPI.
4. Apply Alembic migrations through a trusted, repeatable CI/admin job and test
   backup/restore before storing important data.
5. Deploy the current Cloudflare revision with server-only API variables and a
   high-entropy origin token shared with Render.
6. Run the complete hosted smoke test in [deployment.md](deployment.md),
   including two-user cross-tenant attempts and Render sleep/wake.
7. Add production telemetry and secret-redaction checks across both services.
8. Establish a paid-plan decision and SLO before inviting users; Free tiers are
   not an uptime target.

Exit gate: every status in the hosted smoke-test matrix is recorded with commit,
environment, timestamp, and evidence; rollback and secret rotation are tested.

### P1 — Finish release integrity beyond the fixture invariants

Focused checks now cover byte-reproducible build roots, complete non-root
artifact hashing, build-pinned runner inputs, stored test snapshots, aligned
build/evidence schema v0.3 validation, and report digests. The remaining work is:

1. Keep generated JSON Schemas and OpenAPI drift-checked in final CI.
2. Close the operation fingerprint capture/execution transaction boundary.
3. Store bundles in append-only content-addressed object storage, sign them, and record a
   transparency/audit receipt.
4. Add release environments, promotion, activation, rollback, and compatibility
   gates.
5. Deploy a separate worker with scheduled retry/backoff, cancellation,
   dead-letter administration, metrics, and alerts; the local worker already
   extends owned leases with a heartbeat.

Exit gate: a build can be reproduced byte-for-byte; changing current rules or
tests cannot change an old build's run or report; a signed bundle can be
promoted and rolled back.

### P2 — Become a usable multi-user policy product

1. Team invitations, role administration, ownership transfer, and offboarding.
2. Reviewer identity, comments, assignment, notifications, two-person approval,
   escalation, override/appeal, and approval inbox.
3. Production source ingestion with object storage, malware scanning, DLP,
   versioning, retention, and initial connectors.
4. General policy analysis over a constrained schema with explicit confidence,
   evidence, and human confirmation—never unrestricted generated code.
5. Search, saved views, audit explorer, environment/release UI, and settings.
6. Usage budgets, quotas, billing/admin controls, privacy workflows, and tenant
   export/deletion.
7. WCAG 2.2 AA audit, localization, and timezone/effective-date support.

Exit gate: a design partner can onboard a team, import consented non-production
policies, review changes with separation of duty, and promote a signed bundle
without developer database access.

### P3 — Add a bounded enforcement data plane

1. A small customer-side SDK/proxy that verifies signed bundles and fails closed
   for explicitly covered high-risk operations.
2. Transactional adapters to sandbox/staging tools with idempotency,
   reconciliation, and approval tokens bound to tool, arguments, actor, expiry,
   and single use.
3. Shadow mode against consented traffic with redaction and no external
   mutation.
4. Repeated live-model trials, calibrated judges, human labels, uncertainty,
   latency/cost accounting, and incident-derived regression cases.
5. Controlled canary enforcement with kill switch, rollback, SLOs, and on-call
   ownership.

Exit gate: the first live claim is limited to a named model, tool set, policy
bundle, dataset, environment, time range, sample size, and confidence interval.

## 8. Recommended product boundary

Keep Aletheia centred on reviewed business policy, deterministic pre-tool
decisions, and release evidence. Do not broaden into generic prompt management,
unbounded user-authored policy code, or passive observability before the release
integrity and enforcement boundaries are reliable.

The most credible sequence remains:

```text
deterministic local evaluation
  → authenticated hosted design-partner workspace
  → private shadow pilot with mutations disabled
  → signed-bundle guarded canary for a narrow tool set
  → broader production only after measured evidence and rollback drills
```

## 9. Production capability boundary

Aletheia is not production-capable merely because its UI and API are online. A
complete first production system requires:

- externally verified authentication and tenant isolation at both application
  and database boundaries;
- reliable source ingestion and review ownership;
- reproducible, versioned, build-pinned builds and runs;
- signed artifacts and a release/rollback lifecycle;
- durable approvals and transactional enforcement adapters;
- real audit identities and retention;
- worker recovery, cancellation, observability, backups, and incident response;
- privacy, security, accessibility, and operational reviews;
- a bounded, measured pilot whose claims match its evidence.

Until those conditions are met, the accurate description is: **a deterministic
fixture policy-CI workflow with broad local and repository-CI verification,
pending hosted verification.**
