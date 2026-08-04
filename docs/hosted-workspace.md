# Hosted workspace: what has been built and what comes next

**Updated:** 2026-08-03  
**Purpose:** a detailed, plain-language handoff for understanding the current
system without reading the entire codebase

## Short answer

Aletheia now has a workable authenticated hosted architecture in code. A visitor
can start on a public landing page, sign in through Supabase, enter a personal
Northstar workspace, review policy evidence, compile a candidate through an
operation, run the deterministic comparison, inspect traces, and export a
report. Browser API traffic goes through the Cloudflare application instead of
calling the Python API directly. FastAPI validates both the Cloudflare origin
credential and the user's Supabase JWT, then scopes every resource through the
user's workspace membership.

The external services are not yet verified together as one live system. Supabase Auth and
Postgres, Render, GitHub OAuth, SMTP, Turnstile, runtime secrets, target database
migration, and public-origin smoke tests still need to be provisioned and
verified. The honest status is:

> **Implemented with the complete local repository suite passing; GitHub CI and
> hosted verification are pending.**

## 1. What a user will experience

### Public visitor

The landing page remains public. It explains:

- why conflicting policy documents are dangerous for an agent;
- the concrete 30-day/60-day and `$200`/`$250` refund conflict;
- the difference between proposing and executing a tool call;
- how Aletheia reads, resolves, compiles, and records evidence for a policy change;
- what evidence the system does and does not establish.

The landing page does not query private projects. Every workspace CTA goes to
`/demo`.

### Unauthenticated workspace visitor

Opening `/demo`, a project, a run, a report, or a trace triggers the protected
route boundary. The app preserves a safe relative return path and redirects to
`/login`.

The login page supports:

- GitHub OAuth;
- email magic link;
- email one-time code;
- Turnstile on email requests.

Turnstile tokens are single-use. After every email request—successful or
failed—the component discards the token and remounts the widget. A second
request cannot accidentally replay a consumed token.

### First authenticated visit

`/demo` calls:

```http
POST /api/v1/workspaces/bootstrap
```

The backend creates or reuses:

- one `user_account` keyed by the Supabase `sub` claim;
- one personal workspace owned by that subject;
- one Northstar project inside the workspace.

The derived workspace slug includes a hash of the user subject, so users do not
compete for one fixed `northstar-workspace` slug. Repeating bootstrap returns the
same workspace/project and reports that it was not newly created.

The browser then navigates to:

```text
/projects/{project_id}/overview
```

### Policy workflow

The authenticated user can:

1. inspect the project summary;
2. read normalized sources with numbered lines;
3. see the exact source quote attached to each rule;
4. resolve the two critical seeded conflicts;
5. edit a bounded condition value;
6. approve or reject a rule revision;
7. compile a candidate only after critical findings are resolved;
8. inspect generated prompt, workflow, policy, tests, source map, and manifest;
9. run the build-pinned comparison across its labelled arms;
10. inspect a trace that distinguishes proposal, decision, execution, and state
    change;
11. create and download a Markdown or JSON evidence report.

### Account and logout

The header reads `GET /api/v1/me` and shows the signed-in email plus the first
workspace and role. Logout:

- requires the same Origin/CSRF protections as other mutations;
- signs out the local Supabase session;
- clears the CSRF cookie;
- clears React Query state;
- clears browser Cache Storage;
- returns to `/login`.

## 2. How authentication remains valid during navigation

Supabase stores the browser session in cookies. A Server Component can read but
cannot reliably persist refreshed cookies. The web app therefore refreshes the
session before protected rendering:

1. the Next.js request proxy creates a per-request Supabase server client;
2. `supabase.auth.getClaims()` verifies or refreshes the token;
3. refreshed values are written to the current request so the protected Server
   Component sees them;
4. the same values are written to the response so the browser stores them;
5. an invalid session redirects to login;
6. protected layouts verify the user again before rendering;
7. API route handlers verify the user on every request.

There is also a no-store `/auth/session` route available for an explicit session
check/refresh.

The implementation intentionally uses Next.js 16's deprecated `middleware.ts`
convention so this boundary runs in the Edge runtime. Next.js 16 `proxy.ts`
always uses the Node.js runtime, and OpenNext 1.20.2 for Cloudflare does not yet
support Node middleware. CI validates the production and staging bundles, and
the file can move to `proxy.ts` when the adapter closes that compatibility gap.

## 3. Why the browser does not call Render directly

Every application request uses a same-origin URL such as:

```text
https://aletheia.aletheia-web.workers.dev/api/v1/projects/...
```

The Cloudflare route handler forwards it to Render. This provides one clear
security boundary:

- the browser cannot choose a different API origin;
- the browser's Authorization header is discarded;
- the browser's `X-Aletheia-Origin-Token` is discarded;
- the server verifies the Supabase session before using its access token;
- the real bearer and origin token are attached only inside the Worker;
- cookies are not forwarded to FastAPI;
- mutation requests need exact Origin and CSRF values;
- report exports stream through without buffering the entire file;
- private responses are not cached.

Production fails closed if `API_ORIGIN_URL` or `API_ORIGIN_TOKEN` is missing.
Local development defaults the API origin to `http://localhost:8000` only when
not running in production.

## 4. What FastAPI verifies

The production API router requires two independent credentials.

### Cloudflare-to-Render origin credential

FastAPI compares `X-Aletheia-Origin-Token` to `API_ORIGIN_TOKEN` using a
constant-time comparison. It does not make the Render hostname private by
itself, but calls that bypass the configured web origin cannot use product API
routes without knowing this secret.

### Supabase user credential

FastAPI validates the bearer JWT with the configured JWKS and requires:

- an allowlisted asymmetric algorithm (`ES256`, `RS256`, or `EdDSA`);
- a key ID;
- valid signature;
- exact issuer;
- expected `authenticated` audience;
- `exp`, `iat`, and non-empty `sub`;
- `role=authenticated`;
- no anonymous-user claim.

JWKS lookup is cached for a bounded period, and the blocking key lookup/decode
runs off the async event loop.

Local/test mode never performs these hosted checks; it uses a fixed development
identity. That bypass is selected by `ENVIRONMENT=local|test`, never by a
missing token in production.

## 5. How tenancy works

The data hierarchy is:

```text
user account
  └─ workspace membership (owner/admin/editor/viewer)
       └─ workspace
            └─ project
                 ├─ documents
                 ├─ rules
                 ├─ findings
                 ├─ builds
                 ├─ test cases
                 ├─ runs → scenario results → trace events
                 ├─ reports
                 └─ operations/jobs
```

FastAPI never authorizes a child row only by its UUID. It joins the row through
its project/workspace and the authenticated subject's membership. Reads accept
owner/admin/editor/viewer. Writes accept owner/admin/editor. Workspace resets
require owner/admin. Missing membership returns a not-found error.

Important boundary: these are application-layer checks. The migrations do not
yet create PostgreSQL Row Level Security policies. The Supabase Data API must
not expose these tables to browser clients until RLS or an equivalent database
grant/private-schema design is implemented and tested.

Team invitations and role management are also not present. The schema is ready
for more than one membership, but the product currently bootstraps a personal
owner workspace.

## 6. How builds and runs work now

Build and run endpoints no longer pretend that potentially long work is an
immediate resource response. They return:

```http
HTTP/1.1 202 Accepted
Location: /api/v1/jobs/{operation_id}
```

```json
{
  "id": "operation UUID",
  "workspace_id": "workspace UUID",
  "kind": "compile or run",
  "status": "queued | running | succeeded | failed | dead_lettered | cancelled",
  "progress": 0,
  "resource_type": "build or run",
  "resource_id": null,
  "attempt_count": 0,
  "max_attempts": 3,
  "error": null,
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

The web app polls `GET /api/v1/jobs/{id}` until a terminal status. On success it
requires:

- the expected `resource_type`;
- a syntactically safe non-empty `resource_id`;
- a fetched resource with that exact ID;
- a resource belonging to the project that submitted the work;
- for runs, the selected build relationship.

Only then does navigation occur. Failure and dead-letter messages remain on the
current page.

### Idempotency and stale inputs

Bootstrap is naturally idempotent. Build/run requests carry an
`Idempotency-Key`. The backend scopes it by workspace, project, and operation
kind, records a request fingerprint, returns the existing operation for a true
retry, and rejects reuse with different inputs.

The operation also captures a fingerprint of the mutable rules, findings,
documents, tests, and selected build. If inputs change while work waits in a
queue, execution fails as stale instead of silently using a different state.

### Inline hosted mode versus worker mode

The operation contract is identical in both modes.

- Local Compose can run a separate SQL worker.
- The worker claims with `SKIP LOCKED` on PostgreSQL, limits one running job per
  project, assigns a lease, recovers expired work, retries unexpected failures,
  and dead-letters exhausted jobs.
- The current Render Free blueprint uses `DEMO_INLINE_JOBS=true`; the API
  executes the operation before returning the `202` body, so it may already be
  `succeeded` when the client receives it.

A continuously running hosted worker is still a production next step.

## 7. Cold-start behavior

Render Free can sleep. Ordinary failures should surface quickly, so the web app
does not retry every mutation. It grants the longer recovery window only to
idempotent bootstrap/build/run requests:

- transient gateway/network failures use bounded exponential delay;
- total wake recovery is capped at about 85 seconds;
- after the first retry the UI says **“Waking your workspace…”**;
- the same idempotency key is reused within that attempt;
- after the window ends, the user gets an error and an explicit Retry action;
- the normal read path has a much smaller retry budget.

This handles a common demonstration cold start. It is not an SLO and cannot
guarantee recovery if both Render and Supabase are paused or unavailable.

## 8. Current feature status

| Feature | Status | Notes |
|---|---|---|
| Marketing landing | Implemented; locally verified | Public and independent of private API data. |
| Login UI | Implemented; locally verified | Real provider delivery pending hosted verification. |
| Session refresh/protected routes | Implemented; locally verified | Focused cookie propagation test passes. |
| Turnstile | Implemented; locally verified | Real widget/secret pairing pending. |
| Same-origin proxy | Implemented; locally verified | Render public-origin test pending. |
| JWT/origin verification | Implemented; locally verified | External JWKS and direct Render-origin checks remain hosted gates. |
| Personal workspace bootstrap | Implemented; locally verified | Hosted two-user verification pending. |
| Tenant-scoped API | Implemented; locally verified | App scopes and PostgreSQL role revocations pass locally; target Data API denial remains pending. |
| Rule review/build gate | Implemented; evaluation-limited | Northstar semantics. |
| Compiler/artifacts | Implemented; evaluation-limited | Focused byte-root, build-pinning, and aligned build/evidence schema-v0.3 checks pass; storage and signing gaps remain. |
| Operation contract/polling | Implemented; locally verified | Inline on current Render Free blueprint. |
| Labelled-arm run/trace/report | Implemented; evaluation-limited | Deterministic fixture, no live model. |
| Report streaming | Implemented; locally verified in build/tests | Public network path pending. |
| Account/logout/cache clear | Implemented; locally verified | Real Supabase revocation pending. |
| Supabase Postgres target | Configured in code | External project/migration pending. |
| Render deployment | Blueprint implemented | Service existence and behavior not claimed. |
| Current Cloudflare revision | Build implemented and locally verified | Production deployment pending. |

## 9. Verification completed in this implementation pass

### Web

- ESLint passed.
- Strict TypeScript passed.
- 32 Vitest tests passed across ten files.
- Next.js production build passed.
- OpenNext Cloudflare build passed and emitted a Worker bundle.
- Five Playwright Chromium flows passed against a dedicated migrated/reset
  SQLite database.
- Focused tests cover:
  - session cookie refresh on both request and response;
  - safe redirect parsing;
  - mutation Origin/CSRF checks;
  - queued/running/success operation polling;
  - all modeled/compatible failure terminal states;
  - unknown operation status remaining non-terminal;
  - explicit source-linked conflict resolution payloads;
  - API-derived run/evidence counts and coverage gating;
  - Turnstile token destruction and widget remount.

### Backend verification

- JWT verification and invalid-token rejection;
- workspace bootstrap and idempotency;
- cross-tenant and cross-project denial;
- build/run OperationOut and polling;
- idempotency conflict;
- stale input rejection;
- one operation per project;
- lease recovery and dead-lettering;
- SQLite migration compatibility;
- empty PostgreSQL migration, Supabase-role privilege revocation/default-grant
  checks, bootstrap, and queued worker lifecycle.

The default local run passed 110 tests with the PostgreSQL-only case skipped;
the isolated PostgreSQL 14 run passed that remaining case. All 111 collected
backend tests therefore passed across the two local runs. GitHub's clean
PostgreSQL 17 job remains unverified until the commit is pushed and Actions
finishes.

### Deliberately not claimed

- no live Supabase login was completed;
- no real email or GitHub OAuth callback was completed;
- no hosted Supabase database was migrated;
- no Render service wake was measured;
- no current-revision production Cloudflare deployment was confirmed;
- no full public Cloudflare → Render → Supabase workflow passed;
- no locked Docker image smoke ran because a container runtime was unavailable;
- no penetration, load, accessibility-conformance, backup/restore, or disaster
  recovery exercise was completed.

## 10. Known issues that matter most

### Database isolation needs a second layer

FastAPI tenancy tests are valuable, but an application bug should not be the
only thing separating tenants. Add and test RLS or keep application tables in a
non-exposed private schema with a least-privilege server role.

### Build-pinned evidence is local fixture evidence, not a signed release

The runner now verifies the selected build root and every stored digest, then
uses build-pinned policy, test specifications/trajectories, tools, and fact
metadata. Scenario results store stable test snapshots. A live test row remains
only for relational FK mapping; run, trace, and report labels use the stored
snapshot. The Pydantic and exported build/evidence schema-v0.3 contracts validate the compiled
manifest, pinned runtime inputs, policy, tests, dataset, trace, and report.

The fixture runtime pins domain and lifecycle, validates each tool proposal
against its Draft 2020-12 schema before policy evaluation or execution, uses
exact USD minor-unit amounts, and reports computed rule/source/boundary
coverage. These are bounded deterministic-runner guarantees. They do not turn
the in-memory adapter into a customer enforcement integration or support a
typed fact catalog, multi-currency semantics, or a generic temporal monitor.

### Content addressing is not release authenticity

Focused checks now produce byte-identical roots for equivalent builds. The
exact manifest bytes form the root and cover every other artifact. Those hashes
detect changed content; they do not prove who published it, when it became
active, or which runtime consumed it. Artifacts also remain database JSON rather
than signed objects in a release store.

### Evidence is not signed

Hashes detect changed bytes but do not prove who published the bundle, when it
was active, or which runtime consumed it. Add signing, deployment receipts, and
an append-only audit/transparency record.

### Hosted operations are inline

Inline mode keeps the Free evaluation path simple but ties long work to one API
request. The separate worker code extends owned leases with a heartbeat, but a
serious hosted environment still needs that worker deployed plus scheduled
backoff, cancellation, administration, and alerts.

### The product remains a controlled evaluation

There is no general policy analyzer, production tool SDK, live model loop, or
customer connector. The Northstar scenario demonstrates software behavior inside its
declared boundary; it does not prove business safety in general.

## 11. Next steps, in practical order

### Step 1: provision a staging stack

- Supabase staging project;
- custom SMTP;
- GitHub OAuth app;
- Turnstile widget;
- Supabase database URLs;
- Render staging API;
- Cloudflare staging hostname and secrets.

### Step 2: establish database safety

- review migration on a disposable database;
- verify the checked-in `anon`/`authenticated` current/default privilege
  revocations on the target project;
- confirm Data API exposure is disabled or denied, then decide whether an
  additional private-schema/RLS layer is required before broader data scope;
- run Security Advisor;
- define backups and perform one restore.

### Step 3: pass the hosted smoke test

- both auth methods and session refresh;
- two-user isolation;
- CSRF/origin bypass attempts;
- bootstrap, review, build, run, trace, report, export;
- cold start after 15 minutes;
- logout and browser back/cache behavior;
- log/secret redaction.

### Step 4: finish evidence integrity

- keep runtime/exported schema drift checks green in final CI;
- close the operation fingerprint transaction boundary;
- object storage and signatures;
- release promotion/rollback.

### Step 5: turn personal evaluation into a team product

- invitations and roles;
- review assignments/comments/two-person approval;
- production ingestion and connectors;
- audit explorer, notifications, settings, quotas, privacy operations;
- accessibility and localization.

### Step 6: add live behavior safely

- shadow mode first;
- sandbox/staging transactional tool adapters;
- signed bundle verification at the tool boundary;
- repeated live trials with calibrated evaluation;
- a narrow guarded canary with kill switch and rollback.

## 12. Where to look in the repository

| Concern | Primary files |
|---|---|
| Supabase configuration/clients | `apps/web/lib/supabase/` |
| Protected cookie refresh | `apps/web/middleware.ts` |
| Login/callback/logout/session | `apps/web/app/login/`, `apps/web/app/auth/` |
| Same-origin API boundary | `apps/web/app/api/v1/[...path]/route.ts` |
| Browser retries and CSRF | `apps/web/lib/api.ts`, `apps/web/lib/security.ts` |
| Operation polling | `apps/web/lib/operations.ts` |
| Workspace bootstrap | `apps/web/components/demo-entry.tsx` |
| JWT and origin verification | `apps/api/app/auth.py` |
| Tenant scopes | `apps/api/app/tenancy.py` |
| Operation lifecycle | `apps/api/app/operations.py`, `apps/api/app/worker.py` |
| Schema/migrations | `apps/api/app/models.py`, `apps/api/migrations/` |
| Deployment configuration | `render.yaml`, `apps/web/wrangler.jsonc`, `.env.example` |
| Exact deployment procedure | `docs/deployment.md` |
| Machine-readable inventory | `docs/capabilities.json` |

## Final assessment

The review/compiler/runner flow and complete local invariant/contract/browser
suite work inside a controlled deterministic scope, and the repository contains
the hosted security and tenancy path. The next milestone is verifying that same
architecture on real staging infrastructure, proving the server-only database
boundary through the Supabase Data API, and exercising two-user isolation before
inviting design partners.
