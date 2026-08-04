# Deployment and hosting runbook

**Snapshot:** 2026-08-04  
**Target:** Cloudflare Workers + Render FastAPI + Supabase Auth/Postgres  
**Current status:** Supabase and Render are provisioned. Commit `147448a` is
deployed as the same bundle on staging Worker version
`3788c6b0-291c-43a9-bef3-b48aaa4a0498` and canonical production Worker version
`935c3c39-f63e-4041-804b-ef40431d50fc`. The public surface and real Turnstile
render are verified; Turnstile token redemption and the complete anonymous
hosted workflow are not.

This runbook distinguishes the deployed Worker bundle, public-edge
verification, the previously verified permanent-user staging lifecycle, and
the still-unverified anonymous lifecycle. The Aletheia Supabase project, its
Postgres schema, the Render service, Turnstile, runtime secrets, and both
Cloudflare Workers exist.
Supabase anonymous sign-in is enabled and requires Turnstile. GitHub OAuth and
custom SMTP do not exist. Do not describe the guest workflow as end-to-end
verified until a real token is redeemed and the remaining checks in section 8
pass.

## 1. Target request path

```text
Browser
  │
  ├─ GET / ──────────────────────────────► public landing page
  │
  └─ GET /demo ──────────────────────────────► public guest entry
       │
       ├─ Turnstile challenge
       ├─ Supabase anonymous sign-in
       │    signed JWT: role=authenticated, is_anonymous=true
       │    email magic link remains an optional permanent-account path
       │
       ▼
Cloudflare Worker: Next.js 16 through OpenNext
       │
       ├─ refreshes Supabase cookies before private workspace rendering
       ├─ creates the anonymous session before workspace bootstrap
       └─ proxies browser calls through same-origin /api/v1/*
              │
              ├─ verifies the user session
              ├─ rejects untrusted mutation Origin/CSRF values
              ├─ applies per-user, per-location general/poll/heavy thresholds
              ├─ caps mutations at 64 KiB; requires response headers by 85 s
              ├─ adds Authorization: Bearer <Supabase access token>
              └─ adds X-Aletheia-Origin-Token from a Worker secret
                       │
                       ▼
Render HTTPS origin: FastAPI
       │
       ├─ checks origin credential and bearer presence before routing
       ├─ rejects hosted document uploads before multipart parsing
       ├─ verifies routed JWTs against Supabase JWKS
       ├─ requires a signed role=authenticated JWT
       ├─ accepts is_anonymous=true for the bounded guest path
       └─ scopes resources through workspace membership
                       │
                       ▼
Supabase Postgres
```

The browser never calls Render directly. `API_ORIGIN_URL`,
`API_ORIGIN_TOKEN`, database URLs, OAuth secrets, SMTP credentials, and any
Supabase service-role key remain server-only. A service-role key is not required
by the current application.

## 2. Status matrix

| Component | Implementation | Verification |
|---|---|---|
| Public landing and `/demo` guest entry | Deployed on staging and production | `/` and `/demo` return `200`; current composite scenario and `ALETHEIA` brand are served; anonymous E2E remains unverified |
| Supabase browser/server clients | Deployed | Permanent-user path previously verified on staging; anonymous sign-in is enabled, but hosted token redemption and bootstrap still need verification |
| Cookie refresh before private rendering | Deployed | Focused tests pass and the permanent-user hosted session path was previously verified; repeat with a guest session |
| Email magic link | Enabled with a preview limitation | Turnstile-protected; Supabase default SMTP sends only to authorized project-team addresses until custom SMTP is configured |
| Manual email OTP and GitHub login | Implemented in code; disabled in deployment | OTP is hidden by runtime configuration; GitHub remains off until its OAuth application and secret are configured |
| Turnstile anonymous sign-in | Deployed; render verified | Real script and challenge frame render and UI reaches `waiting`; the previous `ready()` load failure is gone. Automated browsers were challenged, so token redemption, replay rejection, and guest bootstrap remain unverified |
| Same-origin streaming API proxy | Deployed | Unauthenticated `/api/v1/me` returns `401`; permanent-user staging previously passed downloads and credential filtering; anonymous JWT path remains to verify |
| Origin and CSRF mutation protection | Implemented | Local adversarial checks and hosted boundary checks passed |
| Per-user edge rate policy | Deployed | Per-location 120 general, 90 polling, and 30 heavy thresholds per minute; permissive/eventually consistent rather than an exact global quota; hosted exhaustion verification pending |
| Request size/deadline | Worker and guest-capable API deployed | 64 KiB mutation cap at Worker/API plus 85 seconds to receive upstream response headers; streamed bodies are outside that deadline; hosted anonymous-boundary verification remains pending |
| FastAPI JWT and origin-token checks | Guest-capable API deployed and ready | Existing hosted Supabase JWKS/direct-origin checks passed; Render deploy `dep-d9p481tbedkc73e3677g` is ready, while the anonymous `role=authenticated` token path remains to verify with a redeemed CAPTCHA session |
| Pre-routing hosted upload denial | Implemented | Verified without accepting hosted upload data; focused streaming-body coverage also passes |
| Workspace tenancy and scoped resources | Implemented in source | Permanent-user two-user isolation previously passed; guest isolation, no-reset, quotas, and expiry remain to verify hosted |
| Guest write/operation limits | Implemented in source | 30 successful writes and six live operations per guest; hosted exhaustion tests pending |
| Guest retention cleanup | Implemented in source | Seven-day access TTL; 30-day cleanup at startup and every 24 hours; dry-run CLI; failure alerts and fails open; hosted verification pending |
| Waitlist consent | Implemented in source | Normalized unique email behind guest/permanent authenticated API; survives guest cleanup; hosted submission and persistence verification pending |
| Alembic PostgreSQL migration | Guest migration applied on hosted startup | Render logs record `0004 → 0005_guest_access_waitlist` before successful startup; the existing hosted Data API/grant checks passed, while the connected guest data lifecycle remains unverified |
| Render service | Guest-capable API deployed and ready | Free Virginia deploy `dep-d9p481tbedkc73e3677g` is connected to Supabase through SSL and `/readyz` returns `200`; the permanent-user lifecycle previously passed, while the guest lifecycle remains unverified |
| Cloudflare runtime configuration | Deployed | Exact commit bundle is on named staging and canonical production; HTTP redirects to HTTPS with `308` |
| Full Cloudflare → Render → Supabase flow | Permanent-user staging workflow previously verified | Guest token redemption, bootstrap, workflow, and retention boundaries remain unverified |

## 3. Local mode and hosted mode are intentionally different

### 3.1 Local no-key mode

Use this for development and the bundled deterministic demonstration:

```text
API
ENVIRONMENT=local
DATABASE_URL=sqlite+aiosqlite:///./aletheia.db
MIGRATION_DATABASE_URL=sqlite:///./aletheia.db
WEB_ORIGIN=http://localhost:3000
DEMO_MODE=true
DEMO_INLINE_JOBS=true

Web
AUTH_MODE=local
SITE_URL=http://localhost:3000
API_ORIGIN_URL=http://localhost:8000
```

`AUTH_MODE=local` is accepted only when `SITE_URL` resolves to localhost,
`127.0.0.1`, or loopback IPv6. `ENVIRONMENT=local` gives FastAPI a fixed local
identity. The Next.js development server also selects the same local web bypass
when `AUTH_MODE` and Supabase configuration are both absent. That fallback is
disabled when `NODE_ENV=production`; neither bypass is inferred in production.

Start the local path with:

```bash
make bootstrap
make demo
```

For the Compose topology, the checked-in configuration supplies the same
explicit local modes plus a matching non-production origin token:

```bash
docker compose up --build
```

Do not copy local mode values into a public deployment.

### 3.2 Hosted fail-closed mode

The hosted services must use:

```text
API: ENVIRONMENT=production
Web: AUTH_MODE=supabase
```

`ENVIRONMENT` defaults to `production`; local and test commands must opt into a
non-production mode explicitly. The API refuses to start in production if its
PostgreSQL/TLS, Supabase verification, origin-token, or HTTPS web-origin
requirements are incomplete. The web app never infers local auth in a
production build: it refuses protected access when HTTPS Supabase/Turnstile
configuration is incomplete and requires both an HTTPS API origin and the
server-only origin secret before proxying.

## 4. Environment variable ownership

### 4.1 Cloudflare Worker runtime

| Variable | Secret | Required | Purpose |
|---|---:|---:|---|
| `AUTH_MODE=supabase` | No | Yes | Disables local auth bypass. Committed in `wrangler.jsonc`. |
| `SITE_URL` | No | Yes | Exact web origin and auth callback base. Committed separately for the canonical and named staging Workers. |
| `API_ORIGIN_URL` | **Yes** | Yes | HTTPS Render origin, stored as a Worker secret and read only by server route handlers. |
| `API_ORIGIN_TOKEN` | **Yes** | Yes | Shared secret sent to FastAPI as `X-Aletheia-Origin-Token`. |
| `SUPABASE_URL` | No | Yes | Supabase project URL. |
| `SUPABASE_PUBLISHABLE_KEY` | No | Yes | Browser-safe publishable key used by Supabase Auth. |
| `TURNSTILE_SITE_KEY` | No | Yes | Browser widget key. Production auth fails closed when it is absent. The matching secret is configured in Supabase, not in this Worker. |
| `GITHUB_AUTH_ENABLED=false` | No | Yes | Keeps the GitHub control hidden until the OAuth application and Supabase provider are configured and verified. |
| `EMAIL_OTP_ENABLED=false` | No | Yes | Keeps manual code entry hidden; email magic-link authentication remains available. |

There are intentionally no `NEXT_PUBLIC_*` variables. Browser-safe Supabase and
Turnstile values are passed to the login component from server-rendered runtime
configuration; the API origin and origin token are never serialized to the
browser.

`wrangler.jsonc` also binds three Cloudflare Rate Limiting resources, keyed by
the verified Supabase subject: 120 general, 90 job-polling, and 30 heavy
result/report/export requests per 60 seconds. Poll/heavy traffic consumes its
specialized budget and the general budget. Cloudflare evaluates these counters
per location and permissively/eventually consistently; they are not exact
global quotas. Missing bindings fail closed in production. The proxy streams
mutation bodies only up to 65,536 bytes. Its 85-second fetch deadline ends when
upstream response headers arrive; it does not bound a streamed response body
after those headers.

### 4.2 Render FastAPI runtime

| Variable | Secret | Required | Purpose |
|---|---:|---:|---|
| `ENVIRONMENT=production` | No | Yes | Enables fail-closed hosted validation. |
| `DATABASE_URL` | **Yes** | Yes | Async SQLAlchemy PostgreSQL connection for application traffic. |
| `MIGRATION_DATABASE_URL` | **Yes** | Yes | Synchronous PostgreSQL connection used by Alembic/advisory locking. |
| `SUPABASE_ISSUER` | No | Yes | Expected JWT issuer, normally `https://<ref>.supabase.co/auth/v1`. |
| `SUPABASE_JWKS_URL` | No | Yes | Supabase JWKS endpoint. |
| `SUPABASE_AUDIENCE=authenticated` | No | Yes | Expected audience. |
| `API_ORIGIN_TOKEN` | **Yes** | Yes | Must exactly match the Cloudflare secret. |
| `WEB_ORIGIN` | No | Yes | Exact Cloudflare site origin. |
| `DEMO_MODE=true` | No | Current evaluation | Keeps uploads disabled for the hosted Northstar workspace. |
| `DEMO_INLINE_JOBS=true` | No | Current Free topology | Executes operations in the web process because a Free background worker is not configured. |
| `GUEST_MAX_MUTATIONS=30` | No | Yes | Caps successful guest writes. |
| `GUEST_MAX_OPERATIONS=6` | No | Yes | Caps live build/run operations available to a guest. |
| `GUEST_SESSION_TTL_HOURS=168` | No | Yes | Denies guest workspace access after seven days. |
| `GUEST_RETENTION_DAYS=30` | No | Yes | Selects expired guest data for cleanup after 30 days. |
| `GUEST_CLEANUP_INTERVAL_HOURS=24` | No | Yes | Repeats hosted guest cleanup every 24 hours after the startup pass. |
| `API_MAX_BODY_BYTES=65536` | No | Yes | Independently rejects oversized hosted mutations before FastAPI/Pydantic materializes them. Must match the Worker cap. |
| `DEMO_RESET_SECRET` | **Yes** | No | Local-only compatibility setting. Hosted guest reset is always denied; permanent owner/admin reset remains separately authorized. |
| `LOG_LEVEL` | No | No | Runtime log level. |

The pool settings default to three persistent connections plus two overflow
connections. Confirm the selected Supabase connection endpoint and plan can
support the total connections before increasing Render instances or adding a
worker.

### 4.3 Values that do not belong in either browser or repository

- `API_ORIGIN_TOKEN`;
- PostgreSQL usernames, passwords, and connection strings;
- GitHub OAuth client secret;
- Turnstile secret key;
- SMTP password;
- Supabase service-role or secret keys;
- Render deploy hook URLs.

`.env`, `.dev.vars`, generated databases, and deployment output are ignored.
`apps/web/.dev.vars.example` contains placeholders only.

## 5. Supabase state and remaining provider work

The dedicated Aletheia Supabase project is provisioned in `us-east-1`. Its Auth
issuer/JWKS settings, canonical and staging callback allowlist, publishable
configuration, Supavisor session-pooler connections, and managed `Aletheia
sign-in` Turnstile integration are configured. Database and origin credentials
remain in platform secret stores; no service-role or secret API key is used by
the application.

Alembic has upgraded the hosted database through head. The release database
boundary was then checked independently of FastAPI:

- the Data API is disabled (`db_schema` is empty and the REST probe is
  unavailable);
- `anon` and `authenticated` have zero privileges on application tables; and
- a transactionally created probe table inherited zero privileges from the
  migration role's default grants.

Those checks prevent browser Data API access, but they are not tenant-level
Postgres RLS. FastAPI membership scopes remain the tenant boundary for this
preview. Add RLS or move application tables behind a private-schema,
least-privilege server role before broader customer data or team access.

The current Supabase configuration enables anonymous sign-in, manual identity
linking, and the managed Turnstile CAPTCHA. Supabase issues a signed session
with `role=authenticated` and `is_anonymous=true`; this is an Auth identity,
not direct database access through the Supabase Postgres `anon` role.
Application tables remain reachable only through FastAPI. An anonymous visitor
can attach a new email with `updateUser()` without changing the JWT subject or
losing the workspace. The GitHub control remains disabled, but its future
anonymous upgrade uses `linkIdentity()` instead of replacing the guest subject.

Supabase's native CAPTCHA integration verifies successful Turnstile completion
but does not enforce the response's `action` or `hostname` fields. Aletheia's
`guest_demo`, `waitlist`, and `login` actions are client-side labels, not
server-side policy assertions. The Turnstile widget allowlist contains only the
canonical and staging hostnames. Local development uses local auth or
Cloudflare's Turnstile test key; do not add localhost to the production widget.

Permanent-account authentication remains narrower than the code's provider
support:

- email magic link is enabled and protected by Turnstile;
- Supabase's default SMTP is still in use, so delivery is limited to authorized
  members of the Supabase project team;
- manually entered email OTP is disabled by Worker runtime configuration; and
- GitHub login is disabled until a GitHub OAuth application and its secret are
  configured in Supabase.

Trying to attach an email or OAuth identity that already belongs to another
account returns Supabase's conflict without replacing the guest workspace.
Aletheia does not yet merge two existing workspaces automatically.

The public `/demo` path does not require email: it completes Turnstile,
anonymous sign-in, and isolated Northstar bootstrap. Before inviting users to
create permanent email accounts outside the project team, configure custom SMTP
and test delivery, scanner/link-rewrite behavior, expiry, abuse controls, and recovery.
See Supabase's [Auth rate-limit guide](https://supabase.com/docs/guides/auth/rate-limits)
and [SMTP guide](https://supabase.com/docs/guides/auth/auth-smtp). When GitHub is
enabled, register Supabase's provider callback in the OAuth application and
turn `GITHUB_AUTH_ENABLED` on only after the complete staging callback succeeds.
Deployment preview URLs remain disabled and must not be added as Auth origins.

## 6. Render API state and redeploy procedure

`render.yaml` defines the provisioned `aletheia-api` Free Docker web service in
Render's Virginia region. It connects over SSL to Supabase's `us-east-1`
Supavisor session pooler. It intentionally uses inline operations because this
Free preview topology does not include a continuously running background
worker.

For a redeploy or replacement service:

1. Create the service from the repository blueprint or reproduce the same
   Docker settings manually.
2. Set every Render variable in section 4.2. Use the Supabase PostgreSQL URLs
   for both database variables, with driver conversion handled by application
   settings.
3. Verify Alembic against a disposable/target database from a trusted admin
   environment before the release when possible:

   ```bash
   cd apps/api
   DATABASE_URL='<async-runtime-url>' \
   MIGRATION_DATABASE_URL='<sync-migration-url>' \
   ENVIRONMENT=production \
   SUPABASE_ISSUER='https://<ref>.supabase.co/auth/v1' \
   SUPABASE_JWKS_URL='https://<ref>.supabase.co/auth/v1/.well-known/jwks.json' \
   SUPABASE_AUDIENCE=authenticated \
   API_ORIGIN_TOKEN='<shared-secret>' \
   WEB_ORIGIN='https://aletheia.aletheia-web.workers.dev' \
   uv run alembic upgrade head
   ```

   Render's pre-deploy command is not available to a Free web service. In the
   checked-in Free topology, `aletheia serve` therefore acquires a PostgreSQL
   advisory lock, runs the same immutable Alembic upgrade, releases the lock,
   and only then replaces itself with Uvicorn. It never calls
   `Base.metadata.create_all()`. Move this command to Render's pre-deploy phase
   after a paid upgrade, but keep the lock during rolling deploys.
   The Free Blueprint also rejects `maxShutdownDelaySeconds`; the manifest
   intentionally omits it and retains Render's 30-second default shutdown
   delay. Reconsider this only after changing the service plan.
4. Deploy the API image and wait for the locked migration plus `/readyz` to
   complete. The current hosted target has completed this path through Alembic
   head.
5. Confirm `/docs` and `/openapi.json` are disabled in production.
6. Confirm an API call without the origin token is rejected.
7. Confirm an API call with the origin token but without a valid user JWT is
   rejected.
8. Confirm `POST /api/v1/projects/{project_id}/documents` returns
   `uploads_disabled_in_hosted_workspace`; the local integration test also
   proves this pre-routing boundary does not consume the multipart body.
9. Run `aletheia db cleanup-guests --json` first as a dry run. The API startup
   runs the 30-day cleanup under the migration/boot sequence, then the hosted
   lifespan repeats it every 24 hours. Startup and periodic failures alert and
   fail open so readiness is not held hostage. Use `--execute` only for the
   reviewed manual deletion pass.

Guest access expires after seven days even if physical deletion has not run.
On hosted Postgres, cleanup anchors application guest age to
`auth.users.created_at`, then removes anonymous identities and their
workspace/project graph after 30 days. It also removes anonymous Supabase Auth
identities past the cutoff that never created a `user_accounts` row. Permanent
identities are excluded. Waitlist consent is retained with its user link
cleared, so deleting a guest workspace does not withdraw or duplicate an email
consent record.

The staging verification exercised readiness, external Supabase JWTs,
origin-token rejection, two-user membership isolation, inline operations, and
the complete deterministic Northstar workflow through this service. Keep those
checks in every promotion record; a healthy `/readyz` alone is insufficient.

The API filesystem is ephemeral and must not hold SQLite or uploaded state.
Long-lived state belongs in Postgres; future artifact files belong in object
storage.

## 7. Configure and deploy Cloudflare

The browser-safe Supabase URL/publishable key, Turnstile site key, provider
feature flags, `AUTH_MODE`, and environment-specific `SITE_URL` values are
committed in `wrangler.jsonc`. `API_ORIGIN_URL` and `API_ORIGIN_TOKEN` remain
server-only secrets configured separately on the named staging and canonical
Workers. Deployment preview URLs are disabled so they cannot become unreviewed
Auth origins.

The named staging and canonical Workers now serve the same commit `147448a`
bundle. Use the procedures below for a subsequent deploy or secret rotation.
Never place the API origin token in
`vars`, a `NEXT_PUBLIC_*` value, a shell history argument, or the repository.
Wrangler resolves the named environment as a separate Worker at the staging
hostname.

For subsequent releases, complete the guest-specific staging verification in
section 8, then reproduce the production bundle and dry run before canonical
promotion:

```bash
pnpm exec opennextjs-cloudflare build
pnpm run cf-typegen
pnpm exec wrangler deploy --dry-run --env=""
pnpm run deploy:cloudflare
```

The staging deployment procedure is:

```bash
pnpm exec wrangler secret put API_ORIGIN_URL --env staging
pnpm exec wrangler secret put API_ORIGIN_TOKEN --env staging
pnpm exec wrangler deploy --dry-run --env staging
pnpm run deploy:staging
```

The project intentionally retains the deprecated Next.js 16 `middleware.ts`
convention for Supabase cookie refresh because it compiles for the Edge runtime.
Next.js 16 `proxy.ts` is fixed to the Node.js runtime, which OpenNext for
Cloudflare does not yet support for middleware. The production and staging
bundles are validated in CI; migrate to `proxy.ts` only after the adapter adds
Node middleware support.

Use one production deployment authority—Cloudflare Workers Builds or CI—not two
independent systems racing to deploy the same commit.

## 8. Hosted verification record and remaining gates

The named staging Worker has passed the connected permanent-user preview path:

- public landing and protected-route redirect behavior;
- Cloudflare same-origin proxying to Render with server-only credential
  injection and direct-origin rejection;
- external Supabase JWT verification, repeatable personal-workspace bootstrap,
  and two-user cross-tenant denial;
- Origin/CSRF and client-supplied credential rejection;
- complete review → approve → build → run → blocked trace → report → streamed
  Markdown/JSON download;
- hosted upload rejection without storing a body; and
- hosted database migration, empty Data API schema, negative REST access,
  zero current `anon`/`authenticated` grants, and zero future-table default
  grants.

The current public-guest bundle is deployed from commit `147448a` with this
release record:

- the release web suite passed 71 Vitest tests across 18 files;
- staging Worker version `3788c6b0-291c-43a9-bef3-b48aaa4a0498`;
- canonical production Worker version
  `935c3c39-f63e-4041-804b-ef40431d50fc`;
- `/` and `/demo` return `200`, while unauthenticated `/api/v1/me` returns
  `401`;
- HTTP redirects to HTTPS with `308`;
- the stale API-boundary notice is absent, and the current composite refund
  scenario plus `ALETHEIA` brand are served; and
- the real Turnstile script and challenge frame render on both Workers, the UI
  reaches `waiting`, and the former `ready()` load failure is absent.

The automated browser was challenged. It did not redeem a Turnstile token, so
this record does not prove anonymous Supabase sign-in, workspace bootstrap, or
the complete guest workflow. Before describing that path as end-to-end hosted
verified—and before the next production promotion—additionally verify:

- `/demo` is public, completes Turnstile, creates a signed anonymous Supabase
  session, and bootstraps an isolated personal Northstar workspace;
- the Turnstile widget allowlist contains only canonical and staging hosts and
  an unlisted host cannot complete the flow; local checks use local auth or the
  Cloudflare test key, and client `action` labels are not a server-enforced gate;
- FastAPI accepts only correctly signed anonymous tokens with
  `role=authenticated` and continues to reject invalid issuer, audience,
  signature, expiry, subject, role, and origin credential;
- two guests and one permanent user cannot read, mutate, poll, reset, or export
  one another's resources;
- guest reset and hosted uploads/arbitrary project creation are denied;
- the release's per-location 120 general/90 poll/30 heavy policies, fail-closed
  missing bindings, 64 KiB mutation rejection at both hops, and 85-second
  response-header deadline work as designed; verify separately that a streamed
  response body is not described as covered by that header deadline;
- the 30-successful-write and six-live-operation boundaries reject the next
  attempt without creating a partial resource;
- seven-day access expiry is independent from the 30-day deletion threshold;
- cleanup dry-run changes nothing; app-backed eligibility uses
  `auth.users.created_at`; execution removes only eligible guest workspace data
  and expired auth-only anonymous identities; waitlist consent survives with a
  cleared user link; and simulated startup/periodic failure alerts while
  readiness continues;
- normalized waitlist email uniqueness is idempotent and does not disclose
  whether a concurrent duplicate already exists;
- the complete review → approve → build → run → trace → report → download path
  still works for a fresh guest within its limits; and
- a two-session PostgreSQL check confirms snapshot-consuming work and child-row
  mutations share the `Project → child` lock order, so the mutation waits until
  the operation releases its snapshot fence.

The current Worker bundle has already been promoted to production with the
limited public-edge record above. Complete the guest path and security boundary
on `https://aletheia.aletheia-web.workers.dev` before claiming full hosted
functionality. For every subsequent promotion, record the Worker version,
source commit, Render deploy, Alembic head, UTC timestamp, and rollback version.

These limitations remain after a successful promotion and must not be mistaken
for failed core deployment:

1. Email magic link uses Supabase default SMTP and is available only to
   authorized project-team email addresses. Configure and verify custom SMTP
   before opening sign-up more broadly.
2. Manual email OTP is disabled in the current Worker configuration.
3. GitHub OAuth is disabled until its OAuth application, callback, and secret
   pass staging.
4. Render Free can sleep after 15 idle minutes. Measure at least one real wake,
   verify the UI shows “Waking your workspace…”, and retain the explicit Retry
   recovery when the bounded window expires.
5. Complete log-redaction, browser Back/cache logout, accessibility,
   narrow-viewport, load, fault-injection, backup/restore, and incident drills
   before treating the preview as a production service.
6. Guest workspaces are deliberately disposable: no uploads, arbitrary
   projects, or reset; 30 successful writes; six live operations; seven-day
   access; and 30-day cleanup eligibility.
7. Native Supabase CAPTCHA confirms Turnstile success but does not enforce its
   `action` or `hostname` response fields. Treat Aletheia actions as labels and
   retain only canonical and staging hosts in the widget allowlist. Use local
   auth or the Cloudflare test key for local development.

## 9. Free-tier constraints

Free services are suitable for evaluation, not an availability claim.

- [Render Free web services](https://render.com/docs/free) spin down after 15
  minutes without inbound traffic and can take about one minute to wake. They
  have an ephemeral filesystem, 750 shared Free instance hours per month, no
  scaling, and can restart at any time. Aletheia limits retrying to idempotent
  bootstrap/build/run submissions and shows an explicit wake state.
- Render Free rejected the Blueprint `maxShutdownDelaySeconds` field. The
  checked-in Blueprint omits it and uses Render's 30-second platform default.
- [Cloudflare Workers Free limits](https://developers.cloudflare.com/workers/platform/limits/)
  currently include 100,000 requests per day, 10 ms CPU per dynamic request,
  128 MB memory, 50 subrequests, and a 3 MiB compressed Worker limit. SSR and
  authentication can exceed a small CPU budget; measure production traces and
  move to Workers Paid before promising reliability.
- [Supabase Free](https://supabase.com/pricing) currently advertises a 500 MB
  database and can pause low-activity projects. The
  [production checklist](https://supabase.com/docs/guides/deployment/going-into-prod)
  notes additional backup and availability limits. Configure backups, SMTP,
  capacity, and a paid plan according to the required recovery and uptime
  objectives.
- Free-tier cold starts can compound: Supabase may be paused while Render is
  asleep. The 85-second recovery/header window is a usability mitigation, not
  an uptime guarantee or a streamed-body timeout.

## 10. Rollback and incident notes

- Keep the previous Cloudflare Worker version available and roll traffic back
  if auth, proxying, or rendering regresses.
- Render Free supports only limited recent rollbacks; retain a known-good image
  or commit and verify database migration compatibility before rollback.
- Alembic migrations are the database source of truth. Never run destructive
  downgrade commands against a hosted database without a reviewed data plan and
  backup.
- Rotating `API_ORIGIN_TOKEN` requires coordinated updates at Cloudflare and
  Render. During rotation, use a controlled maintenance window unless the API
  supports dual tokens.
- If a JWT or cookie leaks, revoke sessions in Supabase and rotate affected
  provider credentials. If the origin token leaks, rotate it immediately.

## 11. GitHub Pages

GitHub Pages renders repository documentation with Jekyll. It cannot run this
dynamic Next.js/FastAPI architecture. Keep Pages as documentation or disable it;
the Cloudflare Worker is the application target.
