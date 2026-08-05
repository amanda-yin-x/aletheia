# Aletheia current state and production roadmap

**Snapshot date:** 2026-08-04  
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

### Feature-gate status

| Feature gate | Canonical status | Boundary |
|---|---|---|
| Gate 0 — local deterministic foundation | **Operating/Fixture complete in its settled Northstar scope** | The no-key source-review/build/run/trace/report regression floor. |
| Gate 0H — hosted preview/hardening | **Unverified/in progress** | Permanent-user staging passed; anonymous Turnstile redemption and complete guest E2E remain open. |
| Gate 1 — source-aware policy refactoring/compiler | **Fixture complete in verified local two-domain scope** | API/database/frontend/packaging/browser checks include the two-domain/fresh-process path. Not deployed. |
| Gates 2–8 | **Absent** | Provider interfaces, tau data sync, schemas, or planned commands are not operating implementations. |

Feature gates describe product behavior. The later P0–P3 roadmap describes
production maturity. A production task does not silently complete a feature
gate, and a local feature does not silently pass a hosted gate.

The Gate 1 row describes the local working tree. It is not part of the deployed
public `147448a` Worker bundle unless a later release is explicitly verified and
promoted.

## 2. Executive assessment

Aletheia is now three substantial pieces joined in one repository:

1. A polished, deterministic policy-CI workflow for the Northstar Retail
   refund domain.
2. An implemented hosted control-plane path using Supabase Auth, a Cloudflare
   same-origin web boundary, authenticated FastAPI tenancy, PostgreSQL
   migrations, and durable operation contracts.
3. A verified local Gate 1 source-aware compilation implementation with a pinned generic
   compiler profile, explicit placement decisions, exact generated-span
   provenance, structural preservation/context metrics, and a second synthetic
   Acme appointments corpus.

The deterministic product slice can:

- preserve controlled source documents, exact source spans, and hashes;
- represent source-linked, versioned policy rules;
- surface known conflicts and ambiguity for human review;
- block compilation while critical findings remain unresolved;
- compile approved rules into a prompt kernel, scoped `SKILL.md`, knowledge,
  tool-policy, regression, unsupported-material, source-map, metrics, pinned
  input, and manifest artifacts;
- pin the runtime domain/lifecycle and validate proposed tools against complete
  Draft 2020-12 schemas before evaluation or execution;
- evaluate bounded scope, requirements, correlated approvals, exceptions, and
  exact USD minor-unit thresholds with fail-closed unknowns;
- execute the bundled fixture suite across baseline, compiled, and guarded arms;
- compute declared rule/source/boundary linkage and reject unclassified
  critical rules at the release gate;
- distinguish tool proposal, policy decision, execution, result, and state
  mutation in traces;
- demonstrate that the covered `$200.01` refund is routed for approval before
  state mutation;
- export a limitation-aware Markdown/JSON evidence report.

The verified local Gate 1 implementation additionally records document authority metadata,
source-anchored versus reviewer-authored rule provenance, append-only placement
versions, and exact source-to-generated-span links. These are deterministic
structural conformance mechanisms. `behavioral_fidelity` is explicitly
`not_measured`.

The current guest implementation includes the following intended path and
controls:

- keep the landing page and `/demo` entry public while protecting workspace
  resources;
- require Turnstile, create a signed anonymous Supabase session, and bootstrap
  an isolated Northstar workspace without an email or password;
- retain email magic link as a permanent-account path for authorized
  project-team addresses, while manual OTP and GitHub OAuth remain disabled;
- accept only browser-bound PKCE authorization codes at the Auth callback and
  reject portable raw token-hash links;
- send a Turnstile token on anonymous/email auth and prevent token reuse;
- refresh session cookies before protected rendering;
- send browser API calls only through a same-origin Cloudflare route;
- enforce exact mutation Origin and double-submit CSRF validation;
- add a verified Supabase bearer JWT and server-only origin token to Render
  requests;
- validate JWT algorithm, key ID, issuer, audience, expiry, subject, and role in
  FastAPI, accepting a signed `is_anonymous=true` subject only through the
  bounded guest path;
- default the API to fail-closed production settings and reject hosted document
  uploads before route dispatch or multipart body parsing;
- provision a personal workspace/project idempotently for each authenticated
  subject;
- scope projects and all dependent resources through workspace membership;
- submit build/run work through an idempotent `OperationOut` contract;
- poll operation status and navigate only after validating the returned
  resource type, identifier, and project relationship;
- recover expired worker leases and dead-letter exhausted work;
- apply per-subject Cloudflare thresholds of 120 general, 90 polling, and 30
  heavy requests per minute, evaluated permissively per location rather than as
  an exact global quota;
- cap mutation bodies at 64 KiB in both the Worker and API and require upstream
  response headers within 85 seconds;
- cap a guest at 30 successful writes and six live operations, deny guest reset,
  and disable hosted uploads/arbitrary project creation;
- expire guest access after seven days and clean anonymous identities older
  than 30 days at startup/every 24 hours, anchoring hosted age to
  `auth.users.created_at` and including identities that never bootstrapped the
  app, with a dry-run CLI plus fail-open alerting; and
- store normalized unique waitlist consent separately so it survives guest
  workspace cleanup.

The dedicated Supabase project and Render Free service are provisioned, the
hosted database is migrated through Alembic head, and the Data API is disabled.
Hosted inspection found zero application-table privileges for `anon` and
`authenticated`, and a transactionally created probe table inherited the same
default denial. The named Cloudflare staging Worker previously passed the
permanent-user bootstrap, two-user isolation, deterministic
build/run/trace/report, download, and direct-origin security path.

Commit `147448a` is pushed, and its exact web bundle is deployed to the named
staging Worker at `https://aletheia-staging.aletheia-web.workers.dev` as version
`3788c6b0-291c-43a9-bef3-b48aaa4a0498` and to the canonical production Worker
at `https://aletheia.aletheia-web.workers.dev` as version
`935c3c39-f63e-4041-804b-ef40431d50fc`. Live release smoke checks confirmed
`/` and `/demo` return `200`, unauthenticated `/api/v1/me` returns `401`, and
HTTP redirects to HTTPS with `308`. The current composite refund scenario and
`ALETHEIA` brand are served, and the obsolete API-boundary message is absent.
On staging and canonical production, the real Turnstile script and challenge
frame render, the UI settles in its waiting state, and the former `ready()` load
failure is gone. Automated
browsers were challenged before token redemption, so this evidence does not
establish anonymous sign-in or the complete hosted guest workflow.

That is an operating hosted preview, not a production-capable multi-tenant
service. Tenant awareness is implemented in FastAPI query scopes and protected
from browser Data API access, but the system still lacks per-tenant database
RLS, team administration, custom SMTP, GitHub OAuth, operational controls,
independent security testing, and a complete audit model.

## 3. Current system map

```text
                             public landing
Browser ─────────────────────────────────────────► Cloudflare Next.js
   │                                                    │
   └─ public /demo ─► Turnstile ─► Supabase anonymous ──┤
                                  signed session        │
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
                    ├─ source authority + rule/placement review
                    ├─ pinned generic compiler profile
                    ├─ exact generated spans + structural metrics
                    ├─ fixture policy interpreter
                    ├─ labelled-arm runner
                    └─ evidence reporting
```

## 4. Detailed capability inventory

### 4.1 Public landing and product explanation

**Status:** Deployed on staging and canonical production; public smoke verified;
guest authentication and workspace verification pending

The public landing page explains the user pain through a composite refund
scenario backed by the bundled `N-1099` case: a `$249`, nine-day,
non-returnable order, a requested gift-card destination, no matching approval,
and a retained SOP that appears to authorize the proposal. It contains a
source-linked policy trace, with/without-gate comparison, four-stage workflow,
evidence boundary, responsive navigation, keyboard command palette,
reduced-motion behavior, and CTA into `/demo`.

It no longer reads protected project data. Every product CTA enters public
`/demo`, where Turnstile and anonymous sign-in precede private bootstrap.

Remaining work:

- complete Turnstile token redemption and the connected guest workflow on the
  exact deployed revision, then record the passing evidence against both Worker
  version identifiers;
- test real conversion and comprehension with design partners;
- add privacy, terms, security contact, and service-status links before a broad
  launch;
- instrument consent-aware product analytics.

### 4.2 Authentication and session lifecycle

**Status:** Guest entry deployed; permanent-user staging path verified;
anonymous token redemption and session lifecycle pending

Implemented web paths:

- public `/demo` with a Turnstile gate and Supabase anonymous sign-in;
- `/login` with email plus feature-gated GitHub and manual OTP controls;
- Supabase PKCE callback at `/auth/callback` that accepts only an authorization
  `code` and rejects a portable raw `token_hash` callback;
- email magic link and an implemented manually entered OTP path;
- Turnstile token forwarding for guest and email requests;
- mandatory Turnstile reset/remount after every attempt because tokens are
  single-use;
- safe relative return-path validation;
- session-cookie refresh before protected rendering;
- private layouts for projects, runs, reports, and scenario results; `/demo`
  remains public so it can establish the guest session;
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

Current hosted configuration:

- Supabase anonymous sign-in is enabled and requires Turnstile;
- Turnstile-protected email magic link is enabled;
- manual identity linking is enabled, and a guest attaching a new email keeps
  the same Supabase subject and workspace;
- Supabase's default SMTP limits delivery to authorized project-team email
  addresses, so the preview is not open self-service sign-up;
- manual email OTP is disabled with `EMAIL_OTP_ENABLED=false`; and
- GitHub is disabled with `GITHUB_AUTH_ENABLED=false` until its OAuth
  application and Supabase provider are configured and verified.

The backend requires `role=authenticated` on every product JWT and accepts the
signed `is_anonymous=true` claim. This does not expose application tables to the
Supabase database `anon` role: the Data API remains disabled and all browser
product traffic still passes through FastAPI tenancy.

Supabase's native CAPTCHA integration verifies that a Turnstile challenge
succeeded, but it does not enforce the returned `action` or `hostname` fields.
The `guest_demo`, `waitlist`, and `login` action values are client-side labels.
The widget allowlist contains only canonical and staging hostnames; local work
uses local auth or Cloudflare's test key, not a localhost allowlist entry.

Remaining work:

- hosted-verify anonymous sign-in, cookie refresh, logout, expiry, and replay
  rejection on the exact deployed revision;
- configure custom SMTP and verify delivery for non-team users;
- configure and stage-verify GitHub OAuth before enabling its login control;
- define an explicit merge/recovery flow when a guest tries to attach an
  identity that already belongs to another account;
- verify enterprise email scanners and link-tracking do not consume or rewrite
  single-use links;
- add MFA or step-up authentication for high-risk administration;
- add session/device management, forced revocation, account deletion, and
  recovery UX;
- define user lifecycle, support, abuse, and privacy processes.

### 4.3 Same-origin web security boundary

**Status:** Permanent-user staging path verified; guest web boundary deployed;
anonymous proxy lifecycle pending

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

The proxy configures per-subject Cloudflare thresholds of 120 general requests,
90 job polls, and 30 heavy result/report/export requests per minute;
specialized requests also consume the general budget. Cloudflare evaluates
these per location with permissive, eventually consistent counters, so they
are abuse controls rather than exact global quotas. Missing production bindings
fail closed. The Worker streams and rejects mutation bodies over 64 KiB, while
FastAPI independently enforces the same limit before request models are
materialized. Every fetch/retry shares an 85-second deadline to receive
upstream response headers; that deadline does not time a streamed response body
after headers arrive.

The browser therefore sees one application origin. FastAPI remains reachable
on its Render hostname, but a production caller still needs both the shared
origin token and a valid user JWT.

Remaining work:

- repeat proxy, CSRF, credential-stripping, streaming, and cold-start checks
  with a signed anonymous session;
- rotate the origin token through a rehearsed process;
- tune and monitor Cloudflare rate-limit budgets, add broader WAF policy, and
  add permanent/team product quotas; the guest implementation already has
  bounded evaluation allowances;
- verify request IDs and redaction across both services;
- perform independent CSRF, SSRF, request-smuggling, cache, redirect, and
  authentication tests.

### 4.4 Accounts, workspaces, and tenancy

**Status:** Permanent-user application boundary and browser Data API denial
verified; guest paths deployed but lifecycle unverified; database RLS absent

The schema now includes:

- `user_accounts` keyed by the Supabase subject;
- `workspaces` with a globally unique slug and creator;
- `workspace_members` with owner/admin/editor/viewer roles;
- `workspace_id` on projects;
- workspace/project/requester ownership on jobs;
- per-project uniqueness for project slugs, build hashes, and operation keys.

`POST /api/v1/workspaces/bootstrap` creates or reuses the signed subject's first
workspace and seeds one personal Northstar project. This works for permanent
and anonymous identities. The derived workspace slug includes a subject hash;
it is not a shared fixed slug. Repeated bootstrap is idempotent.

Every resource lookup joins back to workspace membership. Unauthorized IDs are
returned as not found to reduce enumeration. Write routes require owner, admin,
or editor. Permanent reset requires owner/admin; guest reset is always denied.

Guest accounts also carry a locked usage ledger. Successful mutations stop at
30 and live operations stop at six. Access expires after seven days. Startup
cleanup uses `auth.users.created_at` as the hosted age source, removes
anonymous identities older than 30 days with their app data, and also removes
expired auth-only identities that never bootstrapped Aletheia. The CLI is
dry-run by default, and cleanup failure alerts without blocking readiness.

The waitlist is behind the authenticated guest/permanent API. Emails are
normalized and unique; repeat/concurrent submissions are idempotent and do not
reveal prior presence. Cleanup clears the guest user link but preserves the
consent record.

Migration `0002` conditionally revokes every current table privilege and the
migration user's default table privileges in `public` from Supabase's `anon`
and `authenticated` roles. That boundary passed both the local PostgreSQL test
and the hosted target inspection. The Supabase Data API is disabled, every
current application-table privilege for those roles is zero, a negative REST
probe is unavailable, and a transactionally created probe table inherited the
default denial. This is strong browser Data API denial evidence, but it is not
per-tenant database isolation.

Remaining work:

- PostgreSQL RLS or a hardened private-schema/grant model. Current tenant
  isolation is application-enforced, not database-enforced;
- keep the Data API disabled and recheck current/default grants after every
  migration that changes ownership, schemas, or privileges;
- invitation, membership, role-change, removal, ownership transfer, and
  workspace deletion flows;
- organization/domain policy, SSO/SAML, SCIM, service accounts, and API keys;
- permanent/team quotas, configurable retention, encryption-key strategy,
  export, deletion, and legal holds beyond the bounded guest policy;
- retain adversarial two-user checks in every staged release and extend them to
  future team/member administration.

### 4.5 Source records and ingestion

**Status:** Fixture viewer; local ingestion API operating; hosted ingestion absent

Working today:

- normalized UTF-8 text records with separate original-byte and normalized-text
  SHA-256 digests;
- name, MIME type, version, line count, token estimate, parser/normalizer name
  and version, locator strategy, and origin metadata;
- exact line-span and quote verification;
- authority owner/status, effective/supersession, and scope metadata in the
  verified local Gate 1 persistence/contracts;
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
- generalized trust/jurisdiction workflows or automated authority inference.

### 4.6 Rule review and findings

**Status:** Verified local Gate 1 fixture review/placement/provenance; no general
analyzer

The UI/API support source-linked rules, exact evidence, bounded condition edits,
approve/reject, finding resolution notes, and a critical finding build gate.
The seed contains source-linked fixture assertions for 30/60-day and `$200`/`$250`
conflicts plus duplicate,
ambiguity, and missing-fact examples.

The Gate 1 implementation distinguishes exact source-anchored rule revisions from
reviewer-authored guidance. The latter requires a named reviewer, rationale,
and offset-aware `reviewed_at`.
It also persists append-only placement decisions for prompt kernel, skill,
knowledge, pre-tool policy, test, human review, and unsupported destinations;
tenant-scoped list and optimistic-update API contracts are present. Browser E2E
verification passed in the final local suite.

The verified local frontend adds a project/domain switcher and a project-scoped
Placements route. It shows every non-superseded rule, latest placement version,
disposition, transform, destinations, reviewer/rationale, source authority, and
explicit missing/blocked/unsupported/human-review states. Updates send the
expected version and turn a `409` into an explicit refresh path. This surface is
implemented. ESLint, `tsc --noEmit`, 14 focused tests across four files, the
full 84-test/22-file Vitest suite, and a production Next.js build passed. The
focused two-domain E2E passed 1/1 and the complete fresh-isolated browser suite
passed 6/6.

Not implemented:

- general contradiction, overlap, duplicate, missing-fact, temporal, and
  reachability analysis for arbitrary documents;
- reviewer assignment, comments, notifications, escalation, two-person
  approval, appeals, effective dates, policy ownership, and separation of duty;
- model-backed extraction. The live extractor class remains an explicit stub.

### 4.7 Deterministic compiler

**Status:** Complete in verified local two-domain fixture scope; not deployed

The compiler is now profile-driven rather than a Northstar-only template seam.
Its pinned `source-aware` profile validates destinations, transform classes,
category/enforcement routing, and dispositions. Missing or unknown values,
invalid source anchors, incomplete active dispositions, and applicable
protected-literal loss fail closed.

The compiler produces:

- `prompt-kernel.md`;
- `skills/<scope>/SKILL.md`;
- `knowledge/<scope>.md`;
- `policies/tool-policy.json`;
- `tests/regression.yaml`;
- `pending/unsupported-rules.json`;
- `routing-report.json`;
- `preservation-report.json`;
- `compilation-metrics.json`;
- `source-map.json` with exact generated spans;
- pinned compiler profile, placement decisions, source metadata, rules,
  findings, tools, and facts;
- `manifest.json` and bundle `README.md`.

Exact source anchors verify quote, line range, UTF-8 byte range, raw and
normalized hashes, parser, and normalizer. Rule-derived generated spans link
the exact build/artifact range to the rule revision, placement version, and
source anchor. Reviewer-authored guidance remains attributable and cannot
masquerade as a source quote; test-generated span markers are explicitly
`compiler_scaffold` and not source-derived.

The manifest records exact pinned inputs, compiler/runtime versions, artifact
hashes, serialization rules, and limitations. Its canonical bytes form the
build root and hash every other emitted artifact. Build submission captures an
input fingerprint and rejects stale mutable inputs before execution. The
generated JSON Schemas and OpenAPI remain drift-checked contracts.

Metrics separately report baseline always-loaded, compiled kernel, skills,
knowledge, machine-enforced, expected task-context, and total-bundle sizes;
routing/source linkage; severity-weighted preservation; high/critical
guard-and-test placement; pending counts; and protected literals. Both
preservation and metric contracts state `behavioral_fidelity: not_measured`.

Northstar retail and Acme appointments use the same schemas/compiler path. The
Acme pack contains a substantial source `SKILL.md`, current policy, stale SOP,
prompt/style/knowledge references, strict tools, synthetic state, and
deterministic cases. This tests domain neutrality but is not a live scheduling
integration.

The verified build-detail surface loads the requested build inspection rather than
silently substituting another build. It shows the full bundle tree, exact
artifact hashes/downloads, numbered generated-span links to pinned source
lines, labeled compiler-scaffold/no-anchor states, the estimator and context
metric table, routing report, preservation report, and the explicit
“Behavioral fidelity: Not measured” boundary. The complete browser checkpoint
passed.

Reviewer-authored spans are rendered as an intentional **no source-anchor
claim**, not as a missing source-derived anchor, and show reviewer, rationale,
and timestamp attribution from routing-report provenance metadata.

Remaining boundaries:

- arbitrary/model-driven extraction and general conflict analysis are absent;
- deterministic structural preservation is not semantic equivalence or
  model-behavior proof;
- maximum reschedule count/cooldown in Acme remain pending/test-only, and
  undefined “daylight hours” is explicitly unsupported;
- artifacts are database JSON columns, not signed append-only release objects;
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
coverage, declared rule/source/boundary linkage, unclassified critical rules,
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
- snapshot-consuming operations and child-row mutations share the same
  `Project → child` lock order; a real two-session PostgreSQL test proves a
  competing mutation waits for the snapshot fence;
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

**Status:** Permanent-user staging path verified with inline work; guest web
release deployed but operation allowance pending hosted verification; durable
hosted worker absent

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
- an 85-second wake/retry window and response-header deadline (not a streamed
  response-body deadline);
- a `Project → child` lock fence around snapshot capture and child mutations,
  proven with two concurrent PostgreSQL sessions;
- an account-locked six-live-operation allowance for anonymous guests.

Remaining work:

- Render Free is configured with `DEMO_INLINE_JOBS=true`; a separate production
  worker is not deployed;
- there is no cancel endpoint despite the modeled cancelled state;
- retry backoff/scheduling is polling-based rather than a queue scheduler;
- no dead-letter administration, replay UI, operation logs, alerts, or SLOs;
- analysis and test-generation operations remain placeholders.

### 4.10 API, CLI, migrations, and packaging

**Status:** Mixed — local paths and permanent-user staging preview operating;
current web release deployed to staging and canonical production; guest
connected-system verification pending

Implemented qualities:

- FastAPI `/api/v1` resources and stable error envelopes;
- health/readiness probes and request IDs;
- `ENVIRONMENT=production` as the API default, with explicit local/test opt-in;
- fail-closed production PostgreSQL/TLS, Supabase, web-origin, JWT, and
  origin-secret requirements on the product boundary;
- pre-routing origin/bearer checks and hosted document-upload rejection;
- local OpenAPI and production docs shutdown;
- Alembic baseline plus tenancy/operation, evidence, document-provenance, and
  guest-access/waitlist migrations;
- PostgreSQL advisory lock helper for controlled migrations;
- async runtime URL and synchronous migration URL normalization;
- bounded SQLAlchemy pool settings;
- Typer local workflow and worker commands;
- a guest-cleanup command that is dry-run by default, plus 30-day cleanup at
  startup and every 24 hours with structured fail-open alerting;
- 64 KiB mutation-body enforcement at both Worker and API boundaries;
- locked Python and Node dependencies;
- Dockerfiles, Compose, Render blueprint, Wrangler/OpenNext, and GitHub Actions;
- a PostgreSQL CI job that upgrades an empty database and exercises bootstrap,
  build, run, operation polling, current/default privilege denial for the
  `anon`/`authenticated` roles, and downgrade cleanup;
- explicit production and named staging Worker environments with deployment
  preview URLs disabled.

The Render Free Blueprint intentionally omits `maxShutdownDelaySeconds` because
the platform rejected that field for the Free plan; Render's 30-second default
remains in effect.

Remaining work:

- move migration execution from the advisory-locked container entrypoint to a
  paid Render pre-deploy phase when the service is upgraded; the current hosted
  database is already at Alembic head;
- retain clean-image Compose and Render container smoke tests for future base
  image or entrypoint changes;
- pagination, stable cursors, permanent/team quotas, endpoint-specific budgets
  beyond the universal 64 KiB mutation cap, and webhook/event delivery;
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

### Gate 1 local completion checkpoint

Gate 1 is complete in the verified local two-domain fixture scope. The API/Gate
1 suites cover the two-domain/fresh-process compiler path, exact provenance,
contracts, migrations, and frontend unit/build behavior; packaging and browser
checks also pass. This does not change hosted or deployed status.

Final local Gate 1 evidence:

- the default API suite passed 139 tests with one skipped;
- the focused regenerated-contract/Gate 1 suite passed 31 tests;
- Ruff and mypy passed;
- SQLite Alembic upgrade/drift passed through migration `0006`;
- a fresh real-PostgreSQL migration integration passed one test with four
  deselected, then removed its temporary database;
- frontend ESLint and strict type checking passed;
- all 84 Vitest tests across 22 files passed;
- the production Next.js build passed and includes the dynamic
  `/projects/[projectId]/routing` route;
- OpenNext at compatibility date `2026-08-04`, Wrangler `4.118.0` type
  generation, root/staging deploy dry-runs, and `wrangler check startup` passed;
- the dry-runs packaged 53 assets and an 8,019.91 KiB bundle (1,665.20 KiB
  gzip), while local active startup measured 34.0 ms;
- focused two-domain Playwright passed 1/1 in 15.2 seconds;
- the complete Playwright suite passed 6/6 in 1.3 minutes using fresh isolated
  API/web ports and Next output;
- `pip-audit` and production `pnpm audit --audit-level high` reported no known
  vulnerabilities; and
- `git diff --check` is clean.

The dry-run size and startup observations do not prove hosted Gate 1 deployment,
production performance, or behavioral fidelity.
The public Workers remain on the separately recorded `147448a` bundle.
The verified Northstar and Acme build roots, 19-artifact trees, representative
source span, context metrics, demo steps, and exact claim boundary are recorded
in [the Gate 1 verification report](gate-1-verification-report.md).
The older counts below are retained as historical regression evidence and must
not be represented as the final Gate 1 count.

### Locally verified for the current web implementation

- ESLint passed.
- Strict TypeScript passed.
- In the current guest implementation, Vitest passes 71 tests across 18 files.
- Next.js 16 production build passed.
- Cloudflare binding type generation passed without a committed diff.
- OpenNext Cloudflare bundle generation passed.
- Wrangler dry-runs passed for both the production and named staging Workers.
- The settled pre-guest revision passed all five Playwright Chromium flows
  against a dedicated migrated/reset SQLite database, covering landing/CTA,
  reduced motion, responsive widths, conflict choice, compile, run, trace,
  report, and export. The current guest implementation still needs this full
  browser rerun.
- Focused tests cover session-cookie propagation, mutation security, safe
  redirects, code-only PKCE exchange/raw-token rejection, API proxy credential
  filtering, every modeled Operation terminal state, conflict payloads,
  API-derived run presentation, Turnstile token reset, per-user edge rate-limit
  categories, missing-binding failure, streaming 64 KiB body rejection, and the
  85-second upstream response-header deadline.

### Locally verified backend and configured CI coverage

- byte-reproducible manifest roots and complete non-root artifact hashing;
- build-pinned policy/test/tool/fact execution and stable test snapshots;
- strict Draft 2020-12 proposal validation before policy evaluation or
  execution, including wrong types and unexpected nested fields;
- exact USD minor-unit fixture arithmetic and predicates;
- pinned runtime domain/lifecycle scope, requirements, correlated approvals,
  exceptions, and fail-closed outcomes;
- explicit assertions for previously vacuous fixture cases;
- declared rule/source/boundary linkage and critical-unclassified gates;
- aligned build/evidence schema v0.3 contracts, report provenance hashes, and self-verifying
  digest;
- worker lease heartbeat;
- hosted JWT validation, fail-closed configuration, and pre-routing upload
  rejection paths;
- bootstrap idempotency and reset;
- tenant scoping and cross-project rejection;
- operation idempotency, status, resource contract, input staleness, per-project
  concurrency, lease recovery, and dead-lettering;
- two-session PostgreSQL proof that `Project → child` locking blocks a child
  mutation across operation snapshot capture;
- API-side 64 KiB mutation-body enforcement and periodic guest cleanup;
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

The current guest implementation passes all 116 backend tests across two local
runs: 115 in the default run and the separately executed PostgreSQL-marked
integration test.
Playwright still lists five browser flows; hosted guest verification remains a
separate release gate.

The focused evidence-correctness gate passed Ruff, strict mypy, 33 targeted
tests, and the SQLite `0003` upgrade/downgrade/backfill/Alembic-check lifecycle.
That is narrower than the final repository-wide CI claim.

### Locally verified PostgreSQL integration

The real PostgreSQL 14 marker passed against an empty database. It migrated
through head, verified current and default table-privilege revocation for
locally created `anon` and `authenticated` roles, bootstrapped a workspace,
processed queued build and run operations through the worker, polled their
results, proved the operation snapshot fence with two concurrent sessions using
the shared `Project → child` lock order, and cleaned up through downgrade. The
GitHub Actions equivalent also
passed against PostgreSQL 17. The target Supabase database has since migrated
through the same Alembic head, and its disabled Data API plus current/default
role-denial boundary passed direct hosted inspection.

### Hosted connected-system and current-release verification

- dedicated Supabase Auth/Postgres and Render services are provisioned;
- Alembic head, empty Data API schema, negative REST access, zero current
  `anon`/`authenticated` table grants, and zero probe-table default grants
  passed on the target database;
- the named Cloudflare staging Worker proxies to Render with the matching
  server-only origin credential;
- external Supabase JWT validation and missing/invalid origin or bearer
  rejection passed;
- two hosted identities received distinct personal workspaces and could not
  access one another's resources; and
- the complete deterministic review, compile, 16-case/three-arm run, blocked
  trace, report, and streamed Markdown export path passed against hosted
  Postgres.

Those connected lifecycle checks used a permanent-user staging session. The
current commit `147448a` web bundle is now live as staging Worker version
`3788c6b0-291c-43a9-bef3-b48aaa4a0498` and canonical production Worker version
`935c3c39-f63e-4041-804b-ef40431d50fc`. Release smoke checks confirmed the two
public routes, unauthenticated API rejection, HTTPS redirect, current composite
scenario and brand, and removal of the stale API-boundary copy. The Turnstile
script and challenge frame rendered to the waiting state on both Workers
without the former `ready()` error.

No equivalent connected hosted claim is made yet for the anonymous guest
lifecycle. Automated browsers were challenged before a token could be redeemed.
Anonymous sign-in, anonymous JWT acceptance, quotas, guest reset denial,
seven-day expiry, 30-day startup/24-hour periodic cleanup, auth-only identity
removal, fail-open behavior, and waitlist persistence therefore remain to be
exercised on staging. The per-location rate policies, two-hop 64 KiB cap,
85-second response-header deadline, and lock-fence revision remain part of that
connected hosted gate.

### Remaining release and production verification

- complete a human-solvable Turnstile challenge on staging and verify token
  redemption, anonymous sign-in, isolated bootstrap, all guest limits, cleanup,
  waitlist, and the complete workflow on the already-deployed exact revision;
- repeat the connected guest smoke path on the canonical Worker, record both
  deployed version identifiers with the evidence, and keep rollback metadata;
- configure custom SMTP for email addresses outside the project team;
- configure and verify GitHub OAuth before enabling it;
- keep manual OTP disabled or verify it explicitly before enabling it;
- record Render sleep/wake recovery on the promoted revision;
- run backup/restore, load, soak, fault-injection, independent security,
  privacy, and accessibility audits; and
- establish production monitoring, incident response, paid-plan/SLO, and
  rollback evidence.

The settled Playwright run starts the API against a dedicated SQLite database
after an Alembic upgrade and reset seed; all five local Chromium flows passed.
The current guest implementation lists those flows but still needs the full
run.
Hosted staging evidence is a separate connected-system check and not a
substitute for the remaining production audits.

## 6. Free-tier operating boundary

The target free topology is an evaluation environment:

- Render can sleep after 15 idle minutes and take about a minute to wake;
- the Render Free Blueprint omits `maxShutdownDelaySeconds` after the platform
  rejected it for that plan, leaving the 30-second default;
- Render's filesystem is ephemeral and the Free service cannot scale;
- Cloudflare Workers Free has a small CPU budget for dynamic SSR/auth work;
- Supabase Free can pause for inactivity and has limited database and backup
  characteristics;
- Supabase default SMTP currently limits magic-link delivery to authorized
  project-team addresses; custom SMTP is required for broader users, and
  GitHub OAuth remains disabled. The guest demo itself does not require email;
- combined Supabase and Render cold starts can exceed one service's advertised
  wake time.

The UI's “Waking your workspace…” state and bounded retry are honest recovery
UX, not an availability guarantee. See [deployment.md](deployment.md) for
current official platform links and the exact limits.

## 7. Production-maturity roadmap (separate from feature gates)

Gate 1 has passed its local checkpoint. Stop for product/evidence review before
authorizing Gate 2. Bounded solver, temporal, mutation, model, live runner, tau
execution, SDK, and enterprise work remain Gates 2–8.

The P0–P3 levels below concern operational maturity. They are not aliases for
those product feature gates.

### P0 — Complete verification and harden the deployed guest preview

1. On staging Worker version `3788c6b0-291c-43a9-bef3-b48aaa4a0498`, complete
   Turnstile token redemption and verify anonymous sign-in, signed anonymous
   JWT enforcement, isolated
   bootstrap, 30-write/six-operation limits, reset denial, seven-day expiry,
   30-day startup plus 24-hour periodic cleanup/fail-open alerting (including
   auth-only anonymous identities), waitlist persistence, and the complete
   Northstar workflow.
2. Rerun the connected guest path on canonical production Worker version
   `935c3c39-f63e-4041-804b-ef40431d50fc`, record evidence and rollback
   metadata, and replace either environment only with a tested exact bundle.
3. Configure custom SMTP, then verify delivery, expiry, scanner behavior,
   abuse controls, and recovery for non-team users.
4. Configure and staging-test GitHub OAuth before turning its feature flag on;
   leave manual OTP disabled unless it receives its own hosted verification.
5. Separate development/staging infrastructure from the canonical preview as
   soon as real user data or release concurrency makes a shared project unsafe.
6. Add tenant-level database defense: RLS on every relevant table or a private
   non-exposed schema with a least-privilege server role. Keep the Data API
   disabled and verify the boundary independently of FastAPI.
7. Move migrations to a trusted pre-deploy/CI-admin phase after upgrading from
   Render Free, and test backup/restore before storing important data.
8. Record Render sleep/wake behavior, production telemetry, request correlation,
   and secret-redaction checks across both services.
9. Establish a paid-plan decision and SLO before inviting broader users; Free
   tiers are not an uptime target.

Exit gate: every status in the hosted smoke-test matrix is recorded with commit,
environment, timestamp, and evidence; rollback and secret rotation are tested.

### P1 — Finish release integrity beyond the fixture invariants

Focused checks now cover byte-reproducible build roots, complete non-root
artifact hashing, build-pinned runner inputs, stored test snapshots, aligned
build/evidence schema v0.3 validation, and report digests. The remaining work is:

1. Keep generated JSON Schemas and OpenAPI drift-checked in final CI.
2. Retain the real two-session `Project → child` lock-order regression in every
   PostgreSQL release run.
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

Keep Aletheia centred on source-aware refactoring of reviewed agent
instructions: a smaller always-loaded prompt kernel, scoped skills/knowledge,
deterministic pre-tool decisions, tests, explicit pending material, and exact
build evidence. Do not broaden into generic prompt management, unbounded
user-authored policy code, or passive observability before the compilation,
release-integrity, and enforcement boundaries are reliable.

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
Northstar fixture workflow with broad settled local/CI evidence; a source-aware
verified local two-domain Gate 1 compilation workflow that is not deployed; a
permanent-user hosted path verified on staging; and a public guest release
deployed to staging/canonical production but still awaiting Turnstile token
redemption and complete connected guest verification.**
