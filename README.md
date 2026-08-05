# Aletheia

**Source-aware policy refactoring and compilation for AI agents.**

[![CI](https://github.com/amanda-yin-x/aletheia/actions/workflows/ci.yml/badge.svg)](https://github.com/amanda-yin-x/aletheia/actions/workflows/ci.yml)
[![Status: Gate 1 deployed; guest E2E pending](https://img.shields.io/badge/status-Gate_1_deployed%3B_guest_E2E_pending-2563eb)](docs/deployment.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-0f766e)](LICENSE)

**Public site:** [aletheia.aletheia-web.workers.dev](https://aletheia.aletheia-web.workers.dev)

The public URL is the canonical Next.js site. Gate 1 release commit
`2329a1e39c00bf6313965bc06454f9bd49119816` is deployed on the named staging
Worker (version `7a049fd2-5053-4334-bea1-92d7f1099235`) and canonical
production Worker (version `091618a0-3582-48f3-9b53-8d2733387ed8`), backed by
Render deploy `dep-d9pa9f6417fc73dfhcvg` and hosted Alembic head `0006`.
Fresh guest bootstrap passed on staging at `2026-08-05T02:53:56Z` and canonical
production at `2026-08-05T02:59:13Z`. Both environments passed basic
Northstar/Acme navigation and inventory checks plus bounded
ownership/reference-isolation probes. This is bootstrap/navigation/inventory
evidence—not a claim that the complete guest review/build/run/report/download,
quota, or cleanup lifecycle has passed hosted testing.
The permanent-user Northstar lifecycle was previously verified on staging; see
[the deployment runbook](docs/deployment.md) for the exact boundary and
rollback record.

Aletheia refactors reviewed prompts, skills, policies, SOPs, and tool schemas
into a smaller always-loaded prompt kernel plus scoped skills, knowledge,
deterministic guards, tests, and explicit pending material. Exact source
anchors, placement decisions, generated spans, and pinned inputs make each
candidate build inspectable. The included Northstar Retail project starts with
a composite `$249` case where
order state, refund destination, approval policy, and a retained SOP disagree.
The workspace then provides a concrete path through the product: resolve two
policy conflicts, approve a strict refund boundary, compile a stored,
content-digested artifact bundle, compare labelled execution arms, inspect a
blocked `$200.01` boundary trace, and export Markdown or JSON evidence.

![Aletheia landing page showing the source-linked refund policy decision](docs/screenshots/landing-desktop.png)

> Aletheia refactors reviewed agent instructions into a smaller always-loaded
> prompt kernel plus scoped skills, knowledge, guards, tests, and explicit
> pending material, with source-linked build evidence.

Aletheia is not a generic prompt compressor, production agent firewall, formal
verification system, compliance certification, or claim about live-model
performance. The bundled records are generated evaluation data; no customer
records or real business side effects are included.

| Product track | Current status |
|---|---|
| Gate 0 — Local deterministic foundation | Complete in the settled tested Northstar fixture scope. |
| Gate 0H — Hosted verification and release hardening | In progress: fresh guest bootstrap plus basic two-domain navigation/inventory and bounded isolation passed on staging and production; complete guest E2E remains unverified. |
| Gate 1 — Source-aware policy refactoring and prompt/skill compilation | Complete in the verified local two-domain fixture scope and deployed to the hosted preview; connected hosted build/run/report and the detailed Acme workflow remain open. |
| Gates 2–8 | Not implemented. Provider interfaces, tau data sync, schemas, or research notes do not make these operating capabilities. |

Gate 1 implementation evidence remains pinned to checkpoint `2292a5f`; release
commit `2329a1e` packages that implementation for Render and the current
Workers. Deployment establishes release presence, not full hosted Gate 1
behavioral verification.

## Why policy CI

Agent instructions rarely live in one clean prompt. In the landing scenario, a
verified customer requests gift-card credit for order `N-1099`: `$249`, nine
days after delivery, but marked non-returnable. A retained SOP appears to allow
the action because it permits 60-day returns, automatic refunds through `$250`,
and the customer-requested destination. Current policy instead requires an
escalation, the original payment method, and matching approval above `$200`.

Northstar makes the entire failure path inspectable. In the unenforced arm, the
policy decision is recorded but the proposed refund still mutates state. In the
guarded arm, destination and returnability rules deny the exact call before
execution; rule IDs, evaluated facts, a decision hash, and unchanged state are
retained. The separate `$200.01` case verifies the strict approval boundary.

![Composite Northstar refund scenario comparing stale guidance with the enforced current policy](docs/screenshots/composite-refund-desktop.png)

## Quick start

Requirements: Python 3.12+, `uv`, Node 22 LTS, and Corepack. The local fixture
path needs no Supabase project, model API key, or Docker.

```bash
make bootstrap
make demo
```

Open [http://localhost:3000](http://localhost:3000). The API and local OpenAPI
UI are available at [http://localhost:8000](http://localhost:8000) and
[http://localhost:8000/docs](http://localhost:8000/docs).

Local and hosted modes are separated, and production fails closed:

- the API itself defaults to `ENVIRONMENT=production`; local commands
  explicitly select `ENVIRONMENT=local` and a fixed development identity;
- explicit `AUTH_MODE=local` is accepted only on a loopback `SITE_URL`;
- `make demo` also has a development-only fallback when Supabase configuration
  is absent; that fallback cannot activate in a production build;
- SQLite is the zero-install database;
- the deterministic fixture runner does not call a model;
- the API refuses to start with incomplete production Postgres/TLS, Supabase,
  web-origin, or origin-secret settings; and
- the production web path disables local auth, rejects incomplete
  Supabase/Turnstile configuration, and will not proxy without an HTTPS API
  origin and server-only origin credential.

Docker Compose is an alternative local PostgreSQL stack:

```bash
docker compose up --build
```

The Compose configuration includes PostgreSQL, FastAPI, a worker, and the
Next.js server. It is configuration-complete, but a clean-image smoke test is
still a release gate in this repository snapshot.

## Product walkthrough

1. Open **Northstar Retail Refund Agent** and go to **Rules**.
2. Review the source-linked 30/60-day and `$200`/`$250` conflicts plus the
   unresolved “daylight hours” ambiguity.
3. Resolve the critical conflicts in favour of Refund Policy v3. Open
   **Approval above $200**, inspect the exact quote and
   `amount.minor_units > 20000`
   condition, then approve the revision.
4. Choose explicit destinations for the reviewed clauses, then open **Build**
   and compile a candidate. The Gate 1 artifact contract includes a prompt
   kernel, scoped `SKILL.md`, knowledge, pre-tool policy, regression YAML,
   unsupported-material ledger, routing/preservation/metric reports, exact
   source map, pinned inputs, and manifest. The concrete build manifest is
   authoritative for the exact artifact set.
5. Open **Tests**, run the bundled release suite, and inspect the
   `$200.01 without approval` guarded trace. The proposal is recorded, approval
   is required, and no refund mutation occurs.
6. Inspect each rule-derived generated span back to its rule revision,
   placement version, and exact source anchor. Then create an evidence report
   and download Markdown or canonical JSON.

The verified Gate 1 implementation includes an Acme appointments domain pack to
test the same compiler outside refunds. It is synthetic evaluation data, not a
live scheduling integration. The release contains that pack and the generic
compiler, while the confirmed source/placement/build/run and sixth Playwright
flow remain local evidence; connected hosted Acme navigation and execution have
not yet been verified.

The exact 90-second talk track is in [docs/demo-script.md](docs/demo-script.md).

## Hosted architecture

```text
public browser
    │
    ├── GET / ───────────────────────────────► public Cloudflare landing page
    │
    └── GET /demo ───────────────────────────► public guest entry
          │
          ▼
    Turnstile ─► Supabase anonymous sign-in
          │ signed session: role=authenticated, is_anonymous=true
          ▼
    Next.js 16 + OpenNext on Cloudflare Workers
          │ same-origin /api/v1/* proxy
          │ Authorization: Bearer <Supabase JWT>
          │ X-Aletheia-Origin-Token: <server-only shared secret>
          ▼
    Render FastAPI service
          │ verifies origin token + JWT, then applies workspace membership scope
          ▼
    Supabase Postgres
```

The browser never receives `API_ORIGIN_URL`, `API_ORIGIN_TOKEN`, a database
connection string, a Supabase service-role key, or OAuth provider secrets. All
product API requests use the Cloudflare app's same-origin proxy. Mutations also
require an exact `Origin` match and a double-submit CSRF token.

The auth callback accepts only a browser-bound Supabase PKCE authorization
`code`; portable raw `token_hash` links are rejected. At the Render boundary,
production requests must first carry the shared origin credential and a bearer
token. Hosted document-upload requests are then rejected before FastAPI routes
or multipart body parsing run; secure customer ingestion is not implemented.

Each signed Supabase subject—anonymous guest or permanent account—receives an
idempotently bootstrapped personal workspace and Northstar project. Backend
reads and writes join through `workspace_members`; unauthorized cross-tenant
resource IDs return not found. A guest can exercise the seeded review,
build/run, trace, and report workflow without supplying an email address. A
guest can later attach a new email identity in place, preserving the same
Supabase subject and workspace; manual identity linking is enabled for the
equivalent future OAuth upgrade path. Guest workspaces intentionally disable
uploads, arbitrary project creation, and
reset; allow at most 30 successful writes and six live operations; and expire
after seven days. Cleanup targets anonymous identities older than 30 days at
startup and every 24 hours. In hosted Postgres, guest age is anchored to
`auth.users.created_at`, and cleanup also removes old anonymous Auth identities
that never created an application account/workspace.

The hosted proxy configures per-subject Cloudflare thresholds of 120 general,
90 polling, and 30 heavy requests per minute. Cloudflare evaluates these
per-location with permissive, eventually consistent counters; they are abuse
controls, not an exact global quota. Mutation bodies are capped at 64 KiB at
both the Worker and FastAPI boundaries. The 85-second bound applies until the
Worker receives upstream response headers; it does not time a streamed body
after headers arrive.

Supabase's native CAPTCHA integration verifies that Turnstile succeeded, but it
does not separately enforce Turnstile's returned `action` or `hostname` fields.
The `guest_demo`, `waitlist`, and `login` actions are client-side labels. The
widget allowlist contains only the canonical and staging hostnames; local
development uses local auth or Cloudflare's Turnstile test key.

The waitlist accepts a normalized, unique email through the authenticated API
for either a guest or permanent session. Its consent record remains after guest
workspace cleanup; submitting an email does not silently convert the anonymous
account into a permanent account. The role model contains owner, admin, editor,
and viewer scopes, although team invitations and role-management UI are not
built yet.

Builds and runs use a durable operation contract. Their `POST` endpoints return
HTTP `202`, a `Location` header, and `OperationOut`. The web app polls
`GET /api/v1/jobs/{id}`, handles success and every modeled failure state, then
loads and navigates to only the validated `resource_type` and `resource_id`.

Read [docs/hosted-workspace.md](docs/hosted-workspace.md) for the complete
human-readable implementation inventory and
[docs/capabilities.json](docs/capabilities.json) for the machine-readable status.

## Architecture inside the API

```text
raw source bytes → versioned documents + authority metadata + exact anchors
    → reviewed Rule IR → append-only placement decisions + pinned profile
    → deterministic compiler → prompt kernel / skill / knowledge / guard / tests
    → generated spans / routing / preservation / metrics / source map
    → deterministic replay → pre-tool policy decision → covered tools
    → labelled-arm results → traces / metrics → evidence report

                         ┌ Typer CLI
domain services + SQL ───┼ FastAPI / SQL operation worker
                         └ Next.js same-origin client
```

The backend remains a modular monolith. Generic compilation is profile-driven;
Northstar and Acme content belongs in domain packs/seed services rather than
compiler branches. Core policy, compiler, and runner
modules do not import FastAPI; HTTP routes and the Typer CLI call the same async
services. SQLite in WAL mode is the local default, while Alembic and the same
SQLAlchemy models support PostgreSQL.

## Commands

```bash
make bootstrap                 # locked install, migrate, seed, export contracts
make demo                      # local API :8000 + web :3000
make test                      # backend + frontend unit suites
make ci                        # lint, typing, tests, OpenNext build, Wrangler dry run

cd apps/api
uv run aletheia analyze --project northstar-retail --extractor fixture
uv run aletheia compile --project northstar-retail
uv run aletheia test --project northstar-retail --adapter fixture --arms all
uv run aletheia report --latest --format markdown
uv run aletheia worker --once
```

A fresh seed intentionally blocks compilation. Resolve the two critical
current-vs-legacy findings and approve the threshold before compiling. That is
the product's human review gate, not a setup failure.

## Deterministic and optional live modes

The `fixture` runner is deterministic and never calls a model. It is the only
execution path used by the bundled tests. Provider protocols and explicit
failure stubs exist, but an OpenAI-compatible live tool loop is not implemented
and no live result is claimed.

The optional tau2 Retail sync is provenance-checked:

```bash
make benchmark-sync
```

It targets `sierra-research/tau2-bench` tag `v1.0.1`, verifies the reviewed
commit prefix, and records selected paths, hashes, licence, and task IDs. Sync
is optional and does not execute or score the benchmark.

## Verification boundary

Gate 1 is complete in the verified local two-domain fixture scope. Final local
results are: 148 passed and one skipped in the default API suite; 40 passed in
the focused regenerated-contract/Gate 1 suite; Ruff and mypy passed; SQLite
Alembic upgrade/drift passed through `0006`; and a fresh real-PostgreSQL
migration integration passed one test with four deselected before its temporary
database was removed. The frontend passed ESLint, strict type checking, all 87
Vitest tests across 23 files, and a production Next.js build including the
dynamic Placements route. The OpenNext bundle passed at compatibility date
`2026-08-04`; Wrangler `4.118.0` type generation, root/staging deploy dry-runs,
and startup check passed. The release dry-run packaged 53 assets and an
8,026.44 KiB bundle (1,666.85 KiB gzip); local active startup measured 40.4 ms.
These remain packaging observations, not production-performance evidence. The
API image initially omitted the pinned compiler-profile directory; release
commit `2329a1e` copies `data/compiler-profiles` into `/data/compiler-profiles`,
and CI now builds the production image and verifies the profile plus both demo
packs before a release can pass.

The focused two-domain browser flow passed 1/1 in 34.6 seconds including fresh
server startup. The complete
Playwright suite passed 6/6 in 1.1 minutes using fresh isolated API/web ports and
Next output. The earlier transient 404 reproduced only with stale reused Next
development output and disappeared on the clean run; no product workaround was
added. `pip-audit` and the production high-severity `pnpm audit` reported no
known vulnerabilities.

The counts below are retained as historical pre-Gate-1/public-guest regression
evidence and must not be substituted for the current Gate 1 test record.

The hosted changes have automated coverage for JWT validation,
tenant scoping, operation idempotency and lease recovery, migrations, CSRF and
Origin checks, the code-only PKCE callback, pre-routing hosted upload rejection,
session-cookie refresh, Turnstile token reuse prevention, operation polling,
strict Draft 2020-12 tool schemas, exact USD minor-unit fixtures,
build/evidence contracts, strict TypeScript, the Next.js production build, the
OpenNext Cloudflare bundle, and a five-flow local Playwright suite. At the
historical `147448a` checkpoint, 71 web unit/component tests passed across 18
files, 116 backend tests passed across the default and PostgreSQL-marked runs,
and five browser flows passed locally. The successor Gate 1 release has the
separate current test and hosted evidence recorded below. A real local
PostgreSQL 14 run also passed the empty-database migration,
Supabase-named role
privilege denial, bootstrap, queued build/run worker, polling, and downgrade
path. A real two-session PostgreSQL test also proves that snapshot-consuming
operations and child-row mutations take locks in the same `Project → child`
order, so a mutation cannot cross the captured-input fence.

The verified Gate 1 backend, web, build, Worker dry-run, and clean six-flow
browser checks all passed locally. [GitHub Actions run
#30970432139](https://github.com/amanda-yin-x/aletheia/actions/runs/30970432139)
is green on release commit `2329a1e`, including the production API-container
smoke that checks the pinned profile and both fixture packs. The hosted database
is now at `0006_gate1_compilation_contracts`, and Render deploy
`dep-d9pa9f6417fc73dfhcvg` is live. Fresh staging and production guests
completed Turnstile/session/bootstrap/navigation, basic Northstar/Acme
inventory checks, and bounded ownership/reference probes. The complete guest
build/run/report/download path, detailed Acme review/build flow, adversarial
cross-user isolation, limits, expiry/cleanup, reset denial, and waitlist
persistence still require connected verification. The earlier
permanent-user Northstar staging lifecycle remains historical evidence rather
than proof of the new release's complete workflow.

For approved, machine-decidable rules, the covered policy adapter can
deterministically allow, block, or request approval before a covered tool call
executes. This applies only to configured semantics and calls routed through
that adapter. Exact provenance and structural preservation checks establish
deterministic build conformance; `behavioral_fidelity` remains `not_measured`.
See [docs/evidence-boundary.md](docs/evidence-boundary.md).

## Deployment status

| Area | Status | Meaning |
|---|---|---|
| Public landing and guest entry | Gate 1 deployed on staging and production; guest E2E pending | Fresh guest bootstrap passed on staging at `02:53:56Z` and production at `02:59:13Z`; basic two-domain navigation/inventory and bounded isolation passed on both. Full workflow verification remains pending. |
| Permanent-account auth and session refresh | Authenticated staging path verified with limits | Email magic link works for authorized project-team addresses. Manual OTP and GitHub remain disabled. |
| Same-origin API proxy | Deployed; guest bootstrap verified on both Workers | Fresh staging and production guest requests crossed the Worker proxy to Render. Streaming downloads and complete mutation paths still need release-specific verification. |
| FastAPI JWT, origin authentication, and tenancy | Gate 1 API deployed; bounded guest isolation verified | Render deploy `dep-d9pa9f6417fc73dfhcvg` at `2329a1e` is live with Alembic `0006`; fresh staging/production bootstrap and bounded ownership/reference probes passed. Complete resource-lifecycle verification remains pending. |
| Guest limits and retention | Implemented in source; hosted lifecycle verification pending | 30 successful writes, six live operations, no reset, seven-day access TTL, and 30-day cleanup at startup/every 24 hours with a dry-run CLI and fail-open alerts. |
| Edge/API request controls | Worker bundle deployed; complete hosted verification pending | Per-user 120 general/90 polling/30 heavy per-location thresholds, 64 KiB mutation bodies at both hops, and an 85-second response-header deadline. HTTP-to-HTTPS and the unauthenticated API boundary pass; the remaining Worker/API controls still need exercise. |
| Waitlist | Implemented in source; hosted submission verification pending | Normalized unique consent email behind the authenticated guest/permanent API; consent survives guest cleanup. |
| PostgreSQL migrations and operation lifecycle | Gate 1 migration applied; operation lifecycle pending release verification | Hosted Alembic is at `0006_gate1_compilation_contracts`. A protected pre-migration `0005` archive exists, but restore has not been drilled. |
| Cloudflare + Render + Supabase integration | Gate 1 release deployed; bootstrap/navigation verified | Commit `2329a1e` is on staging version `7a049fd2-5053-4334-bea1-92d7f1099235` and production version `091618a0-3582-48f3-9b53-8d2733387ed8`; Render is `dep-d9pa9f6417fc73dfhcvg`. Complete guest build/run/report/download and detailed Acme workflow verification remain open. |

See [docs/deployment.md](docs/deployment.md) for the exact runbook.

## Current limitations

- Release commit `2329a1e` is deployed on both named staging and canonical
  production. Fresh guest bootstrap, basic Northstar/Acme navigation and
  inventory, and bounded ownership/reference isolation passed on both. Those
  narrow gates do not verify complete build/run/report/download, quotas,
  cleanup, or production reliability. Prior Worker versions remain rollback
  targets.
- Email magic-link delivery currently uses Supabase's default SMTP and is
  limited to authorized project-team addresses. Custom SMTP is required before
  general sign-up; manual email OTP and GitHub OAuth are currently disabled.
- Render Free sleeps after idle periods and can take roughly a minute to wake.
  The bounded “Waking your workspace…” recovery UI improves the demo path but
  is not an availability guarantee.
- The verified local Gate 1 implementation supplies a generic compiler/profile and a second
  Acme appointments corpus. Fixture findings, seeded reviews, and replay
  trajectories remain domain-specific evaluation code; arbitrary extraction,
  general conflict analysis, temporal monitoring, and live integrations do not
  exist.
- Compilation reports structural routing, exact provenance, protected-literal
  checks, and declared linkage. It does not measure semantic equivalence or
  behavioral fidelity, and it does not prove that a smaller kernel improves
  model quality or cost.
- Runs verify the selected build root and load its stored policy, test
  specifications/trajectories, tool registry, and fact metadata. A live test row
  remains only as relational identity; run, trace, and report presentation uses
  the stored result snapshot.
- The settled backend suite reproduces equivalent build roots byte-for-byte.
  GitHub Actions run `30970432139` passed on release commit `2329a1e`, including
  the API-container runtime-data smoke. Bundles
  remain unsigned database records rather than signed objects in an
  append-only release store.
- Tenant authorization is enforced in FastAPI query scopes; Postgres RLS is not
  defined. On the hosted Supabase target, the Data API is disabled,
  `anon`/`authenticated` hold no application-table privileges, and a
  transactionally created probe table inherited the expected default denial.
  RLS or a private-schema/least-privilege server role remains the stronger next
  boundary before broader customer data or team functionality.
- The hosted Render blueprint uses inline operations on a Free web service. A
  separately deployed durable worker is not part of that free hosted topology.
- Guest workspaces are temporary and bounded: 30 successful writes, six live
  operations, no reset, seven-day access, and cleanup eligibility after 30
  days. They are for evaluating Northstar, not storing customer data.
- Hosted uploads and arbitrary project creation are disabled. The waitlist
  stores a normalized unique consent email separately so consent survives
  guest-workspace cleanup.
- Guest cleanup runs once during API startup and then every 24 hours; failures
  are alerted without taking readiness down. It also removes anonymous
  Supabase Auth identities older than 30 days that never bootstrapped an app
  account.
- No team invitation, role administration, approval inbox, audit-ledger,
  billing/plan administration, object-storage, artifact-signing,
  release-promotion, or customer runtime SDK exists yet.
- No OCR, URL ingestion, arbitrary policy code, or live-model tool loop exists.
- The fixture runner validates every proposed call against its build-pinned
  Draft 2020-12 tool schema before policy evaluation or execution, including
  types, required fields, nested schemas, and unexpected properties. Northstar
  money uses exact `{currency: "USD", minor_units}` values.
- The bounded interpreter supports tool/domain/lifecycle scope, fact and
  prior-event requirements, correlated approvals, exceptions,
  `not_applicable`, and fail-closed `indeterminate` results. It is still an
  in-memory fixture adapter: there is no typed fact catalog, multi-currency
  model, generic timezone/temporal monitor system, or customer runtime SDK.

## Documentation

- [Hosted workspace: built, verified, pending, and next](docs/hosted-workspace.md)
- [Current state and production roadmap](docs/current-state-and-production-roadmap.md)
- [Deployment and hosting runbook](docs/deployment.md)
- [Machine-readable capabilities](docs/capabilities.json)
- [Architecture](docs/architecture.md)
- [Evidence boundary](docs/evidence-boundary.md)
- [Design references and decisions](docs/design-references.md)
- [90-second walkthrough](docs/demo-script.md)
- [Build plan and gates](docs/build-plan.md)
- [Gate 1 local verification report](docs/gate-1-verification-report.md)
- [Independent product and engineering review v2](docs/aletheia_independent_review_and_product_decision_v2.md)
- [Repository continuation and Gate 1 handoff v3](docs/aletheia_refined_codex_execution_handoff_v3.md)
- [Research map v2 (80 retained sources)](docs/aletheia_research_map_80_sources_v2.md)

## License and acknowledgements

Aletheia is released under the [MIT License](LICENSE). Third-party data,
libraries, the project-scoped Hallmark skill, and research references are
documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and
[docs/design-references.md](docs/design-references.md).
