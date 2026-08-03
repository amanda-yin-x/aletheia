# Aletheia current state and production roadmap

**Status:** engineering assessment and proposed roadmap  
**Snapshot date:** 2026-08-03  
**Repository:** Aletheia Policy CI  
**Audience:** founders, product/engineering, security reviewers, design partners, and future contributors  
**Scope:** what is actually working now, what is demo-only or scaffolded, and what should be built to reach a fully functional production system

This document is intentionally more conservative than a launch page. It distinguishes tested behavior from interfaces, configuration, and future intent. It does not turn the current fixture results into claims about live models, customer traffic, security certification, or production reliability.

## 1. Executive assessment

Aletheia currently provides a polished and technically coherent vertical slice of a policy-CI product:

1. It ingests a controlled fictional source corpus and preserves source text, line spans, and hashes.
2. It represents policy clauses as versioned, source-linked rules.
3. It exposes conflicts and ambiguities for human review.
4. It blocks compilation while critical conflicts remain unresolved.
5. It compiles approved rules into a smaller prompt kernel, workflow, knowledge, deterministic tool policy, regression suite, source map, and manifest.
6. It evaluates a deterministic 16-case refund suite across three comparison arms.
7. It shows that a covered `$200.01` refund proposal is intercepted before sandbox state mutation when approval is missing.
8. It exports a hash-linked Markdown/JSON evidence report with explicit limitations.
9. It delivers the same domain services through FastAPI, a Typer CLI, a SQL worker, and a responsive Next.js interface.
10. It is backed by automated backend, frontend, and browser tests plus reproducible dependency locks and deployment configuration.

That is a meaningful prototype, but it is not yet a general production service. The largest gaps are not cosmetic:

- The extraction, arbitrary-document analysis, and live-agent adapters are interfaces or deliberate stubs, not operating model integrations.
- Findings and the compiled refund workflow are produced from the known Northstar demo semantics, not a general policy-analysis pipeline.
- The runner replays checked-in scripted trajectories; it does not yet execute a nondeterministic model/tool loop.
- The τ retail integration imports and verifies pinned data but does not run the benchmark.
- There is no authentication, organization model, tenant isolation, production approval service, customer runtime SDK, signed artifact distribution, object storage, retention system, or canonical audit ledger.
- The current worker has persisted jobs, but not production-grade lease recovery, heartbeats, retry scheduling, idempotency, cancellation, or dead-letter operations.

The recommended product direction is to keep the current constrained policy IR and deterministic side-effect boundary as Aletheia's core. Build a secure multi-tenant control plane around it, then add a small independently deployable enforcement data plane. Do not turn Aletheia into a generic observability product or replace its reviewed business-policy model with unrestricted user-authored code.

The first credible production milestone should be a **private shadow pilot** against consented customer traffic with all external mutations disabled. The next milestone should be a narrowly scoped guarded canary with signed policy bundles, durable approvals, strong tenant isolation, replayable evidence, and an immediate rollback path.

Verification performed for this snapshot on 2026-08-03:

- `make ci` passed Ruff, strict mypy over 24 backend source files, all 27 backend tests, ESLint, strict TypeScript, all 5 frontend unit tests, and the Next.js production build;
- `corepack pnpm --filter @aletheia/web test:e2e` passed all 5 Chromium paths, including landing interactions, reduced-motion behavior, and 320/375/414/768 px overflow checks;
- all relative Markdown links in the reviewed documentation resolve, and all 39 external research links in this document returned successfully during the final link check.

These checks establish the state of the local deterministic implementation, not production operation or the unbuilt capabilities identified below.

## 2. How to read the status labels

| Label | Meaning |
|---|---|
| **Working** | Implemented, reachable through a product/API/CLI path, and covered by automated tests. |
| **Demo-limited** | Working for the bundled Northstar fixtures, but not generalized or production-safe. |
| **Interface only** | A protocol, configuration seam, endpoint, or command exists, but the substantive external behavior is not implemented. |
| **Configuration only** | Deployment or integration files exist but were not exercised against a real hosted environment. |
| **Not built** | No meaningful implementation exists yet. |

## 3. Product and evidence boundary

The safe current product claim remains:

> Aletheia turns agent policies into reviewed prompt, guard, and regression-test artifacts, then shows how a candidate behaves on repeatable sandbox scenarios.

The safe deterministic runtime claim remains:

> Approved, machine-decidable rules can allow, block, or request approval before a covered sandbox tool call executes. Results are limited to the configured rules and calls passing through this adapter.

The current system does **not** establish:

- formal verification;
- universal policy adherence;
- protection for calls that bypass the adapter;
- security, safety, privacy, or compliance certification;
- production reliability across models, frameworks, domains, or customer environments;
- live-model quality, cost, or latency;
- causal proof that a smaller prompt improves outcomes;
- lossless compression of every source instruction;
- readiness for confidential customer documents.

These boundaries are enforced in the current README, report generator, UI language, and evidence documentation.

## 4. What has been built

### 4.1 Repository and application architecture — Working

The repository is a Python/TypeScript workspace with:

- `apps/api`: Python 3.12, FastAPI, Pydantic v2, async SQLAlchemy, Alembic, Typer, and a SQL worker;
- `apps/web`: Next.js App Router, React, strict TypeScript, React Query, Recharts, Lucide, Vitest, and Playwright;
- `packages/api-client`: generated OpenAPI TypeScript schema output;
- `data/demo`: the fictional Northstar Retail corpus and sandbox state;
- `data/benchmarks/tau3-retail`: provenance-checked benchmark material;
- `docs`: architecture, evidence, course, build, demo, screenshots, and this roadmap;
- root Docker Compose, Render, Vercel, Make, CI, and lockfile configuration.

The backend is a modular monolith. Domain services do not import FastAPI. FastAPI, Typer, and the worker call the same service layer. This is the right shape for the next stage: the system does not need microservices merely to become production-capable.

Key implementation files:

- `apps/api/app/models.py`
- `apps/api/app/schemas.py`
- `apps/api/app/services/`
- `apps/api/app/api/routes.py`
- `apps/api/app/cli.py`
- `apps/api/app/worker.py`
- `apps/web/app/`
- `apps/web/features/`

### 4.2 Persistence and versioned contracts — Working, single-tenant

The data model includes:

- projects;
- immutable document versions;
- versioned rules;
- findings;
- immutable builds;
- declarative test cases;
- runs and scenario results;
- ordered trace events;
- immutable evidence reports;
- persisted jobs.

Important implemented properties:

- UUID identifiers;
- foreign keys and useful indexes;
- unique document versions and rule revisions;
- optimistic rule revision checks;
- supersession rather than in-place rule overwrite;
- canonical JSON hashing;
- content-addressed build/report deduplication;
- SQLite WAL for zero-install local use;
- PostgreSQL-compatible SQLAlchemy models;
- hosted `postgres://` URL normalization to the async driver;
- one Alembic initial migration;
- 13 exported JSON Schemas and an OpenAPI document.

Limitations:

- There is no `organization_id` or `tenant_id` anywhere in the model.
- Actors and reviewer identities are not persisted.
- JSON columns carry several important domain structures without database-level constraints.
- The web app currently keeps a parallel handwritten type layer instead of using the generated client end to end.
- Application startup calls `create_schema()` and seeds the demo, which must be removed from production startup behavior in favor of migrations and controlled commands.

### 4.3 Northstar source corpus and ingest — Working for safe local formats; demo-limited as a pipeline

The bundled corpus contains six fictional files:

1. a meaningful 165-line baseline system prompt;
2. current Refund Policy v3;
3. a conflicting legacy refund SOP;
4. a style guide;
5. a sandbox tool registry;
6. fictional order data.

The ingest service accepts UTF-8 `.txt`, `.md`, `.json`, `.yaml`, `.yml`, and text-based `.pdf` files. It:

- enforces a byte limit;
- rejects empty and unsupported files;
- parses JSON/YAML safely;
- uses strict PDF parsing;
- rejects scanned/no-text PDFs rather than pretending OCR happened;
- normalizes newlines;
- records MIME type, origin, line count, and a SHA-256 digest.

The demo's source references are computed from actual file text. Tests verify that every quote and line range matches the persisted document and hash.

Production gaps:

- no upload UI or connector workflow;
- no object storage;
- no content-type sniffing independent of filename;
- no malware scanning, parser sandbox, quarantine, OCR, layout anchors, or archive-bomb controls;
- no retention, deletion, legal hold, or data residency policy;
- no general analysis is triggered after a document upload.

### 4.4 Rule IR and deterministic interpreter — Working for a bounded AST

The rule contract captures:

- stable key and revision;
- title and normative text;
- category, effect, severity, status, and confidence;
- scope;
- a bounded condition AST;
- prerequisites and exceptions;
- enforcement and decidability classifications;
- exact source references;
- target tools and reviewer note.

The safe interpreter supports:

- `all`, `any`, and `not` nodes;
- `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `in`, `not_in`, `exists`, `contains`, and length-bounded `regex` predicates;
- fact roots limited to `tool`, `state`, `user`, `context`, and `events`;
- decimal-safe ordered comparisons;
- precedence among deny, prior-event, approval, and allow effects;
- matching approval events for the demo refund;
- fail-closed `indeterminate` decisions for high/critical rules with missing or invalid facts;
- canonical decision hashes and evaluated-fact evidence.

It never executes user-authored Python, JavaScript, shell, Rego, Cedar, or `eval`.

Production gaps:

- `RulePatch.condition` accepts an untyped dictionary rather than validating the complete AST and fact schema at the API boundary.
- Fact paths are root-allowlisted but are not backed by a versioned typed fact registry.
- Tool arguments are not validated against strict JSON Schemas immediately before policy evaluation.
- Money is represented in some fixtures as floating-point values; production money must use currency plus integer minor units or an equivalent exact type.
- Python regular expressions can exhibit pathological backtracking despite input-length limits; use a linear-time engine such as RE2 or remove general regex from enforcement.
- Approval matching is only a demo check on order ID and amount. It lacks approver identity, tenant, call ID, expiry, state/build binding, revocation, and replay protection.
- The global default is `allow`; production needs explicit per-tool/per-risk fail behavior and a distinct `not_applicable` result.
- Only `pre_tool` enforcement exists.
- There is no published conformance suite across runtime languages or versions.

### 4.5 Human review and findings — Working for seeded semantics; not a general analyzer

The UI and API support:

- a source-linked rule table;
- filters for review, critical, guarded, and missing-test states;
- an accessible rule drawer;
- the exact source quote and line range;
- a bounded form editor for condition values;
- approve/reject actions;
- optimistic revision conflict handling;
- finding resolution with a recorded note;
- build blocking while critical findings remain open.

The Northstar fixture includes:

- a proved 30-day versus 60-day conflict;
- a proved `$200` approval versus `$250` automatic-refund conflict;
- a duplicate instruction finding;
- a “daylight hours” ambiguity;
- a missing-timezone-fact finding.

Production gaps:

- Findings are seeded from known Northstar facts. There is no general overlap, contradiction, duplicate, missing-fact, temporal-scope, or reachability analyzer for arbitrary policies.
- Analysis jobs currently acknowledge fixture verification; they do not extract new candidates.
- Reviewer identity and separation of duties do not exist.
- Critical changes do not support two-person approval.
- There are no comments, assignments, queues, notification rules, due dates, escalation, or appeal/override workflow.
- Effective dates, jurisdiction, business unit, environment, and policy ownership are not modeled.

### 4.6 Deterministic compiler — Working for Northstar; domain-specific

Compilation requires resolved critical findings and approved revisions. It produces an immutable bundle containing:

- `prompt-kernel.md`;
- `workflows/refunds.md`;
- `knowledge/refund-reference.md`;
- `policies/tool-policy.json`;
- `tests/regression.yaml`;
- `source-map.json`;
- `manifest.json`;
- bundle `README.md`.

The manifest records document hashes, rule revisions, test IDs, compiler version, artifact hashes, estimator label, and limitations. Build stats are computed from persisted content, not hardcoded percentages. A normal reviewed build routes seven machine-decidable refund rules to the guard and 16 cases to the regression artifact.

Production gaps:

- The generated prose and refund workflow contain Northstar-specific static text.
- There is no domain-neutral routing/templating system.
- Builds are stored inside a database JSON column rather than immutable encrypted object storage.
- Hashes prove byte identity but not publisher authenticity; bundles are not cryptographically signed.
- There is no release channel, environment promotion, scheduled activation, canary, rollback, or runtime bundle-distribution protocol.
- There is no compatibility declaration among compiler, schema, policy runtime, tool registry, and SDK versions.

### 4.7 Declarative test suite and three-arm runner — Working deterministic fixture; not live evaluation

The bundled suite contains 16 Aletheia-authored cases covering:

- days 29, 30, and 31;
- `$200`, `$200.01`, and an approved `$249` refund;
- verified and unverified identity;
- invalid refund destination;
- duplicate refund;
- missing confirmation;
- non-returnable items;
- conflict, ambiguity, missing-fact, and style evidence.

Every case can run from identical deep-copied state in:

1. `baseline_unenforced`;
2. `compiled_unenforced`;
3. `compiled_enforced`.

The trace distinguishes proposal, policy decision, approval/block, execution, result, and state mutation. For the `$200.01` case, the guarded arm records the proposal and approval requirement without a `tool_executed` or state-change event.

The runner computes task success, attempted violation, executed violation, blocked call, false block, coverage, final-state hash, and first divergence. Tokens and cost remain honestly `N/A` in fixture mode.

Production gaps:

- Trajectories are checked-in scripts, not model-generated behavior.
- The sandbox tools are in-memory functions, not transactional adapters to real customer staging systems.
- A run executes all cases serially in one worker transaction and cannot resume individual trials.
- There are no repeated nondeterministic trials, uncertainty intervals, pass@k/pass^k, judge calibration, or human labels.
- Test generation jobs return the existing count and do not generate cases.
- No production-log mining, incident-to-regression workflow, or challenge-set lifecycle exists.

### 4.8 Reports and evidence — Working for fixtures

Reports persist:

- the evidence and deterministic runtime boundary;
- dataset provenance;
- adapter/model label;
- build, run, and dataset hashes;
- comparison arms and case count;
- metrics and top failures;
- limitations;
- a content hash;
- Markdown and JSON exports.

The verdict is deliberately restricted to `Changes required` or `Ready for sandbox pilot`.

Production gaps:

- A content hash is not a digital signature or trusted timestamp.
- Reports do not contain actor/reviewer identities, environment, runtime deployment receipt, container digest, complete provider parameters, or dependency provenance.
- There is no evidence retention policy, external auditor view, SIEM/GRC export, or revocation status.
- A report is not yet a complete reproducible safety case for a nondeterministic agent.

### 4.9 HTTP API, CLI, and jobs — Working demo surface; partially durable

The FastAPI surface provides health/readiness, public config, demo reset, projects, documents, analysis jobs, rules, approvals/rejections, findings, builds/artifacts, tests, runs/results/traces, reports/exports, and job polling.

Implemented API qualities include:

- `/api/v1` version prefix;
- Pydantic response schemas for core resources;
- request IDs and a stable error envelope;
- restricted CORS;
- baseline security headers and CSP;
- upload limits;
- `202` job behavior when inline demo jobs are disabled.

The Typer CLI can migrate/create schema, seed, analyze fixture data, compile, test, report, run a worker, and synchronize τ retail data.

The SQL worker claims PostgreSQL jobs with `FOR UPDATE SKIP LOCKED`, records an owner/lease, and handles compile/run plus placeholder analysis/test-generation jobs.

Production gaps:

- No endpoint is authenticated or authorized.
- Most list endpoints lack pagination, filtering, stable cursors, and quotas.
- Mutation endpoints lack general idempotency keys.
- The worker does not reclaim expired leases, heartbeat, schedule retries/backoff, dead-letter failures, enforce maximum attempts, or honor cancellation.
- Analysis and test-generation worker handlers are placeholders.
- There is no webhook/event-delivery subsystem.
- The CSP still allows inline script/style and `unsafe-eval`; production should use nonces/hashes and environment-specific policies.
- Errors are redacted for clients, but structured operational logging and exception reporting are not implemented.

### 4.10 Optional model adapters — Interface only

`RuleExtractor` and `AgentAdapter` protocols exist, along with classes named `StructuredLLMExtractor` and `OpenAICompatibleAgentAdapter`.

This is a good dependency boundary, but both live classes deliberately fail with a `503`-style service error. Even with credentials, they do not call a provider. This avoids a silent fixture fallback and prevents false claims, but it must be described as an interface rather than an integration.

### 4.11 τ retail benchmark support — Import working; execution not built

The sync adapter:

- clones `sierra-research/tau2-bench` at tag `v1.0.1`;
- verifies commit prefix `fc0055d`;
- selects the reviewed 17 task IDs;
- excludes known open tasks 4, 5, and 7;
- copies policy/database/task inputs;
- normalizes selected tasks;
- records hashes, license, commit, task purposes, and import time.

The real pinned data is present in the repository. The CLI run command only confirms that synchronized data exists; it does not execute τ. No τ score has been produced or claimed.

### 4.12 Web product — Working polished demo workflow

The web app includes:

- a proof-first public landing page with a source-linked policy trace, an interactive with/without-gate scenario, a four-stage release workflow, a keyboard jump palette, and explicit evidence boundaries;
- demo entry and overview;
- source viewer with numbered text and linked evidence;
- rules/findings workbench;
- condition editor and review actions;
- build blocker and artifact viewer;
- measured prompt comparison;
- regression table and run control;
- three-arm charts and scenario table;
- trace detail showing proposal versus execution;
- evidence report and downloads;
- designed loading, empty, error, and blocked states;
- responsive layouts and keyboard-accessible primary interactions.

Production gaps:

- no sign-in, onboarding, organization switcher, team management, settings, or service-account UI;
- no document upload/connectors UI;
- no environment/release/deployment UI;
- no approval inbox;
- no comments, assignments, notifications, saved views, or audit explorer;
- no usage/quotas/billing/admin controls;
- no WCAG 2.2 AA conformance audit across the full authenticated product;
- no localization or timezone-aware policy administration.

### 4.13 Quality, packaging, and deployment — Working locally; hosting configuration only

Current automated gates cover:

- Ruff;
- strict mypy over 24 backend source files;
- 27 backend tests;
- ESLint;
- strict TypeScript;
- 5 frontend unit tests;
- 5 Chromium end-to-end paths;
- a Next.js production build;
- schema export and generated API types.

The browser suite covers the source-linked conflict, human review/build flow, complete run/trace/report flow, landing jump palette and reduced-motion behavior, and narrow-viewport overflow safety.

The repository also contains:

- locked `uv` and pnpm dependencies;
- Dockerfiles;
- Docker Compose with PostgreSQL, API, worker, and web;
- Render API/worker/PostgreSQL configuration;
- Vercel configuration;
- GitHub Actions CI;
- health and readiness endpoints;
- MIT license and upstream notices.

The local environment used to build the MVP did not contain Docker, so Compose/container execution was not verified there. No external deployment was performed.

The prior source-path-depth defect has been removed: demo and benchmark data now resolve through a configurable `DATA_ROOT`, the API image sets it to `/data`, the web image copies the shared root tokens, and `.dockerignore` excludes local dependencies, caches, databases, and environment files from the build context. Docker was unavailable in the verification environment, so image startup remains unverified and needs a clean-image smoke test. Render also enables demo mode on a free database without configuring a reset secret; that is not an acceptable production deployment.

### 4.14 Fix-before-feature correctness audit

The following issues affect the truth of builds, runs, evidence, or hosted operation. They should be fixed before broadening the feature set.

#### 4.14.1 Runs are not pinned to the build they claim to evaluate

`run_comparison()` loads the project's latest approved rule rows and current test rows. It does not execute `policies/tool-policy.json` and `tests/regression.yaml` from the selected immutable build. A caller can also supply a build from another project because project ownership is not checked.

Consequence: editing a rule or test after build A can change a later run that still reports build A as its input. This violates the core reproducibility claim.

Required fix:

- validate that `build.project_id` equals the requested project;
- execute policy and tests from the selected build snapshot;
- store exact test version/hash and rule revision/hash in the build;
- reject incompatible schema/runtime versions;
- add a regression test that modifies current rules/tests after a build and proves the old build's run is unchanged.

#### 4.14.2 Build hashes are not deterministic for identical inputs

The compiler places `created_at` in the manifest before hashing it. Identical logical inputs can therefore produce different build hashes. Artifact hashes are computed before `manifest.json` and the bundle README are added, and `unresolved_findings` is always empty even when non-critical findings remain open.

Required fix:

- separate reproducible content from publication metadata;
- hash every emitted artifact or define an explicit root digest over a complete manifest;
- record all unresolved/accepted-risk findings accurately;
- add byte-for-byte reproducibility tests in separate processes/containers;
- expand the source map from stable-key lists to output spans, exact rule revisions, and source references.

#### 4.14.3 Resolving a conflict does not resolve the losing rule

“Use current policy” changes only the finding status/note. It does not atomically reject or supersede the losing legacy rule. The legacy rule happens to start in `needs_review`, but a reviewer can later approve it and compile contradictory approved summaries.

Required fix:

- make conflict resolution an explicit transaction with winner, loser, rationale, actor, and effective scope;
- reject/supersede or constrain the losing revision in that transaction;
- re-run conflict analysis before build and block contradictory approved rules even if an older finding was marked resolved.

#### 4.14.4 Semantic rule edits can remain approved

The bounded form editor creates a new revision, but `revise_rule()` preserves the prior status unless the caller supplies another status. Editing an approved condition therefore creates a new immediately approved guard. The UI's bounded fields help usability, but they are not a backend security boundary.

Required fix:

- any semantic change to condition, effect, scope, prerequisites, exceptions, enforcement, decidability, target tools, or normative meaning returns the revision to `needs_review`;
- re-run schema validation, finding analysis, coverage, and required approval policy;
- allow only explicitly non-semantic metadata changes to preserve approval.

#### 4.14.5 Interpreter semantics are incomplete

Current gaps include:

- `requires`/`require_prior_event` is represented but not generally evaluated;
- rule `exceptions` are ignored;
- approval matching is refund-specific rather than interpreting declared requirements;
- high-severity indeterminate rules are handled before matched denies, so global precedence is not fully modeled;
- equality type mismatches normally become `false` rather than `indeterminate`;
- trace rule references contain stable keys but not exact revisions/source references.

These are safe to demonstrate within the current fixture, but must be specified and tested before new rule types are advertised.

#### 4.14.6 Tool execution is not schema-validated

The sandbox `tools.json` defines schemas, but the runner does not load them before proposing/executing calls. Missing or wrong-typed arguments can reach `_execute()`. An unknown tool is recorded as `tool_executed` before returning `invalid_tool`, which corrupts execution semantics.

Required fix:

- validate and canonicalize against the exact build-pinned tool schema before `tool.proposed` becomes eligible for policy evaluation;
- record invalid proposals without an execution event;
- include the tool-schema digest in decisions, runs, reports, approvals, and execution receipts.

#### 4.14.7 Test assertions and metrics are narrower than the product contract

`expected` remains a broad dictionary. Several finding/style cases have no trajectory and pass without asserting the finding/compiler state. Observe-only success is mostly the absence of a forbidden execution rather than complete end-state correctness. `positive_negative_boundary` coverage is hardcoded `true`.

Required fix:

- type expected decisions, proposals, arguments, event order, reason codes, final-state predicates, and response assertions;
- make finding/style cases assert real outputs;
- calculate coverage from rule/test relationships and boundary classification;
- report worst/high-severity behavior separately from aggregate rates.

#### 4.14.8 Evidence reports are incomplete for release decisions

Current reports omit exact rule revisions, compiler/runner versions, tool-schema digest, detailed test-suite digest, open/accepted findings, source/test coverage, and trace/source links. The verdict checks guarded executed violations and false blocks, but not overall guarded task success or blocking evidence completeness. JSON export returns the evidence body without the report's own content hash.

Required fix:

- define a versioned evidence schema and release-gate policy;
- include the complete immutable run manifest and report digest/signature;
- render failures and linked evidence in both Markdown and UI;
- require all configured release conditions, not two aggregate fields.

#### 4.14.9 Hosted queued jobs are not end-to-end functional

With `DEMO_INLINE_JOBS=false`, build/run POST routes return a `202` job-shaped response, while the declared OpenAPI response and frontend mutation expect an immediate `Build` or `Run`. The frontend does not poll the returned job and follow its `resource_id`.

Required fix:

- model asynchronous operation responses explicitly in OpenAPI;
- make the frontend poll or subscribe to the operation and navigate to the resulting resource;
- add hosted-mode E2E tests with a separate worker;
- then add lease recovery, heartbeat, retries, cancellation, dead letters, and idempotency.

#### 4.14.10 Ingest provenance misnames the original hash

For uploads, `original_sha256` is calculated over normalized text rather than the original uploaded bytes. PDF provenance records a page count but not the actual page-to-normalized-line mapping.

Required fix:

- preserve `original_blob_sha256` and a separate `normalized_content_sha256`;
- store parser/normalizer versions and complete anchor mapping;
- migrate existing fixture metadata without relabeling old hashes as byte hashes.

#### 4.14.11 API, deployment, and documentation drift

- FastAPI validation failures still use the framework's default 422 body rather than the Aletheia error envelope.
- Several mutation bodies are unbounded dictionaries.
- CI regenerates schemas/client code but does not fail on generated-file drift.
- `make ci` and the GitHub workflow do not represent exactly the same gates.
- This audit corrected the README's former `FixtureAgentAdapter` wording and Docker implication, clarified test stable keys in the architecture note, and corrected the benchmark-data notice.
- CI still lacks an automated claims/implementation drift check; generated schema drift also needs an explicit `git diff --exit-code` gate once the workspace is under version control.

Required fix: correct these statements and add contract/deployment smoke tests before using the repository configuration as deployment evidence.

## 5. Current readiness matrix

| Capability | Status today | Meaningful next gate |
|---|---|---|
| Source-linked Northstar demo | **Working** | Preserve as golden end-to-end regression. |
| Safe local file parsing | **Working** | Quarantine, scan, object-store, and process files in a sandbox. |
| Arbitrary policy extraction | **Interface only** | Real structured provider adapter plus deterministic quote verification and human review. |
| General finding analysis | **Demo-limited** | Static overlap/conflict/coverage engine over arbitrary reviewed IR. |
| Rule review/revision | **Working, single-user** | Authenticated actors, assignments, two-person critical approval, effective dates. |
| Bounded policy interpreter | **Working** | Typed facts/tools, exact money, conformance/fuzz/property tests, versioned semantics. |
| Northstar artifact compiler | **Working** | Domain-neutral routing/templates and signed release bundles. |
| Deterministic fixture runner | **Working** | Live provider loop, repeated trials, staging tools, evaluator calibration. |
| τ data import | **Working** | Real adapter execution and version-complete provenance; never mix revisions. |
| τ benchmark execution | **Not built** | Execute pinned tasks with explicit models/config/trials and publish limitations. |
| Evidence report | **Working for fixtures** | Signed attestation, full run manifest, actor/deployment provenance, revocation. |
| Persisted SQL jobs | **Demo-limited** | Lease recovery, heartbeat, retries, DLQ, idempotency, cancellation, observability. |
| API/CLI/web workflow | **Working** | Auth, tenancy, pagination, service accounts, SDKs, webhooks, audit explorer. |
| Multi-tenant SaaS security | **Not built** | OIDC, organizations, RBAC, PostgreSQL RLS, object isolation, abuse controls. |
| Runtime customer enforcement | **Not built** | Signed-bundle SDK/gateway, approval service, shadow/canary/rollback. |
| Production operations | **Configuration only** | Hosted staging, SLOs, backups/restore drill, alerts, incident runbooks, threat model. |

## 6. What “fully functional” should mean

Aletheia should not use “fully functional” as a synonym for “has more pages.” A fully functional private-pilot system should allow a real design partner to complete these workflows safely:

### 6.1 Organization administrator

1. Sign in through an enterprise identity provider.
2. Create an organization and invite or provision users.
3. Assign organization/project roles.
4. Configure retention, residency, model-provider, and export settings.
5. Create scoped service accounts/API keys with rotation and revocation.
6. Review immutable audit events and export them.

### 6.2 Policy owner

1. Create a project and environments such as development, staging, and production.
2. Upload or connect policy sources.
3. See processing/quarantine status and stable source anchors.
4. Run extraction and deterministic analysis.
5. Review candidates, conflicts, missing facts, scope, and coverage.
6. Assign reviews and approve a release under separation-of-duties rules.

### 6.3 Agent engineer

1. Register strict tool schemas and trusted fact providers.
2. Map approved rules to tools and lifecycle points.
3. Compile a versioned candidate bundle.
4. Add or import declarative scenarios.
5. Run deterministic and live evaluations with complete manifests.
6. Compare candidate versus active release and set a release gate.
7. Integrate a runtime SDK/gateway first in shadow mode.

### 6.4 Approver/operator

1. Receive a queue item for a specific blocked tool proposal.
2. Inspect normalized arguments, source rules, state/build hashes, risk, and expiry.
3. Approve, reject, or escalate with a rationale.
4. Resume the exact compatible execution.
5. See whether the tool executed and whether state committed or rolled back.

### 6.5 Security/evidence consumer

1. Inspect the exact release, policy, tool schema, model, dataset, and runtime versions.
2. Verify artifact/report signatures.
3. Review high-severity failures separately from aggregate rates.
4. Trace every consequential action from proposal through policy decision and commit.
5. Verify limitations, deployment status, overrides, incidents, and rollback history.

## 7. Recommended target architecture

Keep a modular control plane, but separate the latency- and trust-sensitive runtime enforcement path.

```text
                                      CONTROL PLANE

 browser / CLI / CI ── OIDC/API auth ──> FastAPI application
                                              │
                   ┌──────────────────────────┼──────────────────────────┐
                   │                          │                          │
             PostgreSQL                 object storage            durable jobs
       metadata, revisions, audit    sources, artifacts, traces   parse/extract/eval
         tenant RLS + PITR            KMS + retention policy       retry + resume
                   │                          │                          │
                   └────────────── build/review/release ────────────────┘
                                              │
                                    signed immutable bundle
                                              │
                               registry / customer distribution
                                              │
                                      RUNTIME DATA PLANE

 agent proposes tool call ──> policy enforcement point ──> side-effecting tool
                                     │       │
                         local/cached decision│
                                     │       └── durable approval service
                                     │
                         canonical execution ledger
                                     │
                         redacted OTLP projection
```

### 7.1 Control-plane responsibilities

- identity, organizations, membership, roles, and service accounts;
- document ingestion and governance;
- extraction, findings, rule review, and approvals;
- builds, tests, evaluation, release gates, and reports;
- signed artifact publication and rollback metadata;
- customer configuration, audit administration, and integrations.

### 7.2 Runtime data-plane responsibilities

- accept only a strict normalized tool proposal;
- select an already verified active bundle;
- validate tool schema and trusted facts;
- evaluate policy before any covered side effect;
- pause for a durable, call-bound approval when needed;
- re-evaluate immediately before execution;
- execute with idempotency and timeout controls;
- record a canonical receipt and before/after state hashes;
- continue safely on control-plane unavailability using the last valid signed bundle and an explicit fail policy.

The control plane should not sit synchronously in every tool-call path. This follows the policy decision point/policy enforcement point separation described in [NIST SP 800-207 Zero Trust Architecture](https://csrc.nist.gov/pubs/sp/800/207/final) and avoids turning a control-plane outage into an implicit policy bypass. Each release/risk class must declare a maximum bundle age and behavior after expiry.

### 7.3 Keep these decisions

- Keep FastAPI, Next.js, PostgreSQL, Pydantic, SQLAlchemy, and Alembic.
- Keep the modular monolith until scale or team boundaries justify a split.
- Keep the constrained Aletheia IR as the human-review and portability contract.
- Keep deterministic verification after any model-shaped output.
- Keep fixtures as a required offline test path.
- Keep proposals, decisions, executions, and state changes as distinct events.
- Keep source/build/run/report hashes, but add signatures rather than replacing hashes.

### 7.4 Add these boundaries

- A managed OIDC identity provider instead of building password authentication.
- PostgreSQL-only production with tenant-aware transactions and row-level security.
- Encrypted object storage for original files, generated artifacts, and large trace payloads.
- A durable job contract with idempotency and resumability.
- A policy bundle registry and signature service backed by a cloud KMS/HSM.
- A language-neutral runtime protocol plus one reference SDK/gateway.
- A canonical audit ledger separate from sampled/redacted operational telemetry.

### 7.5 Do not add these yet

- Microservices for every domain noun.
- Kubernetes before a managed platform can meet measured requirements.
- A vector database merely because documents are involved.
- Unrestricted customer-authored Rego, Cedar, Python, or JavaScript.
- A full observability backend.
- A dozen agent-framework integrations before one reference runtime integration is safe.
- A custom identity provider.
- A compliance badge generated from fixture results.

## 8. Production workstreams

Each workstream below names the current gap, the recommended implementation, and an acceptance gate.

### 8.1 Identity, organizations, and tenant isolation

Build:

- managed OIDC authorization-code flow with PKCE and secure server-managed sessions;
- token/session validation for issuer, audience, signature, nonce, expiry, and authorized party where applicable;
- phishing-resistant MFA options for tenant administrators, policy approvers, signing-key operations, and break-glass access, primarily enforced by the managed identity provider;
- organizations, users, memberships, groups, projects, and environments;
- roles such as organization admin, policy owner, reviewer, agent engineer, runtime operator, approver, auditor, and read-only viewer;
- project-scoped service accounts and hashed API credentials with expiry/rotation;
- authorization in the service layer, not only the route or UI;
- `tenant_id` on every tenant-owned record, object key, job, event, and cache key;
- tenant-inclusive unique constraints and composite foreign keys so invalid cross-tenant references cannot be persisted;
- PostgreSQL row-level security with default deny and `FORCE ROW LEVEL SECURITY` where appropriate;
- a non-owner application database role so normal application traffic cannot bypass RLS;
- tests that deliberately attempt cross-tenant access through every API and worker path.

Tenant context must be derived from the validated identity and server-side membership. Never authorize an arbitrary organization identifier supplied by a request body, job payload, URL, model output, or webhook without checking that binding.

Acceptance gate:

- No unauthenticated access to customer resources.
- Every request/job has an authenticated actor or service principal and organization context.
- Cross-tenant reads/writes fail in route, service, worker, direct SQL, export, object storage, and cache tests.
- Privilege changes and service-key lifecycle actions appear in the audit ledger.

Enterprise follow-on:

- SAML/OIDC SSO policies;
- SCIM user/group provisioning;
- domain verification;
- session controls and conditional access delegated to the IdP.

### 8.2 Governed document ingestion

Build:

- direct-to-object-storage uploads through short-lived signed URLs;
- random storage keys independent of customer filenames;
- upload session, size/page/decompression quotas, and checksum verification;
- quarantine before parsing;
- MIME/content sniffing and extension allowlists;
- malware scanning and, where justified, content disarm/reconstruction;
- isolated resource-limited parser jobs with timeouts;
- OCR/layout extraction with page, paragraph, and bounding-box anchors;
- immutable source versions with effective date, jurisdiction, business unit, owner, confidentiality, and retention metadata;
- duplicate/near-duplicate detection and supersession links;
- connectors only after the upload pipeline is safe and observable.

Acceptance gate:

- An uploaded source cannot be downloaded or analyzed before passing quarantine controls.
- Parser crashes/timeouts cannot crash the API or starve the worker pool.
- Original bytes, normalized representation, anchors, parser version, and hashes remain reproducible.
- Deletion and retention jobs remove all eligible database/object/index/telemetry copies and leave a non-sensitive audit receipt.

### 8.3 Real extraction and deterministic candidate verification

Build:

- a provider-neutral model gateway for extraction and test generation;
- strict structured output into a candidate schema;
- explicit model/provider/snapshot/settings and prompt hash per invocation;
- bounded retries, timeouts, rate limits, cost budgets, and circuit breakers;
- no model tools during extraction;
- deterministic verification that every quote occurs at the claimed source anchor;
- schema/fact/tool validation before a candidate enters review;
- an explicit `unverified` state rather than silently repairing unsupported claims;
- per-tenant provider-data-retention settings and secret references;
- evaluation fixtures for malicious source instructions and prompt injection.

Acceptance gate:

- Model output can create candidates but cannot approve or publish rules.
- Fabricated or shifted quotes are rejected or flagged.
- Every candidate has model provenance and exact source evidence.
- Missing provider credentials or outages never switch to fixture output silently.
- Provider content retention and telemetry behavior is visible to the organization admin.

### 8.4 General findings and coverage analysis

Build deterministic analyzers for:

- contradictory effects over overlapping conditions;
- numeric and temporal boundary disagreement;
- duplicate/subsumed rules;
- missing trusted facts;
- uncovered consequential tools or argument fields;
- unreachable rules and shadowed effects;
- precedence and prerequisite cycles;
- incompatible jurisdictions/effective periods;
- ambiguous non-numeric terms that cannot be guarded;
- missing positive, negative, boundary, approval, and failure-path tests.

Model suggestions may enrich explanations, but severity/proof labels must distinguish deterministic proof, heuristic suspicion, and human concern.

Acceptance gate:

- A synthetic corpus with known overlaps has no missed critical proved conflicts.
- Heuristic findings never masquerade as proved facts.
- Every finding includes a machine-readable witness and source/rule links.
- Coverage is reported by rule, tool, argument, risk tier, fact, and lifecycle stage.

### 8.5 Review, release, and policy governance

Build:

- immutable rule revision history with author/reviewer identities and rationale;
- draft, in review, changes requested, approved, rejected, scheduled, active, superseded, and revoked states;
- effective/expiry dates and environment scope;
- assignments, comments, mentions, due dates, and notifications;
- two-person approval for critical enforceable rule changes;
- separation between author and final approver where policy requires it;
- review diffs across source, normalized text, condition AST, tool scope, and compiled artifacts;
- accepted-risk decisions with owner and expiry;
- stale-review invalidation when a source, tool schema, fact schema, compiler, or dependency changes.

Acceptance gate:

- No critical release can become active without the configured approval policy.
- Every active rule resolves to exact reviewed sources and actors.
- Any material input change invalidates affected approvals and release gates.
- Rollback selects a previously signed compatible release without rewriting history.

### 8.6 Versioned policy semantics and conformance

Build:

- a fully discriminated condition schema at write and compile boundaries;
- a versioned typed fact catalog with ownership, trust source, freshness, and sensitivity;
- versioned strict tool schemas with `additionalProperties: false` semantics where supported;
- exact money/time primitives;
- safe string/membership operations and a linear-time regex implementation if regex remains;
- an explicit result model: `allow`, `deny`, `require_approval`, `require_prior_event`, `indeterminate`, and `not_applicable`;
- configurable default/fail behavior per tool and risk tier;
- explain plans showing matched/non-matched rules without leaking sensitive facts;
- policy schema migrations and compatibility windows;
- property, mutation, fuzz, and differential conformance suites.

Acceptance gate:

- Malformed ASTs and tool arguments cannot reach evaluation.
- Every interpreter version passes the same golden conformance corpus.
- Boundary tests cover exact currency, time, missing, null, NaN/infinity, Unicode, oversized values, and malicious regex inputs.
- A production release declares compatible runtime and schema versions.

### 8.7 Generic compiler and signed artifact lifecycle

Build:

- domain-neutral routing based on rule category, effect, enforcement, decidability, scope, and target tools;
- configurable, versioned templates rather than hardcoded Northstar prose;
- separate source maps for prompt, workflow, knowledge, policy, and tests;
- deterministic serialization and reproducible build containers;
- an immutable object-store bundle with content digest, signature, certificate/key ID, and provenance attestation;
- environment channels such as candidate, staging, canary, and active;
- compatibility checks before activation;
- distribution using authenticated fetch, caching/ETag, last-known-good persistence, and atomic activation;
- revocation and rollback.

Acceptance gate:

- Identical inputs under the same compiler produce byte-identical artifacts.
- Any input/template/compiler change changes the manifest.
- Runtime nodes reject invalid, unsigned, revoked, incompatible, or partially downloaded bundles and retain the last valid release.
- Activation and rollback are observable and auditable.

### 8.8 Authoritative runtime enforcement

Build one reference enforcement point before broad framework integrations. It must:

1. accept a proposal with tenant, project, environment, agent, conversation/run, call, tool, arguments, actor, and state-version identifiers;
2. validate strict tool input;
3. fetch trusted facts with bounded freshness;
4. load the exact active signed bundle;
5. evaluate before execution;
6. return a stable reason code and decision receipt;
7. pause and persist a resumable continuation for approval;
8. revalidate approval, bundle, state, and facts before execution;
9. execute through an idempotent customer adapter;
10. commit or roll back state atomically where the tool permits it;
11. record execution outcome independently from the proposal;
12. operate in `observe`, `approval_only`, `guarded_canary`, or `enforced` mode.

Recommended deployment choices:

- local/in-process or same-host policy evaluation for the latency-critical decision;
- optional gateway service where language/platform constraints require it;
- cached last-known-good bundles;
- explicit per-tool behavior if the approval/control plane is unavailable;
- no direct model credential with permissions broader than the gateway tool set.

Acceptance gate:

- A covered mutating tool cannot be invoked except through the enforcement point.
- Duplicate requests cannot create duplicate side effects.
- Approval replay, stale approval, changed arguments, changed state, changed build, and expired approval are rejected.
- Timeout/network/crash tests demonstrate fail behavior for each risk tier.
- Shadow mode proves integration without external mutation before guarded canary activation.

### 8.9 Durable human approval service

Add:

- `ApprovalRequest` and immutable `ApprovalDecision` records;
- binding to tenant, actor, tool-call ID, normalized arguments hash, state hash/version, rule/build/runtime versions, risk, and expiry;
- approver eligibility rules and delegation;
- queue, notification, SLA, escalation, expiry, rejection, cancellation, and appeal states;
- resumable execution state with SDK/agent compatibility marker;
- exact diff and source evidence in the approval UI;
- re-evaluation immediately before execution;
- narrowly scoped batch approvals only when the normalized call set and risk policy allow them.

Acceptance gate:

- Approval never acts as a reusable bearer token.
- An approval can resume only the exact compatible pending call.
- Every transition is append-only and attributable.
- The approver can always see whether execution subsequently succeeded, failed, or never occurred.

### 8.10 Production evaluation and release gates

Keep the three-arm comparison, but extend the measurement model:

- unsafe proposal rate;
- executed violation rate;
- intercept rate;
- false-block rate;
- unnecessary-approval rate;
- stale/incorrect approval rate;
- tool-selection accuracy;
- tool-argument accuracy;
- end-state correctness;
- response correctness;
- handoff correctness;
- rollback correctness;
- latency and cost;
- metrics by rule, risk, task class, model, and environment.

Add:

- repeated nondeterministic trials and confidence intervals;
- pass@k/pass^k where appropriate;
- frozen regression sets plus separately versioned evolving challenge sets;
- typical, edge, adversarial, incident-derived, and customer-authored cases;
- calibrated human labels and judge validation;
- replay from recorded model proposals/tool outputs;
- candidate-versus-active evaluation on identical proposals;
- release policies that treat high-severity failures individually rather than averaging them away.

Acceptance gate:

- Every run has a complete immutable manifest: sources, rules, compiler/runtime, prompts, tools, evaluator, test set, model/user simulator, settings, trial count, seed, limits, dependency locks, container digest, and patches.
- Results from different benchmark versions are never compared as if equivalent.
- A live result is never replaced with fixture output after provider failure.
- Release gates are explainable, overrideable only by authorized actors, and audited.

### 8.11 Canonical ledger and operational observability

Create an append-only canonical ledger with at least:

```text
tool.proposed
policy.evaluated
approval.requested
approval.approved | approval.rejected | approval.expired
tool.execution_started
tool.executed | tool.failed
state.committed | state.rolled_back
```

Each event should carry:

- organization/project/environment;
- actor/service principal;
- trace/span/run/scenario/call IDs;
- monotonic sequence number and timestamp;
- source/rule/build/runtime hashes;
- tool and normalized argument hash;
- before/after state hashes where meaningful;
- reason/result code;
- sensitivity/redaction class;
- integrity chain or signature metadata.

OpenTelemetry should receive a redacted, potentially sampled projection of this ledger. It should not be the sole audit system. Pin the semantic-convention mapping version because GenAI conventions remain under active development.

Operational telemetry should cover:

- API availability and latency;
- policy-decision latency and outcomes;
- bundle freshness/activation failures;
- queue wait, retry, lease age, and dead letters;
- approval age and expiry;
- provider latency, rate limits, token/cost use, and errors;
- tool latency/errors and duplicate suppression;
- build/evaluation failure and duration;
- tenant quotas and abuse signals;
- backup/PITR status and restore-test age.

Acceptance gate:

- Operators can move from an SLO alert to a request/job/run/call without exposing raw customer content by default.
- Full prompt/tool content is opt-in, access-controlled, encrypted, retention-limited, and never placed in high-cardinality metric labels.
- Dropped telemetry cannot erase the canonical execution history.

### 8.12 Durable jobs and workload isolation

The SQL queue can remain for an early pilot if it gains:

- atomic claim and unique idempotency keys;
- lease heartbeat and expired-lease recovery;
- exponential backoff with jitter and maximum attempts;
- retryability classification;
- cancellation checkpoints;
- job dependencies and child trial records;
- progress events;
- dead-letter inspection/requeue;
- per-tenant concurrency, rate, and cost quotas;
- separate worker pools for parsing, model calls, compilation, and evaluations;
- graceful shutdown and resumability.

Use a transactional outbox for events that must leave the database transaction, and assume duplicate delivery. A hardened PostgreSQL queue is a reasonable bridge. If human approvals, multi-hour evaluation, and cross-service resumption make the queue increasingly complex, evaluate a durable workflow engine such as Temporal against measured requirements rather than recreating workflow replay semantics indefinitely.

Move to a dedicated workflow/queue platform only when measured scheduling, concurrency, isolation, or long-lived approval requirements justify the operational cost.

Acceptance gate:

- Killing a worker at every critical point does not lose or duplicate a job's externally visible effect.
- A poison job cannot starve other tenants.
- Operators can cancel, inspect, retry, and correlate every job.

### 8.13 Security, privacy, and software supply chain

Before confidential data or guarded production mutations:

- complete a threat model covering cross-tenant access, prompt injection, excessive agency, confused deputy, malicious files, approval replay, stale bundles, trace tampering, provider compromise, secrets leakage, and denial of service;
- adopt a secure-development baseline using NIST SSDF and OWASP ASVS;
- manage secrets in a cloud secret/KMS service with least privilege and rotation;
- encrypt transport and managed storage; separate metadata keys from customer-content access;
- classify/redact sensitive fields before logs/telemetry;
- add per-tenant retention, deletion, export, legal-hold, and residency controls;
- add rate limits, request/body/decompression/model budgets, and abuse monitoring;
- generate SBOMs, scan dependencies/images/IaC, pin build actions, protect branches, and use signed provenance/attestations;
- run SAST, secret scanning, dependency review, container scanning, DAST, and focused penetration tests;
- maintain vulnerability disclosure, incident response, key compromise, and customer notification runbooks;
- do not claim SOC 2, ISO 27001, GDPR/PIPEDA compliance, or similar status solely because controls were implemented.

Acceptance gate:

- Independent security review finds no unresolved critical/high issue for the pilot scope.
- Secrets and real customer content do not appear in client errors, standard logs, build artifacts, or default telemetry.
- Backup, key rotation, tenant export/deletion, and incident exercises have recorded evidence.

### 8.14 Frontend and product operations

Add product surfaces for:

- sign-in/onboarding and organization/project/environment navigation;
- secure upload and source processing status;
- extraction runs and candidate triage;
- assignment/comment/review queues;
- release diff, approval, promotion, canary, and rollback;
- runtime integration setup and health;
- approval inbox and execution outcome;
- live evaluation configuration and complete manifests;
- audit/incident explorer;
- organization security, retention, provider, service-account, and usage settings;
- accessible exports and an external reviewer view.

Quality gate:

- WCAG 2.2 AA target, combining automated checks with keyboard, zoom/reflow, contrast, screen-reader, focus-management, and accessible-authentication testing.
- Designed permission-denied, processing, partial-failure, stale-data, empty, degraded, and offline states.
- Destructive or irreversible actions require explicit scope and consequence review.

### 8.15 Deployment, recovery, and incident response

Build the operational system, not merely deploy descriptors:

- separate development, staging, and production accounts/projects, databases, keys, provider credentials, and audit destinations;
- managed multi-zone PostgreSQL, encrypted/versioned object storage, secret manager/KMS, private service networking, edge TLS/WAF/rate limiting, multiple stateless API replicas, and independent worker pools;
- infrastructure as code, immutable images, least-privilege workload identity, resource limits, graceful drain, and canary/blue-green application releases;
- expand/migrate/contract database changes with compatibility checks and rollback plans;
- business-approved RPO/RTO, continuous WAL/PITR, base backups, protected backup copies, and monitored archive health;
- automated restore validation plus scheduled full recovery exercises that verify RLS, membership, environment pointers, bundle signatures, legal holds, and deletion behavior;
- an on-call/severity model, incident commander, security/privacy/legal/customer-communication roles, out-of-band contacts, evidence preservation, and status communication;
- tested runbooks for cross-tenant access, stolen credentials, enforcement bypass/fail-open, compromised signing keys/bundles, malicious uploads, supply-chain compromise, provider exposure, destructive deletion, and backup failure;
- emergency controls to revoke sessions/keys, disable connectors, freeze promotion, revoke signing keys, roll back bundles, isolate a tenant, stop egress, and force risky tools to deny without waiting for a code deployment.

Acceptance gate:

- A clean environment can be created from infrastructure and migration sources.
- A restore drill meets the agreed RPO/RTO and produces evidence.
- A tabletop/game-day exercises at least cross-tenant exposure and compromised-bundle scenarios.
- Operators can execute rollback, tenant isolation, credential rotation, and enforcement kill-switch procedures under pressure.

## 9. Proposed data-model evolution

Do not place every new concern in one JSON column. Introduce explicit entities incrementally.

### Identity and tenancy

- `organizations`
- `users`
- `memberships`
- `groups`
- `role_bindings`
- `service_accounts`
- `api_credentials`
- `sessions`

### Project and environment lifecycle

- `environments`
- `tool_schemas`
- `fact_schemas`
- `connectors`
- `project_settings`
- `release_channels`

### Sources and extraction

- `document_blobs`
- `document_versions`
- `document_anchors`
- `processing_runs`
- `extraction_runs`
- `model_invocations`
- `candidate_rules`

### Governance and release

- `review_requests`
- `review_decisions`
- `finding_resolutions`
- `policy_releases`
- `artifact_bundles`
- `artifact_signatures`
- `deployments`
- `runtime_instances`

### Runtime and approvals

- `tool_proposals`
- `policy_decisions`
- `approval_requests`
- `approval_decisions`
- `execution_receipts`
- `audit_events`

### Evaluation

- `test_suites`
- `test_case_versions`
- `run_trials`
- `model_manifests`
- `evaluator_versions`
- `human_labels`
- `release_gate_results`

Every tenant-owned table needs `organization_id`, and usually `project_id`/`environment_id`. Immutable records should be append-only in application behavior. Large/raw content belongs in encrypted object storage with database metadata and integrity hashes.

## 10. API and SDK evolution

### Control-plane API

Add:

- authenticated actor/tenant context;
- typed request bodies instead of broad dictionaries;
- stable cursor pagination, sorting, and filters;
- idempotency keys on mutations and job creation;
- ETags or revision preconditions on editable resources;
- consistent async operation resources;
- versioned webhooks with signature verification and deduplication;
- export/import contracts with explicit schema versions;
- deprecation and compatibility policy;
- organization/project/environment-scoped endpoints.

### Runtime API/SDK

Define a small language-neutral contract for:

- bundle fetch/status;
- tool proposal/decision;
- approval interruption/resume;
- execution receipt;
- audit/telemetry correlation.

Ship one reference SDK or gateway first. A good first integration is a Python-owned tool dispatcher because the backend and conformance suite are already Python. Add Node/TypeScript only after the protocol and failure semantics stabilize.

The SDK must make bypass difficult and visible. It should not expose a helper that an agent developer can accidentally call after already invoking the real side effect.

## 11. Delivery roadmap

Durations are rough sequencing aids for a focused team of roughly 2–4 engineers with product/design and security support. They are not commitments; discovery with the first design partners should change the scope.

### Phase 0 — Preserve truth and production invariants (2–4 weeks)

Goals:

- convert this assessment into tracked epics and architectural decision records;
- add a machine-readable capability/status page so stubs cannot be confused with live integrations;
- pin every run to the exact selected build policy, tests, tools, and schema versions;
- make build content hashes deterministic and complete;
- make conflict resolution atomic and force semantic rule edits back through review;
- add a clean container startup smoke test for the now configuration-driven data root;
- make queued build/run operations type-correct and functional through the web UI;
- remove production startup seeding/schema creation behavior;
- validate condition ASTs at write/compile boundaries;
- replace float money in the policy/runtime contracts;
- define tool/fact schema contracts and decision result semantics;
- extend trace IDs with a stable call ID and timestamp;
- add property/fuzz tests for policy boundaries;
- establish a data classification and threat-model draft.

Exit gate:

- Current demo remains green.
- An old build produces the same run inputs after current project rules/tests change.
- Two identical builds are byte-identical and share the same content digest.
- Unsafe or ambiguous policy inputs fail explicitly.
- Production versus fixture capabilities are machine-visible and documented.

### Phase 1 — Secure private-pilot control plane (4–6 weeks)

Goals:

- OIDC, organizations, memberships, RBAC, and service accounts;
- PostgreSQL-only hosted staging with tenant RLS;
- object-storage/quarantine ingestion;
- canonical actor-aware audit events;
- hardened SQL jobs with retry/recovery/cancellation;
- structured logs, metrics, tracing, dashboards, and initial SLOs;
- backup/PITR plus a restore drill;
- authenticated onboarding, upload, team, and settings UI.

Exit gate:

- Two test organizations cannot access each other's resources through any surface.
- A source can be uploaded, scanned, parsed, retained, exported, and deleted under policy.
- Worker crash recovery and restore tests pass.
- No live side effect or confidential production traffic is enabled.

### Phase 2 — Real policy CI for design partners (5–8 weeks)

Goals:

- live structured extraction behind the provider-neutral gateway;
- deterministic source verification;
- general finding/coverage engine;
- generic compiler templates;
- governed rule/review/release lifecycle;
- test-case generation plus human review;
- live model runner with repeated trials, cost/latency, and full manifests;
- actual pinned τ execution as a separately labeled benchmark;
- CI/Git integration and signed candidate bundles.

Exit gate:

- A new non-Northstar policy corpus can move from source upload to reviewed candidate build without code changes.
- Live runs are reproducible at the manifest/replay level and never silently fall back.
- Design partners can define release gates and export evidence with honest limitations.

### Phase 3 — Shadow runtime and guarded canary (6–10 weeks)

Goals:

- reference enforcement SDK/gateway;
- signed bundle registry/distribution and last-known-good cache;
- authoritative tool schemas and trusted fact providers;
- canonical proposal/decision/execution ledger;
- durable approval service and workbench;
- idempotent execution receipts;
- observe, approval-only, canary, enforced, rollback, and kill-switch modes;
- incident replay and production-trace-to-test intake.

Exit gate A — shadow:

- Real consented proposals are evaluated, but Aletheia cannot mutate external state.
- Candidate and active decisions can be compared with measured latency and no data-boundary violations.

Exit gate B — guarded canary:

- One narrow reversible/compensatable tool path uses enforcement.
- Approval replay, bypass, stale-bundle, worker/network failure, and duplicate-call tests pass.
- Rollback and kill-switch drills meet the agreed recovery target.

### Phase 4 — Enterprise readiness and wider beta (8–12 weeks)

Goals:

- enterprise SSO policy and SCIM;
- data residency, retention, legal hold, and customer-managed export workflows;
- SIEM/GRC/webhook integrations;
- production quotas, usage metering, support/admin tools, and status communication;
- WCAG 2.2 AA audit/remediation;
- SBOM, signed build provenance, vulnerability management, and penetration test;
- formal SLO/error-budget process, on-call, incident management, and DR exercises;
- additional runtime languages/frameworks selected from customer demand.

Exit gate:

- Security, privacy, reliability, support, and contractual launch checklists are reviewed by accountable owners.
- No unresolved critical/high finding remains in the intended deployment scope.
- Claims and evidence have been reviewed by counsel/security/compliance specialists where applicable.

### Phase 5 — General availability and scale (ongoing)

Only after usage evidence:

- regional cells/data residency;
- larger evaluation scheduling and autoscaling;
- more policy backends/exporters;
- more connectors and runtime SDKs;
- advanced policy analysis or bounded formal methods;
- billing/pricing automation;
- external control/audit certifications pursued through their actual processes.

## 12. Recommended first 12 implementation pull requests

1. **Build-pinned runs:** execute exact build policy/tests/tools, validate project ownership, and prove later edits cannot change an old build's run.
2. **Reproducible complete bundles:** remove wall-clock data from the root digest, hash every artifact, record real unresolved findings, and test byte identity.
3. **Safe review transitions:** atomically resolve conflict winner/loser and force every semantic edit back to `needs_review`.
4. **Production/container invariant:** configuration-driven data roots, Docker startup smoke test, Alembic-only production schema, and explicit demo seed.
5. **Typed async contract:** explicit operation resource for queued build/run, frontend polling, hosted-worker E2E, and uniform error envelopes.
6. **Typed policy/tool boundary:** validate conditions, requirements, exceptions, fact/tool schema versions, and unsupported types before persistence.
7. **Exact value primitives:** migrate money to currency plus integer minor units, add timezone-aware time, and choose linear-time regex semantics.
8. **Policy conformance suite:** property/mutation/fuzz tests, complete precedence/prerequisite/exception semantics, and stable reason-code snapshots.
9. **Tenant/auth foundation:** organizations, memberships, environments, OIDC, RBAC, service accounts, and negative authorization tests.
10. **PostgreSQL RLS and audit:** composite tenant keys, default-deny policies, non-owner app role, worker context, and actor-aware append-only events.
11. **Object ingestion and durable jobs:** quarantine/scanning/parser limits, original/normalized hashes, lease recovery, retry/cancel/dead-letter/idempotency.
12. **Real provider and generic analysis:** one strict extraction adapter, quote verification, overlap/coverage findings, generic compiler, and a second domain fixture.

After these, build signed bundles and the shadow runtime rather than adding many low-value UI integrations.

## 13. Testing and assurance plan

### 13.1 Keep current gates

- lint and strict typing in both languages;
- backend unit/integration tests;
- frontend component tests;
- end-to-end product flows;
- production builds;
- generated-schema drift checks.

### 13.2 Add before private customer data

- migration upgrade/downgrade and fixture compatibility tests;
- PostgreSQL integration tests in CI;
- tenant-isolation matrix and authorization mutation tests;
- upload/parser fuzzing, decompression-limit, malicious PDF, and timeout tests;
- secret/PII log scans;
- API rate-limit and quota tests;
- backup restoration test in an isolated environment;
- accessibility checks plus manual assistive-technology review.

### 13.3 Add before runtime canary

- property-based policy tests and mutation testing;
- differential tests between compiler/runtime versions and any OPA/Wasm export;
- tool-schema fuzzing and malicious argument cases;
- idempotency/concurrency tests around every side effect;
- approval expiry/replay/revocation/stale-state tests;
- worker and network fault injection at each lifecycle boundary;
- signed-bundle corruption, partial download, key rotation, revocation, and rollback tests;
- bypass analysis proving all covered calls pass the enforcement point;
- prompt-injection/confused-deputy/excessive-agency red-team cases;
- performance/load tests with actual policy/data shapes.

### 13.4 Add for live evaluation

- repeated trials and uncertainty reporting;
- human calibration sets for any model judge;
- tool selection, arguments, state, response, safety, approval, and latency metrics;
- frozen regressions and independently versioned challenge sets;
- incident/override-derived cases;
- benchmark-version compatibility checks;
- replay tests from recorded provider/tool interactions.

## 14. Initial service objectives to validate

These are proposed design targets, not current claims or contractual SLAs. Validate them with design partners and measured load.

| Area | Initial internal objective |
|---|---|
| Control-plane availability | 99.9% successful well-formed requests monthly, excluding announced maintenance. |
| Policy decision correctness | 100% pass on the versioned conformance corpus; no tolerated high-severity known mismatch. |
| Local decision latency | p95 under 10 ms for the agreed pilot policy/tool shape, measured without external fact fetching. |
| Remote gateway latency | p95 under 75 ms excluding approval and customer tool execution; validate rather than promise. |
| Bundle activation | Atomic activation; invalid bundle never replaces last known good; rollback initiation under 5 minutes. |
| Job durability | No lost acknowledged jobs; at-least-once processing with idempotent externally visible effects. |
| Approval integrity | Zero accepted stale/replayed/mismatched approvals in conformance and security testing. |
| Tenant isolation | Zero known cross-tenant access; every supported access path covered by negative tests. |
| Recovery | Pilot target RPO ≤ 5 minutes and RTO ≤ 4 hours, demonstrated by restore drill before launch. |
| Security response | Critical vulnerability triage within one business day; concrete remediation SLA set by policy. |

Use a small number of user-relevant SLIs and an error budget. Do not claim 100% service availability; correctness and isolation invariants should instead be enforced through release gates and incident policy.

## 15. Threat model priorities

| Threat | Why it matters to Aletheia | Required control direction |
|---|---|---|
| Cross-tenant access | Policies, traces, and sources may be highly confidential. | OIDC/RBAC, tenant-aware service layer, RLS, object-key isolation, negative tests. |
| Prompt/source injection | Uploaded policy text is untrusted input to an extractor/model. | Isolate instructions from data, strict schemas, no extraction tools, deterministic quote validation, adversarial tests. |
| Excessive agency/tool bypass | A model with direct tool access can ignore the policy adapter. | One authoritative enforcement point, least-privilege credentials, integration/bypass tests. |
| Confused deputy | A valid service may act for the wrong user/tenant/context. | Actor/tenant/call binding, audience/scopes, trusted fact sources, reauthorization. |
| Approval replay/substitution | A prior approval could authorize a changed or repeated action. | Bind approval to call/args/state/build/tenant/expiry; re-evaluate; consume once. |
| Malicious file/parser exploit | Policy files can attack parsing infrastructure. | Quarantine, scanning, content sniffing, isolated parser, quotas/timeouts, patching. |
| Policy bundle tampering | A modified guard changes side-effect authorization. | Signed bundles, KMS keys, atomic verification, revocation, last known good. |
| Trace/audit tampering | Evidence loses value if events can be rewritten or confused. | Append-only ledger, identity, sequence/integrity metadata, restricted administration, exports. |
| Sensitive telemetry leakage | Prompts/tool arguments may contain customer data or secrets. | Classification/redaction, opt-in content capture, encryption, limited retention/access. |
| Resource exhaustion/cost abuse | Model calls, PDFs, runs, and traces are expensive. | Limits, quotas, budgets, rate control, workload isolation, circuit breakers. |
| Supply-chain compromise | The compiler/runtime decides consequential actions. | Locked deps, SBOM, scanning, signed provenance/images, protected CI/release identities. |
| Stale facts or policies | A technically valid old decision can still be unsafe. | Freshness metadata, effective dates, version binding, activation health, fail behavior. |

## 16. Main product and engineering risks

| Risk | Likely consequence | Mitigation/decision |
|---|---|---|
| Trying to generalize before one real customer corpus | A broad but shallow rule model. | Co-design the second-domain pipeline with 2–3 design partners; preserve typed constraints. |
| Treating model extraction as authoritative | Fabricated rules enter enforcement. | Model creates candidates only; deterministic source/schema checks and human approval remain mandatory. |
| Guard blocks unsafe calls but agent cannot recover | Lower safe task completion and poor UX. | Measure safe success and recovery after intervention; design explicit agent-visible denial/approval results. |
| Runtime integration can be bypassed | Safety claims become false. | Make the gateway the only credentialed path to covered side effects and test architecture bypasses. |
| False blocks create operator fatigue | Teams disable enforcement. | Shadow mode, per-rule metrics, calibrated tests, narrow canaries, actionable reason codes. |
| Approval queue becomes blanket authorization | Human review becomes theatre. | Exact call binding, expiry, risk caps, re-evaluation, and no broad sticky approvals by default. |
| Benchmark score becomes a marketing shortcut | Misleading comparability and incentives. | Preserve full version/config/trial provenance; separate customer suites and benchmark revisions. |
| Overbuilding infrastructure before product proof | Slow learning and operational burden. | Keep modular monolith/managed services; split only around runtime trust/latency or measured load. |
| Compliance language gets ahead of evidence | Legal and trust risk. | Maintain claim registry and independent review; reports state limitations and control scope. |
| Sensitive traces become a second data lake | Privacy/security exposure. | Canonical minimal ledger, protected payload store, redacted OTLP, explicit retention. |

## 17. Research-backed conclusions

The roadmap above is an engineering inference informed by current primary sources. The sources do not certify this design; they provide relevant standards, threats, and operating patterns.

### 17.1 Governance and secure development

- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework) frames AI risk work across design, development, use, evaluation, and operation. NIST notes that AI RMF 1.0 is being revised, so use it as a current governance baseline rather than a frozen compliance target.
- [NIST AI RMF Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) adds GenAI-specific risks/actions.
- [NIST SP 800-218A](https://www.nist.gov/publications/secure-software-development-practices-generative-ai-and-dual-use-foundation-models-ssdf) extends the Secure Software Development Framework for AI model development and should be used with the base SSDF.
- [OWASP ASVS 5.0](https://owasp.org/www-project-application-security-verification-standard/) provides a testable web-application security baseline.
- [OWASP Agentic AI threats and mitigations](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/) and [OWASP Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) reinforce least functionality, permissions, and autonomy at tool boundaries.

Conclusion: Aletheia's deterministic pre-tool boundary is directionally correct, but production safety requires identity, least privilege, lifecycle governance, monitoring, response, and recovery—not only a policy evaluator.

### 17.2 Identity and tenant isolation

- [OAuth 2.0 Security Best Current Practice, RFC 9700](https://datatracker.ietf.org/doc/rfc9700/) updates the OAuth threat model and deprecates insecure modes.
- [NIST SP 800-63B-4](https://pages.nist.gov/800-63-4/sp800-63b.html) defines current authenticator assurance guidance, including phishing-resistant options at higher assurance.
- [SCIM protocol, RFC 7644](https://datatracker.ietf.org/doc/html/rfc7644) defines standardized enterprise user/group provisioning and contains explicit multi-tenancy/security considerations.
- [PostgreSQL 18 row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) provides default-deny row filtering when RLS is enabled without a matching policy, but superusers, `BYPASSRLS`, and normally table owners bypass it.

Conclusion: use a managed IdP, application-layer authorization, and PostgreSQL RLS as defense in depth. The normal application connection must not be a table owner or RLS-bypass role.

### 17.3 Upload and data safety

- [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) recommends allowlisting, size limits, authorized uploaders, storage outside the web root/on a separate host, scanning, and safe retrieval.

Conclusion: the current parser allowlist is a good start, but confidential production ingest requires quarantine, object isolation, scanning, resource-limited parsing, and a governed lifecycle.

### 17.4 Evaluation and benchmarks

- [τ-bench paper](https://arxiv.org/abs/2406.12045) evaluates stateful tool-agent-user interaction and motivates repeated-trial reliability metrics such as pass^k.
- The [τ benchmark repository](https://github.com/sierra-research/tau2-bench) exposes task/split, model, seed, trial, concurrency, and detailed log parameters; its [changelog](https://github.com/sierra-research/tau2-bench/blob/main/CHANGELOG.md) shows that benchmark task fixes can materially affect results.
- [AgentDojo](https://openreview.net/forum?id=m1YYAQjO3w) measures both utility and security for agents operating over untrusted tool data.
- [OpenAI evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices) recommend task-specific, production-representative, continuously run evaluations and calibrated graders rather than “vibe-based” assessment.
- As of this document's snapshot, [OpenAI's legacy Evals documentation](https://developers.openai.com/api/docs/guides/evals) announces read-only status on 2026-10-31 and shutdown on 2026-11-30. Aletheia should keep its run/evidence contract provider-neutral rather than depending on that retiring API.
- [NIST AI RMF Measure playbook](https://airc.nist.gov/airmf-resources/playbook/measure/) emphasizes documented test sets, metrics, limitations, deployment-like conditions, and appropriate independent/domain review.

Conclusion: keep deterministic fixtures, but production evidence needs repeated live trials, complete manifests, separate utility/security metrics, human calibration, deployment-representative cases, and explicit benchmark version boundaries.

### 17.5 Runtime approvals and traces

- [OpenAI guardrails and approvals guidance](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals) places tool-side validation next to consequential actions.
- [OpenAI Agents SDK human-in-the-loop documentation](https://openai.github.io/openai-agents-python/human_in_the_loop/) demonstrates interruption, durable pending state, call-scoped approval, and compatible resumption. This is used as a lifecycle reference, not as a requirement to adopt that SDK.
- [OpenTelemetry trace conventions](https://opentelemetry.io/docs/specs/semconv/general/trace/) distinguish duration-bearing spans, while [event conventions](https://opentelemetry.io/docs/specs/semconv/general/events/) cover point-in-time occurrences.
- Current [OpenTelemetry GenAI conventions](https://github.com/open-telemetry/semantic-conventions-genai) are evolving and sensitive content is opt-in/high risk.

Conclusion: model proposals, policy decisions, approvals, execution, and commits must remain separate. Keep a canonical application ledger and export a redacted version-pinned OTLP projection.

### 17.6 Policy distribution and artifact integrity

- [OPA bundle management](https://www.openpolicyagent.org/docs/management-bundles) shows useful production patterns: revisioned/signed bundles, atomic activation, and retaining the prior active bundle on verification failure.
- [OPA management architecture](https://www.openpolicyagent.org/docs/management-introduction) separates distributed policy decision points from a logical control plane, while clarifying that OPA does not provide a complete control plane itself.
- [Sigstore blob signing](https://docs.sigstore.dev/cosign/signing/signing_with_blobs/) and [verification](https://docs.sigstore.dev/cosign/verifying/verify/) provide one implementation option for signed artifact bundles.
- [SLSA v1.2 build requirements](https://slsa.dev/spec/v1.2/build-requirements) describe build provenance and hardened build expectations.

Conclusion: keep Aletheia IR as the product contract. Borrow signed-bundle and management patterns or add an OPA exporter later; do not immediately expose unrestricted Rego as the authoring model.

### 17.7 Reliability, recovery, and accessibility

- [PostgreSQL point-in-time recovery](https://www.postgresql.org/docs/current/continuous-archiving.html) explains WAL archiving and PITR; backups only count when restore procedures are exercised.
- [Google SRE service-level objectives](https://sre.google/sre-book/service-level-objectives/) recommends user-relevant SLIs/SLOs, a small number of meaningful indicators, percentiles, and error budgets rather than impossible 100% availability.
- [OpenTelemetry Collector deployment patterns](https://opentelemetry.io/docs/collector/deploy/) cover agent/gateway collection topologies and security considerations.
- [NIST SP 800-61 Rev. 3](https://csrc.nist.gov/pubs/sp/800/61/r3/final) integrates incident response across the NIST Cybersecurity Framework lifecycle.
- [Temporal workflow execution](https://docs.temporal.io/workflow-execution) and [retry policy](https://docs.temporal.io/encyclopedia/retry-policies) documentation provide a useful reference if measured workflow durability needs outgrow the SQL queue.
- [AWS transactional outbox guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html) describes avoiding dual-write inconsistency while accepting idempotent duplicate delivery.
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) is the current W3C accessibility recommendation and advises WCAG 2.2 as the target for future applicability.

Conclusion: production readiness requires measured SLOs, restore/rollback drills, actionable alerting, and an accessibility conformance program—not just deploy files and a green build.

### 17.8 Privacy lifecycle and sanitization

- The [NIST Privacy Framework](https://www.nist.gov/privacy-framework) provides a voluntary framework for identifying and managing privacy risk; its version status should be checked before claiming alignment.
- [NIST SP 800-88 Rev. 2](https://csrc.nist.gov/pubs/sp/800/88/r2/final) covers media sanitization and cryptographic-erasure considerations.

Conclusion: every Aletheia data class needs an owner, purpose, access policy, location, retention, export/deletion path, backup-expiry behavior, and provider/subprocessor boundary. Implemented controls do not by themselves establish legal compliance.

## 18. Questions to validate with design partners

These questions should shape the roadmap before investing in broad infrastructure:

1. Is the first paid job policy review/CI, runtime enforcement, or security evidence for procurement?
2. Which agent stack and tool boundary can the first partner actually integrate?
3. Which one or two consequential tools are narrow enough for a safe shadow/canary pilot?
4. Who owns policy review, and what separation of duties is required?
5. What source formats and systems are truly required in the first three deployments?
6. Which facts are trusted at decision time, who owns them, and how fresh must they be?
7. What false-block and approval-volume levels are operationally acceptable?
8. What latency budget can the runtime boundary consume?
9. What data can leave the customer's region or reach a model provider?
10. What retention/deletion/legal-hold obligations apply to sources and traces?
11. What evidence does an enterprise reviewer actually accept?
12. Does the customer require self-hosted enforcement, a hosted gateway, or both?
13. Which integration should be first: Python dispatcher, Node dispatcher, HTTP gateway, or an existing framework adapter?
14. What incident/override should automatically become a regression case?

## 19. Definition of done for a production private pilot

Aletheia may call itself a production private-pilot system only when all of the following are true for the stated scope:

- [ ] Real users authenticate and are authorized within isolated organizations/projects/environments.
- [ ] Confidential sources follow a quarantined, encrypted, retained, and deletable lifecycle.
- [ ] A new customer corpus can be extracted, verified, reviewed, compiled, and tested without source-code changes.
- [ ] Every active rule and artifact resolves to immutable sources, reviews, versions, and signatures.
- [ ] Live evaluations record complete provider/evaluator/tool/dataset manifests and repeated-trial uncertainty.
- [ ] The runtime integration first passes a consented no-mutation shadow pilot.
- [ ] Every covered mutation goes through the enforcement point with strict schemas and trusted facts.
- [ ] Approvals are durable, exact-call-bound, expiring, replay-resistant, and re-evaluated before execution.
- [ ] Execution receipts distinguish proposed, blocked, approved, started, executed, failed, committed, and rolled-back states.
- [ ] Bundles activate atomically, reject invalid signatures, persist last known good, and support tested rollback/kill switch.
- [ ] Jobs recover from worker failure without losing or duplicating externally visible effects.
- [ ] Tenant isolation, policy conformance, abuse limits, backup restore, security, accessibility, and load gates pass.
- [ ] SLO dashboards, alerts, incident runbooks, on-call ownership, and customer support paths exist.
- [ ] Evidence and marketing language state the exact technical and evaluation boundary.
- [ ] An accountable product, engineering, security, and privacy owner accepts the residual risk.

General availability requires additional operational history, customer validation, contractual/security review, and incident learning. It cannot be inferred from completing a checklist once.

## 20. Immediate recommendation

Do not begin with more visual polish or many agent-framework adapters. The strongest next sequence is:

1. harden policy values, schemas, semantics, and conformance;
2. add identity, tenancy, audit, and secure source storage;
3. make arbitrary source extraction/findings/compiler behavior real for a second domain;
4. add reproducible live evaluation;
5. sign and distribute bundles;
6. integrate one authoritative runtime path in shadow mode;
7. add durable exact-call approvals;
8. progress to one narrow guarded canary only after security, recovery, and rollback gates pass.

This path preserves what is distinctive and already credible in Aletheia: reviewed source provenance, deterministic compilation, clear proposal-versus-execution traces, and policy enforcement at the side-effect boundary.
