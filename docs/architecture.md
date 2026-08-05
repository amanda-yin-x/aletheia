# Architecture

Aletheia is a modular monolith with two deliberately separate boundaries: a
hosted identity/request path and a deterministic source-to-artifact compilation
path. FastAPI, Typer, and the SQL operation worker share one service layer;
Next.js is the product surface and the same-origin backend-for-frontend on
Cloudflare.

Gate 1 is complete in the verified local Northstar/Acme fixture scope. That
compiler/UI result is not deployed: the public Workers remain on the separately
recorded `147448a` bundle.

## Hosted request path

```text
public Cloudflare landing/demo
  → Supabase Auth (permanent or bounded anonymous identity)
  → signed HTTP-only session cookies
  → same-origin /api/v1/* Cloudflare proxy
       ├─ refreshes the Supabase session
       ├─ checks mutation origin/CSRF
       ├─ injects the user JWT
       └─ injects the Worker-only origin token
  → Render FastAPI
       ├─ verifies origin secret
       ├─ verifies JWT iss/aud/exp/sub through cached JWKS
       └─ resolves every application resource through workspace membership
  → Supabase Postgres through Supavisor session mode
```

Only `/healthz` and `/readyz` are public on the API origin. Browser code never
receives the Render origin token, database URLs, OAuth secret, Supabase service
role, or Turnstile secret. Supabase provides identity and Postgres; application
tables are accessed through FastAPI, not the Supabase Data API.

`ENVIRONMENT=local` is an explicit development exception with a fixed identity
and SQLite by default. Production fails closed when required JWT, origin,
HTTPS-origin, database, or migration configuration is absent.

## Source-aware compilation path

```text
raw source bytes
  → immutable document version + authority metadata
  → verified source anchor
       (quote, lines, UTF-8 bytes, raw/normalized hashes, parser/normalizer)
  → versioned Rule IR
       (source-anchored or reviewer guidance with reviewer/rationale/reviewed_at)
  → append-only placement decision
  → pinned compiler profile + compilation config
  → prompt kernel / scoped skill / knowledge / guard / test / pending material
  → exact generated spans + source map + routing/preservation/metric evidence
  → content-digested manifest and immutable build/run evidence
```

The generic compiler is profile-driven. It routes reviewed clauses to
`prompt_kernel`, `skill`, `knowledge`, `pre_tool_policy`, `test`,
`human_review`, or `unsupported` with explicit transform/disposition types.
Unknown profile values, incomplete active dispositions, invalid provenance, and
applicable protected-literal loss fail closed.

Reviewer-authored guidance requires an offset-aware review timestamp and cannot
masquerade as source-anchored text. Test-generated span markers are explicitly
`compiler_scaffold`; they do not imply a source quote.

Primary artifacts include `prompt-kernel.md`, `skills/<scope>/SKILL.md`,
`knowledge/<scope>.md`, `policies/tool-policy.json`, `tests/regression.yaml`,
`pending/unsupported-rules.json`, routing/preservation/metrics reports,
`source-map.json`, pinned inputs, and the manifest. The manifest from a concrete
build is the source of truth for its exact artifact set.

Northstar retail and Acme appointments are domain packs. They share compiler
contracts and modules; fixture-specific seeds, findings, rule text, and
evaluation trajectories remain outside generic compilation code.

## Code boundaries

- `apps/api/app/services/compilation`: profile validation, provenance,
  rendering, structural metrics, source-map construction, and bundle assembly.
- `apps/api/app/services/compiler.py`: build orchestration and persisted build
  integration; domain content belongs in seed/domain-pack modules.
- `apps/api/app/services`: deterministic ingest, review, policy, runner,
  metrics, reporting, and seeded domain services without FastAPI imports.
- `apps/api/app/api`: HTTP validation, tenant-scoped orchestration, operation
  resources, error envelopes, and request IDs.
- `apps/api/app/auth.py` and `tenancy.py`: Supabase/Worker authentication,
  memberships, and loaders that return `404` across tenant boundaries.
- `apps/api/app/operations.py` and `worker.py`: idempotent build/run operations,
  leases, bounded attempts, recovery, and inline/free versus worker execution.
- `apps/api/app/models.py` and `migrations`: portable persistence and explicit
  schema evolution for SQLite/PostgreSQL.
- `apps/api/app/adapters`: optional provider/benchmark seams. Their presence
  does not mean a model or upstream benchmark operates.
- `apps/web/app/api/v1/[...path]`: streaming authenticated proxy that does not
  expose browser cookies to Render or buffer report downloads unnecessarily.
- `apps/web`: public product story plus tenant-scoped source, rule/placement,
  build, run, trace, and report inspection.

## Identity, tenancy, and startup

`user_accounts` mirrors the minimum stable Supabase identity. `workspaces` and
`workspace_members` define membership. Projects are workspace-owned and slugs
are unique per workspace. Jobs carry workspace/project identity, and
placements, builds, runs, traces, and reports are loaded through the same
ownership chain.

Bootstrap is idempotent: first access creates a personal workspace and seeded
Northstar project; later access reopens it. Reset replaces only that project’s
seeded contents while preserving its ID. Hosted arbitrary project creation and
source upload remain disabled.

Alembic is the only production schema creator. API/worker startup does not call
`create_all()` or globally seed data. Render Free applies migrations under a
PostgreSQL advisory lock before Uvicorn; a paid topology should move this into a
pre-deploy phase.

## Evidence and execution boundary

Documents preserve the raw input-byte hash, normalized-text hash, normalized
content, line boundaries, MIME/origin, and parser/normalizer identity. Exact
anchors and placements are pinned into builds. Generated spans identify their
artifact range and derivation. Builds pin documents, rules, tests, tools, facts,
profile/config, placements, artifacts, findings, compiler/runtime versions, and
limitations. Runs isolate case/arm state. Reports snapshot completed run
evidence and verify their own content hash.

Policy JSON is data evaluated by an allowlisted interpreter; it cannot import
modules or execute customer code. A covered proposal may mutate fixture state
only after strict schema validation and an allow decision. Structural
preservation metrics and exact provenance do not prove behavioral fidelity,
semantic equivalence, or live-customer safety.

## Deliberately deferred

Gate 1 does not include arbitrary/model-driven extraction, Z3 analysis,
generic temporal monitors, policy mutation scoring, live model/tool execution,
upstream tau execution, a customer dispatcher SDK, signed bundle promotion, or
enterprise ingestion/control-plane features. Database RLS/private-schema
isolation, customer uploads, encrypted object storage, service accounts,
durable approvals, backup/restore drills, production SLO evidence, and
compliance claims also remain separate work.
