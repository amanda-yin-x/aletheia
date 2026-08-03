# Architecture

Aletheia is a modular monolith with one domain service layer and three delivery
surfaces: FastAPI, Typer, and a persisted SQL worker. The Next.js application is
a thin API client.

## Boundaries

- `app/services`: deterministic ingest, review, compiler, policy, runner,
  metrics, and reporting. It does not import FastAPI.
- `app/api`: validation, error envelopes, request IDs, and service orchestration.
- `app/models.py`: portable SQLAlchemy JSON-backed snapshots for SQLite and
  PostgreSQL.
- `app/adapters`: optional model/benchmark dependencies; deterministic replay has no
  network or credential dependency.
- `apps/web`: product interaction and visualization. Every metric comes from the
  API.

## Evidence lifecycle

Documents preserve normalized text, a normalized-content hash, line numbers,
MIME type, and origin. The upload field currently named `original_sha256` does
not yet preserve the raw input-byte hash; that provenance correction is Phase 0
roadmap work. Rules point to exact quotes and source hashes. Review produces new
rule revisions. Builds persist document hashes, rule revisions, test stable
keys, artifact hashes, estimator label, and limitations. They do not yet persist
exact versioned test snapshots; that is also a Phase 0 roadmap requirement. Runs
deep-copy each case state for each arm. Reports snapshot the completed run and
content hash.

The covered-tool registry is static. Policy JSON is data interpreted by an allowlist;
it cannot import modules or execute user code. Enforced calls mutate state only
after an `allow` decision.

## Later production work

Authentication, tenant isolation, encrypted object storage, retention/deletion,
audit administration, durable job recovery, capacity planning, and production
threat modelling are explicit later requirements.
