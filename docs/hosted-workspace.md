# Hosted workspace: what has been built and what comes next

**Updated:** 2026-08-04  
**Purpose:** a detailed, plain-language handoff for understanding the current
system without reading the entire codebase

## Short answer

Aletheia now has a public-guest candidate for the complete Northstar workspace.
A visitor can open `/demo`, pass Turnstile, receive a signed anonymous Supabase
session, and enter an isolated personal workspace without providing an email.
Inside it they can review policy evidence, compile a candidate, run the
deterministic comparison, inspect traces, and export a report. Browser API
traffic goes through Cloudflare; FastAPI validates both the Cloudflare origin
credential and the signed Supabase JWT, then scopes every resource through the
subject's workspace membership.

Supabase Auth/Postgres, Render, Turnstile, server-only runtime credentials, and
the named Cloudflare staging Worker are provisioned. A permanent-user staging
revision passed the connected personal-workspace, two-user isolation,
review/build/run/trace/report/download, Data API denial, and direct-origin
security path. The newer guest candidate, migration, quotas, cleanup, reset
denial, and waitlist have not been deployed or verified there. The honest
release status is:

> **Permanent-user workflow verified on staging; the public guest candidate is
> not yet deployed; canonical production still serves the preceding
> release.**

Supabase anonymous sign-in is enabled and requires Turnstile. Email magic link
remains available for permanent accounts, but default SMTP reaches only
authorized project-team addresses. Manual OTP and GitHub login are disabled.
Those permanent-account onboarding limits do not block the no-email guest demo.

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

### Guest workspace visitor

`/demo` is public. With no existing session it presents a Turnstile gate, then
calls Supabase anonymous sign-in. Supabase returns a signed JWT with
`role=authenticated` and `is_anonymous=true`; this is a private application
identity, not public database access. The widget token is discarded and
remounted after every attempt because Turnstile responses are single-use.

Important CAPTCHA boundary: Supabase's native integration verifies a successful
Turnstile token, but it does not enforce the token response's `action` or
`hostname` fields. Aletheia's `guest_demo`, `waitlist`, and `login` actions are
client-side labels, not server-enforced authorization claims. The widget
allowlist contains only the canonical and staging hostnames. Local development
uses local auth or Cloudflare's Turnstile test key rather than adding localhost.

Direct project, run, report, and trace routes remain private. A visitor without
a session is redirected to `/login`, while `/demo` can create the bounded guest
session first. Email magic link remains the persistent-account option. A guest
can attach a new email in place and retain the same Supabase subject/workspace;
manual identity linking is enabled for the equivalent future OAuth path. Manual
email-code and GitHub OAuth controls stay deployment-disabled, and existing-
account workspace merge remains future work.

### First signed visit

`/demo` calls:

```http
POST /api/v1/workspaces/bootstrap
```

For a guest or permanent subject, the backend creates or reuses:

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

Guest use is intentionally bounded: no uploads, arbitrary project creation, or
reset; at most 30 successful writes and six live build/run operations; and a
seven-day access TTL. Guest data becomes cleanup-eligible after 30 days.

### Policy workflow

The signed guest or permanent user can:

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

The header reads `GET /api/v1/me` and shows either **Guest demo** or the
permanent account email, plus the first workspace and role. Logout/end session:

- requires the same Origin/CSRF protections as other mutations;
- signs out the local Supabase session;
- clears the CSRF cookie;
- clears React Query state;
- clears browser Cache Storage;
- returns to `/login`.

The landing-page waitlist sends a normalized email through the authenticated
guest/permanent API. The address is unique and idempotent. It is a separate
consent record: guest cleanup clears its user link but preserves the consent,
and waitlist submission does not convert a guest into a permanent account.

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

The Worker configures per-signed-subject Cloudflare thresholds: 120 general, 90
job-polling, and 30 heavy result/report/export requests per minute. Specialized
requests also consume the general budget. Cloudflare evaluates counters per
location and permissively/eventually consistently; this is abuse damping, not
an exact global quota. Missing production bindings fail closed. Mutation bodies
are bounded to 64 KiB while streaming at the Worker and again before
FastAPI/Pydantic materialization.

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
- either a permanent subject or the explicitly bounded
  `is_anonymous=true` guest identity.

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
owner/admin/editor/viewer. Writes accept owner/admin/editor. Permanent-workspace
resets require owner/admin; guest reset is denied regardless of membership.
Missing membership returns a not-found error.

Important boundary: these are application-layer tenant checks. The migrations
do not yet create PostgreSQL Row Level Security policies. On the hosted target,
the Supabase Data API is disabled, `anon`/`authenticated` have zero
application-table privileges, and a transactionally created probe table
inherited the same default denial. That blocks the browser Data API path, but
RLS or an equivalent private-schema/least-privilege server role remains the
stronger defense before broader customer data or team access.

Team invitations and role management are also not present. The schema is ready
for more than one membership, but the product currently bootstraps a personal
owner workspace.

Guest mutations use an account-scoped counter and row lock. A guest receives at
most 30 successful writes and six live operations; the next attempt is rejected
without creating a partial resource. These are evaluation allowances, not a
billing or general quota system.

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

The input-snapshot mutation race is closed for the current resource model:
snapshot-consuming operations lock `Project`, and every child-row mutation
takes the same `Project → child` lock order. A real two-session PostgreSQL test
holds the operation lock, confirms the competing mutation blocks, then confirms
it proceeds only after the operation transaction releases the fence.

### Inline hosted mode versus worker mode

The operation contract is identical in both modes.

- Local Compose can run a separate SQL worker.
- The worker claims with `SKIP LOCKED` on PostgreSQL, limits one running job per
  project, assigns a lease, recovers expired work, retries unexpected failures,
  and dead-letters exhausted jobs.
- The current Render Free blueprint uses `DEMO_INLINE_JOBS=true`; the API
  executes the operation before returning the `202` body, so it may already be
  `succeeded` when the client receives it.
- Render Free rejected the Blueprint `maxShutdownDelaySeconds` field, so the
  checked-in service intentionally omits it and uses Render's 30-second default.

A continuously running hosted worker is still a production next step.

## 7. Cold-start behavior

Render Free can sleep. Ordinary failures should surface quickly, so the web app
does not retry every mutation. It grants the longer recovery window only to
idempotent bootstrap/build/run requests:

- transient gateway/network failures use bounded exponential delay;
- total wake recovery is capped at 85 seconds, and the Worker aborts a fetch if
  upstream response headers have not arrived by that deadline; once headers
  arrive, this bound does not time the streamed response body;
- after the first retry the UI says **“Waking your workspace…”**;
- the same idempotency key is reused within that attempt;
- after the window ends, the user gets an error and an explicit Retry action;
- the normal read path has a much smaller retry budget.

This handles a common demonstration cold start. It is not an SLO and cannot
guarantee recovery if both Render and Supabase are paused or unavailable.

### Guest expiry and cleanup

A guest session is accepted for seven days. Physical deletion is separate. In
hosted Postgres, application guest age is anchored to
`auth.users.created_at`; anonymous identities older than 30 days are selected
with their workspace/project graph. Cleanup also removes anonymous Supabase
Auth identities past the cutoff that never created a `user_accounts` row or
workspace. Upgraded permanent identities are excluded. `aletheia db
cleanup-guests --json` is a dry run by default; `--execute` performs the
reviewed deletion. API startup runs the same cleanup. If cleanup fails, it logs
a structured `guest_cleanup_failed` alert and continues serving, so maintenance
cannot make the preview unavailable. Hosted API lifespan also repeats cleanup
every 24 hours; periodic failure is logged and the loop continues.

Waitlist consent is intentionally outside that cascade. Cleanup nulls its user
link and preserves the normalized unique email record.

## 8. Current feature status

| Feature | Status | Notes |
|---|---|---|
| Marketing landing | Older revision live; guest candidate pending | Public and independent of private API data. Canonical production is stale. |
| `/demo` guest entry | Candidate implemented; hosted verification pending | Turnstile → anonymous Supabase session → isolated Northstar bootstrap. |
| Permanent login UI | Hosted preview operating with limits | Magic link is limited to project-team addresses; manual OTP and GitHub are disabled. |
| Session refresh/private routes | Permanent-user staging path verified | Guest cookie/session behavior still needs hosted verification. |
| Turnstile | Provisioned; guest use pending verification | Supabase CAPTCHA is required for anonymous sign-in. |
| Same-origin proxy | Permanent-user staging path verified | Reverify credential injection/streaming with anonymous JWTs. |
| Edge/API request controls | Candidate implemented; hosted verification pending | Per-location 120 general/90 polling/30 heavy thresholds per subject; 64 KiB mutations at both hops; 85-second response-header deadline. |
| JWT/origin verification | Candidate extended; hosted guest verification pending | Signed anonymous `role=authenticated` JWTs are accepted; direct-origin checks remain. |
| Personal workspace bootstrap | Permanent-user staging path verified; guest pending | Each signed subject receives a distinct repeatable workspace. |
| Tenant-scoped API | Staging verified at the app boundary | Two-user denial passes; hosted Data API is disabled and role grants are zero. Postgres RLS is still absent. |
| Guest limits/reset | Candidate implemented; hosted verification pending | 30 successful writes, six live operations, and reset denied. |
| Guest expiry/cleanup | Candidate implemented; hosted verification pending | Seven-day TTL; auth-created-at 30-day cleanup at startup/every 24 hours, including auth-only anonymous identities; dry-run CLI; failures alert and fail open. |
| Waitlist | Candidate implemented; hosted verification pending | Normalized unique consent survives guest cleanup. |
| Rule review/build gate | Implemented; evaluation-limited | Northstar semantics. |
| Compiler/artifacts | Implemented; evaluation-limited | Focused byte-root, build-pinning, and aligned build/evidence schema-v0.3 checks pass; storage and signing gaps remain. |
| Operation contract/polling | Permanent-user staging path verified | Inline on Render Free; guest six-operation boundary pending. |
| Labelled-arm run/trace/report | Implemented; evaluation-limited | Deterministic fixture, no live model. |
| Report streaming | Staging verified | Markdown/JSON responses traverse both Cloudflare and Render hops. |
| Account/logout/cache clear | Implemented; staging session path verified | Broader browser/back-cache audit remains. |
| Supabase Postgres target | Provisioned and verified | Alembic head applied; Data API off; current/default app-table grants denied. |
| Render deployment | Provisioned and staging verified | Free Virginia service; inline work and cold-start limits apply. |
| Current Cloudflare revision | Guest candidate not deployed | Named staging evidence is for the preceding permanent-user build; canonical production is stale. |

## 9. Verification completed in this implementation pass

### Web

- ESLint passed.
- Strict TypeScript passed.
- In the current guest candidate, all 60 Vitest tests pass across 16 files.
- Next.js production build passed.
- OpenNext Cloudflare build passed and emitted a Worker bundle.
- The settled pre-guest revision passed five Playwright Chromium flows against
  a dedicated migrated/reset SQLite database; the guest candidate still needs
  that browser rerun.
- Focused tests cover:
  - session cookie refresh on both request and response;
  - safe redirect parsing;
  - mutation Origin/CSRF checks;
  - queued/running/success operation polling;
  - all modeled/compatible failure terminal states;
  - unknown operation status remaining non-terminal;
  - explicit source-linked conflict resolution payloads;
  - API-derived run/evidence counts and coverage gating;
  - Turnstile token destruction and widget remount;
  - per-subject general/poll/heavy rate-limit selection and fail-closed missing
    bindings;
  - streaming 64 KiB mutation-body rejection at the proxy; and
  - abort when upstream response headers do not arrive within 85 seconds; this
    bound does not cover a streamed body after headers.

### Backend verification

- JWT verification and invalid-token rejection;
- workspace bootstrap and idempotency;
- cross-tenant and cross-project denial;
- build/run OperationOut and polling;
- idempotency conflict;
- stale input rejection;
- one operation per project;
- `Project → child` locking against a two-session PostgreSQL mutation race;
- lease recovery and dead-lettering;
- API-side 64 KiB hosted mutation-body rejection;
- startup/periodic guest cleanup, auth-created-at anchoring, and removal of
  expired auth-only anonymous identities;
- SQLite migration compatibility;
- empty PostgreSQL migration, Supabase-role privilege revocation/default-grant
  checks, bootstrap, and queued worker lifecycle.

The default local run passed 110 tests with the PostgreSQL-only case skipped;
the isolated PostgreSQL 14 run passed that remaining case. All 111 collected
backend tests therefore passed across the two local runs. GitHub's clean
PostgreSQL 17 job also passed for the settled implementation.

The newer guest candidate passes all 116 backend tests across two local runs:
115 default tests plus the separately executed PostgreSQL-marked test. That real
two-session PostgreSQL path includes the `Project → child` input-snapshot lock
fence. Hosted verification remains separate.

### Hosted staging verification for the preceding permanent-user revision

- the target Supabase database migrated through Alembic head;
- the Data API is disabled, negative REST access is unavailable, current
  `anon`/`authenticated` application-table grants are zero, and a transactional
  probe table inherited zero default grants;
- the Render service validates real Supabase JWTs and rejects missing origin or
  bearer credentials;
- the named Cloudflare staging Worker forwards only server-derived credentials;
- two hosted identities bootstrap distinct personal workspaces and cannot read
  one another's project; and
- the complete deterministic review, compile, 16-case/three-arm run, blocked
  trace, report, and streamed Markdown export path passed with hosted Postgres.

### Deliberately not claimed

- no hosted guest flow is claimed yet: anonymous sign-in, quotas, expiry,
  cleanup, reset denial, and waitlist persistence have not been deployed and
  exercised end to end;
- no hosted claim is made yet for the new per-location rate policies, two-hop
  64 KiB mutation cap, 85-second response-header deadline, 24-hour cleanup loop,
  auth-only identity cleanup, or lock-fence revision;
- no open permanent-account email onboarding is claimed: default SMTP is
  limited to authorized project-team addresses;
- no manual email OTP flow is claimed because it is deployment-disabled;
- no GitHub OAuth callback is claimed because the provider is disabled pending
  OAuth application configuration;
- no production Render availability or SLO is claimed; Free cold-start behavior
  remains a preview limitation;
- no guest-candidate staging or production Cloudflare deployment was confirmed;
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

### Step 1: verify the guest candidate on staging

- deploy the current API/migration and Worker candidate to staging;
- verify Turnstile-protected anonymous sign-in, isolated bootstrap, all guest
  limits, reset/upload/project-creation denial, seven-day expiry, 30-day
  cleanup, fail-open alerting, and waitlist persistence;
- repeat the complete Northstar workflow and cross-tenant security checks with
  guest and permanent identities; and
- promote only the exact passing revision, then repeat the public smoke path and
  record Worker/Render versions, Alembic head, timestamp, and rollback version.

### Step 2: finish permanent-account authentication delivery

- configure custom SMTP and test non-team delivery, link scanners, expiry,
  abuse controls, and recovery;
- create and staging-test the GitHub OAuth application before enabling its
  feature flag;
- keep manual OTP disabled unless its hosted path receives equivalent testing.

### Step 3: strengthen database and operational safety

- keep the Data API disabled and recheck current/default grants after every
  ownership or schema migration;
- add and test RLS or a private-schema/least-privilege server role before
  broader customer data or team access;
- run Security Advisor, define backups, and perform one restore;
- measure a real Free-tier cold start and preserve explicit failure recovery;
- complete logout/back-cache, log-redaction, accessibility, load, security, and
  incident-response checks.

### Step 4: finish evidence integrity

- keep runtime/exported schema drift checks green in final CI;
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

The review/compiler/runner flow works inside a controlled deterministic scope.
Its permanent-user security/tenancy path is connected and verified on the named
staging Worker: Supabase Postgres is migrated, Data API/grant denial is checked,
and two-user isolation plus the complete Northstar lifecycle passed. The newer
public guest candidate is implemented but not deployed or hosted-verified, and
canonical production remains on the preceding release. The immediate milestone
is guest staging verification—not an unqualified production promotion. Broader
permanent-account onboarding still requires custom SMTP and GitHub OAuth; a
production-capable service still requires database defense in depth, paid
availability, observability, recovery drills, and independent
security/accessibility work.
