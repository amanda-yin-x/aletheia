# Architecture

Aletheia remains a modular monolith. FastAPI, the Typer CLI, and the persisted
SQL worker call one domain-service layer; the Next.js application is the product
surface and a same-origin backend-for-frontend when deployed to Cloudflare.

## Hosted request path

```text
public Cloudflare landing page
  → Supabase Auth (email OTP/magic link or GitHub)
  → signed, HTTP-only session cookies
  → same-origin /api/v1/* proxy
       ├─ verifies/refreshes the Supabase session
       ├─ rejects untrusted mutation origins and CSRF tokens
       ├─ injects the user JWT
       └─ injects X-Aletheia-Origin-Token from a Worker secret
  → Render FastAPI service
       ├─ verifies the origin secret with constant-time comparison
       ├─ verifies iss/aud/exp/sub against cached Supabase JWKS
       └─ resolves every resource through workspace membership
  → Supabase Postgres through Supavisor session mode
```

Only `/healthz` and `/readyz` are deliberately public on the API origin. A
browser does not receive the Render origin token, database credentials, an OAuth
secret, or a Supabase service-role key. Supabase Auth supplies identity only;
application data is read and written through FastAPI.

Local development is an explicit exception: `ENVIRONMENT=local` uses a fixed
development identity and SQLite by default. Production fails closed when JWT,
origin-token, HTTPS-origin, or migration settings are absent.

## Code boundaries

- `apps/api/app/services`: deterministic ingest, review, compiler, policy,
  runner, metrics, and reporting. These modules do not import FastAPI.
- `apps/api/app/api`: HTTP validation, tenant-scoped orchestration, operation
  resources, error envelopes, and request IDs.
- `apps/api/app/auth.py`: Supabase JWT and Worker-origin authentication.
- `apps/api/app/tenancy.py`: workspace membership and resource loaders that
  deliberately return `404` across tenant boundaries.
- `apps/api/app/operations.py` and `worker.py`: idempotent build/run operations,
  leases, bounded attempts, and inline/free-tier versus worker/paid execution.
- `apps/api/app/models.py`: portable SQLAlchemy models for SQLite and PostgreSQL.
- `apps/api/app/adapters`: optional model/benchmark dependencies; deterministic
  replay has no network or credential dependency.
- `apps/web/app/api/v1/[...path]`: streaming authenticated proxy. It does not
  buffer report downloads or forward browser cookies to Render.
- `apps/web/lib/supabase`: browser/server clients, identity, and session refresh.

## Identity and tenancy

`user_accounts` mirrors the minimum stable Supabase identity needed by the
application. `workspaces` and `workspace_members` define membership. Every
project belongs to one workspace, and project slugs are unique inside that
workspace. Jobs carry both `workspace_id` and `project_id` so polling,
idempotency, and concurrency checks cannot cross tenants.

The bootstrap operation is repeatable: a first login creates one personal
workspace and one Northstar project; later logins reopen the same IDs. Reset
replaces only that user's Northstar contents and preserves the project ID.
Arbitrary hosted project creation and source upload remain disabled.

## Schema and process startup

Alembic is the only production schema creator. Migration `0001` contains
explicit operations and the tenancy/operation migration upgrades existing local
data without seeding a new empty production database. API and worker startup no
longer call `Base.metadata.create_all()` or seed global data.

Render Free has no pre-deploy command, so the container entrypoint holds a
PostgreSQL advisory lock while applying Alembic and then replaces itself with
Uvicorn. The lock prevents two cold-starting instances from racing. On a paid
Render service, migrations should move to the platform pre-deploy phase.

## Evidence lifecycle

Documents preserve normalized text, a normalized-content hash, line numbers,
MIME type, and origin. The upload field currently named `original_sha256` still
does not preserve the raw input-byte hash; that provenance correction remains a
truth-critical follow-up. Rules point to exact quotes and source hashes. Review
produces new rule revisions. Builds persist document hashes, rule revisions,
test stable keys, artifact hashes, estimator label, and limitations. Runs
deep-copy each case state for each arm. Reports snapshot the completed run and
content hash.

The covered-tool registry is static. Policy JSON is data interpreted by an
allowlist; it cannot import modules or execute customer code. Enforced calls
mutate state only after an `allow` decision.

## Deliberately deferred

This hosted evaluation workspace is not the full enterprise data plane.
Encrypted object storage, confidential-document quarantine, durable external
approvals, signed bundle distribution, retention/deletion administration,
service accounts, billing, and production SLO evidence remain separate work.
