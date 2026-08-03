# Deployment and hosting runbook

Last verified: 2026-08-03

## Current public endpoints

- Website: <https://aletheia.aletheia-web.workers.dev>
- GitHub repository: <https://github.com/amanda-yin-x/aletheia>
- GitHub Pages documentation: <https://amanda-yin-x.github.io/aletheia/>

The Cloudflare endpoint is the real Next.js application. The GitHub Pages
endpoint is intentionally described as documentation because GitHub's legacy
branch deployment runs Jekyll against the repository root and renders
`README.md`; it does not run Next.js or FastAPI.

## What is deployed

The `apps/web` Next.js 16 application is adapted for the Workers runtime by
`@opennextjs/cloudflare`. Cloudflare serves the generated static assets and the
OpenNext Worker handles App Router routes, including the dynamic project,
build, run, trace, and report route shells.

The current public release does **not** expose the FastAPI service or its
database. The landing page is public, while `/demo` presents an explicit hosted
API boundary and links to the verified local workflow. This prevents a public
button from silently sending requests to `localhost` or implying that a shared
mutable workspace is production-ready.

## Cloudflare files

- `apps/web/wrangler.jsonc` names the Worker, pins the compatibility date,
  enables `nodejs_compat`, serves `.open-next/assets`, uploads source maps, and
  enables sampled observability.
- `apps/web/open-next.config.ts` selects the default Cloudflare adapter.
- `apps/web/public/_headers` gives fingerprinted Next.js assets an immutable
  cache policy.
- `apps/web/cloudflare-env.d.ts` is generated from Wrangler configuration.
- `.open-next/` is generated output and remains ignored by Git.

## Verified commands

From the repository root:

```bash
corepack enable
corepack pnpm install
cd apps/web
pnpm exec opennextjs-cloudflare build
pnpm run cf-typegen
pnpm exec wrangler deploy --dry-run
pnpm exec wrangler check startup
pnpm exec opennextjs-cloudflare preview
pnpm exec opennextjs-cloudflare deploy
```

The 2026-08-03 verification produced a 1.1 MiB compressed Worker, a 25 ms
reported startup time during deployment, successful 200 responses for `/` and
a dynamic route under the Workers runtime, and Cloudflare version
`62aacf51-1620-4d03-8579-6f426d5c64c7`.

Use `pnpm run deploy:cloudflare` when a fresh build and immediate deployment are
both intended. Use `pnpm run upload:cloudflare` when creating a version without
moving production traffic.

## Build-time configuration

Next.js inlines public variables into the browser bundle. Configure these in
the build environment before building:

```text
NEXT_PUBLIC_SITE_URL=https://aletheia.aletheia-web.workers.dev
NEXT_PUBLIC_API_URL=https://api.example.com
```

`NEXT_PUBLIC_API_URL` must be an HTTPS origin without a trailing slash. The web
client treats a missing production value as “API not configured”; local
development continues to use `http://localhost:8000`.

If Cloudflare Workers Builds is connected to GitHub, run the build from the
monorepo context so the root lockfile, workspace packages, and `tokens.css` are
available. Pin Node 22 and pnpm 11.17.0. Use one automatic deployment system at
a time—Workers Builds or GitHub Actions—not both.

## API release gates

The existing FastAPI/SQLAlchemy service needs a persistent hosted database and
a browser-reachable HTTPS origin. Before connecting it to the public site:

1. Fix and smoke-test the hosted PostgreSQL Alembic driver path.
2. Choose an access model. The current generated Northstar project is one
   shared mutable workspace with no authentication or tenancy.
3. Protect reset with `DEMO_RESET_SECRET`; add authentication, rate limits, and
   mutation quotas before anonymous exposure.
4. Either keep hosted jobs inline for a controlled evaluation deployment or
   teach the web client to poll queued build/run jobs before enabling the
   background worker.
5. Stop creating schema and seed data during every process startup; use Alembic
   and an explicit idempotent seed operation.
6. Set API `WEB_ORIGIN` to the exact final website origin and verify CORS from
   the public hostname.
7. Run the full browser workflow against the hosted origins, including build,
   comparison, guarded trace, report export, reset protection, and rollback.

For a controlled review, place the workspace behind Cloudflare Access. For an
anonymous product experience, first add per-session isolation and expiry so
visitors cannot change one another's state.

## GitHub Pages diagnosis

The GitHub Pages run at
<https://github.com/amanda-yin-x/aletheia/actions/runs/30847669580> checked out
`main`, pulled GitHub's `jekyll-build-pages` image, and ran “Build with Jekyll.”
That is why the Pages URL displays a polished copy of the README rather than the
application. Changing the Pages theme cannot fix this architecture: Pages can
host a static export, but this repository also has dynamic App Router paths and
a separate Python API.

Keep Pages as project documentation or disable it in **Repository Settings →
Pages**. The Cloudflare Worker is the canonical application URL.
