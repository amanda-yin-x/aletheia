# Deployment and hosting runbook

**Snapshot:** 2026-08-03  
**Target:** Cloudflare Workers + Render FastAPI + Supabase Auth/Postgres  
**Current status:** implementation and broad local verification complete;
external provisioning, deployment, and hosted end-to-end verification pending

This runbook deliberately distinguishes code that exists from infrastructure
that has actually been provisioned. Nothing in `render.yaml`, `wrangler.jsonc`,
or the environment examples proves that a Supabase project, Render service,
database, OAuth application, SMTP provider, Turnstile widget, or production
secret currently exists.

## 1. Target request path

```text
Browser
  │
  ├─ GET / ──────────────────────────────► public landing page
  │
  └─ /demo or another protected route
       │
       ├─ Supabase Auth
       │    email magic link / email OTP / GitHub OAuth
       │    Turnstile token on email requests
       │    code-only PKCE callback exchange
       │
       ▼
Cloudflare Worker: Next.js 16 through OpenNext
       │
       ├─ refreshes Supabase cookies before protected rendering
       ├─ redirects unauthenticated users to /login
       └─ proxies browser calls through same-origin /api/v1/*
              │
              ├─ verifies the user session
              ├─ rejects untrusted mutation Origin/CSRF values
              ├─ adds Authorization: Bearer <Supabase access token>
              └─ adds X-Aletheia-Origin-Token from a Worker secret
                       │
                       ▼
Render HTTPS origin: FastAPI
       │
       ├─ checks origin credential and bearer presence before routing
       ├─ rejects hosted document uploads before multipart parsing
       ├─ verifies routed JWTs against Supabase JWKS
       ├─ requires role=authenticated and rejects anonymous JWTs
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
| Public landing and protected route shells | Implemented | Locally verified |
| Supabase browser/server clients | Implemented | Locally verified |
| Cookie refresh before protected rendering | Implemented | Locally verified with a focused middleware test |
| Email link/OTP and GitHub login UI | Implemented | Code-only PKCE exchange and raw `token_hash` rejection are locally verified; provider flows remain pending |
| Turnstile token forwarding and single-use reset | Implemented | Locally verified; widget/secret pairing pending hosted verification |
| Same-origin streaming API proxy | Implemented | Header filtering, credential injection, streaming, and mutation rejection are locally verified; public Render origin pending |
| Origin and CSRF mutation protection | Implemented | Locally verified |
| FastAPI JWT and origin-token checks | Implemented | Full local backend suite passed; external JWKS behavior remains unverified |
| Pre-routing hosted upload denial | Implemented | A local streaming-body test confirms origin/auth/upload rejection occurs without reading the multipart body |
| Workspace tenancy and scoped resources | Implemented | Full local backend suite passed; hosted two-user verification remains pending |
| Alembic PostgreSQL migration | Implemented | A PostgreSQL 14 empty-database lifecycle and role-privilege test passed locally; the PostgreSQL 17 Actions job is configured, while the target Supabase database remains pending |
| Render service blueprint | Implemented | Pending hosted verification |
| Cloudflare runtime configuration | Implemented | Production and named staging Worker bindings, `preview_urls: false`, OpenNext builds, and both Wrangler dry-runs are locally verified; deployment remains pending |
| Full Cloudflare → Render → Supabase flow | Implemented in code | Pending hosted verification |

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
| `API_ORIGIN_URL` | Treat as configuration | Yes | HTTPS Render origin; read only by server route handlers. |
| `API_ORIGIN_TOKEN` | **Yes** | Yes | Shared secret sent to FastAPI as `X-Aletheia-Origin-Token`. |
| `SUPABASE_URL` | No | Yes | Supabase project URL. |
| `SUPABASE_PUBLISHABLE_KEY` | No | Yes | Browser-safe publishable key used by Supabase Auth. |
| `TURNSTILE_SITE_KEY` | No | Yes | Browser widget key. Production auth fails closed when it is absent. The matching secret is configured in Supabase, not in this Worker. |

There are intentionally no `NEXT_PUBLIC_*` variables. Browser-safe Supabase and
Turnstile values are passed to the login component from server-rendered runtime
configuration; the API origin and origin token are never serialized to the
browser.

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
| `DEMO_RESET_SECRET` | **Yes** | No | Local-only compatibility setting. The legacy demo reset route is disabled in production; personal reset requires workspace admin membership. |
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

## 5. Provision Supabase

This section is pending hosted verification.

1. Create or select a Supabase project in the intended region.
2. Record the project URL, publishable key, Auth issuer, and JWKS URL.
3. Set the Auth Site URL to the exact Cloudflare hostname.
4. Add the exact production callback URL:
   `https://aletheia.aletheia-web.workers.dev/auth/callback`. For a separate
   staging Supabase project, add
   `https://aletheia-staging.aletheia-web.workers.dev/auth/callback` there.
   Deployment preview URLs are deliberately disabled and must not become Auth
   redirect origins.
5. Enable email authentication. The callback deliberately accepts only the
   browser-bound PKCE authorization `code` and rejects portable raw
   `token_hash` links. Keep the email link on Supabase's browser-initiated PKCE
   flow; the manually entered OTP is verified directly by the login form. Set
   an appropriately short OTP expiry.
6. Configure GitHub OAuth and add the callback URI shown by Supabase to the
   GitHub OAuth application.
7. Create a managed Turnstile widget named `Aletheia sign-in`. Restrict its
   hostname allowlist to `aletheia.aletheia-web.workers.dev`,
   `aletheia-staging.aletheia-web.workers.dev`, `localhost`, and `127.0.0.1`;
   use no pre-clearance. Configure its secret in Supabase Auth CAPTCHA settings
   and put only the site key in the web runtime. Keep this integration
   unverified until a real token succeeds and replaying that token is rejected.
8. Configure custom SMTP before inviting real users. Supabase's built-in email
   service is deliberately rate-limited and is not a production delivery
   system; current official limits and SMTP guidance are documented in the
   [Supabase Auth rate-limit guide](https://supabase.com/docs/guides/auth/rate-limits)
   and [SMTP guide](https://supabase.com/docs/guides/auth/auth-smtp).
9. Obtain separate runtime and migration database connection strings. Test both
   from a non-production environment before storing them in Render.
10. Run Supabase Security Advisor. Migration `0002` conditionally revokes all
    current table privileges and migration-user default table privileges in
    `public` from the `anon` and `authenticated` roles. A local PostgreSQL 14
    integration test creates those roles and verifies every current table plus
    a post-migration probe table. This does not prove the target Supabase role,
    schema, ownership, or Data API configuration, and it is not tenant-level
    RLS. Inspect the actual grants and test Data API denial before exposure;
    otherwise keep the tables outside the Data API or add verified RLS/private
    schema controls. This is an explicit release gate from the
    [Supabase production checklist](https://supabase.com/docs/guides/deployment/going-into-prod).

## 6. Migrate and deploy the Render API

`render.yaml` currently defines one Free Docker web service. It intentionally
uses inline operations because Render Free does not provide a continuously
running background worker in this blueprint.

1. Create the Render service from the repository blueprint or configure the
   equivalent Docker web service manually.
2. Set every Render variable in section 4.2. Use the Supabase PostgreSQL URLs for
   both database variables, with the appropriate driver conversion handled by
   application settings.
3. Verify Alembic against a disposable/target database from a trusted admin
   environment before the first release when possible:

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
4. Deploy the API image and wait for the locked migration plus `/readyz` to
   complete.
5. Confirm `/docs` and `/openapi.json` are disabled in production.
6. Confirm an API call without the origin token is rejected.
7. Confirm an API call with the origin token but without a valid user JWT is
   rejected.
8. Confirm `POST /api/v1/projects/{project_id}/documents` returns
   `uploads_disabled_in_hosted_workspace`; the local integration test also
   proves this pre-routing boundary does not consume the multipart body.

The API filesystem is ephemeral and must not hold SQLite or uploaded state.
Long-lived state belongs in Postgres; future artifact files belong in object
storage.

## 7. Configure and deploy Cloudflare

From `apps/web`:

```bash
pnpm exec wrangler secret put API_ORIGIN_URL
pnpm exec wrangler secret put API_ORIGIN_TOKEN
```

Set the browser-safe `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and
`TURNSTILE_SITE_KEY` as Worker runtime variables through the Cloudflare
dashboard or an approved deployment workflow. Keep `API_ORIGIN_URL` and
`API_ORIGIN_TOKEN` as server-only Worker secrets. `AUTH_MODE` and `SITE_URL` are
committed in `wrangler.jsonc` for both the canonical environment and the named
`staging` environment. Wrangler resolves the latter as a separate staging
Worker with the staging hostname. Secrets and environment-specific bindings
must be configured separately for it. `preview_urls: false` prevents deployment
preview URLs from creating additional unreviewed application/Auth origins; this
is separate from the explicitly configured workers.dev production and staging
hostnames.

Then verify and deploy:

```bash
pnpm exec opennextjs-cloudflare build
pnpm run cf-typegen
pnpm exec wrangler deploy --dry-run --env=""
pnpm run deploy:cloudflare
```

Before production, run the same bundle validation against staging and deploy
the named environment deliberately:

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

## 8. Required hosted smoke test

Run these checks against the actual public origins before changing the status
from “pending hosted verification”:

1. Public `/` loads without authentication and makes no protected API call.
2. `/demo` redirects to `/login` with a safe relative return path.
3. Email request requires Turnstile, sends a real message through custom SMTP,
   and works by both a browser-initiated PKCE magic link and OTP. A callback
   containing only `token_hash` must fail without creating a session.
4. A consumed Turnstile token cannot be reused.
5. GitHub OAuth returns to `/auth/callback` and opens `/demo`.
6. Session refresh writes replacement cookies and survives a full page reload.
7. Bootstrap creates one personal workspace/project and repeated bootstrap is
   idempotent.
8. Two real users cannot read, write, reset, poll, export, or enumerate each
   other's resources.
9. A cross-origin mutation, missing CSRF header, client-supplied bearer token,
   and client-supplied origin token are rejected.
10. Resolve findings, approve the threshold, submit a build, poll its operation,
    submit a run, inspect the blocked trace, create a report, and stream both
    exports through Cloudflare.
11. Let Render sleep for at least 15 minutes, then verify the UI shows
    “Waking your workspace…” and recovers within the bounded retry window.
12. Verify request IDs across Cloudflare and Render logs without logging JWTs,
    cookies, origin secrets, database URLs, or policy source contents.
13. Verify logout clears Supabase cookies, React Query state, and browser Cache
    Storage, then blocks the browser Back path from reopening protected data.
14. A hosted document-upload attempt is rejected with
    `uploads_disabled_in_hosted_workspace`; no uploaded body is stored.
15. Inspect `has_table_privilege` for every real hosted `anon` and
    `authenticated` table privilege, then make negative Data API read/mutation
    requests. Create a disposable post-migration table with the same owner used
    for migrations and confirm the default denial also applies.
16. Run an accessibility and narrow-viewport pass on login and authenticated
    routes.

## 9. Free-tier constraints

Free services are suitable for evaluation, not an availability claim.

- [Render Free web services](https://render.com/docs/free) spin down after 15
  minutes without inbound traffic and can take about one minute to wake. They
  have an ephemeral filesystem, 750 shared Free instance hours per month, no
  scaling, and can restart at any time. Aletheia limits retrying to idempotent
  bootstrap/build/run submissions and shows an explicit wake state.
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
  asleep. The 85-second client recovery window is a usability mitigation, not
  an uptime guarantee.

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
