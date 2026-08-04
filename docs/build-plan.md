# Build plan and gates

## Completed Gate 0 implementation

- Scaffold, SQL models/migration, UUIDs/hashes, typed contracts, and seed corpus.
- Allowlisted policy interpreter and money-boundary evaluation cases.
- Source-linked rule review, atomic source-authority conflict decisions,
  optimistic concurrency, loser retirement, and forced re-review after semantic
  edits.
- Compiler, seven guarded rules, a build-pinned regression suite, labelled-arm
  runner, trace, metrics, and content-digested Markdown/JSON report.
- FastAPI, Typer CLI, typed/idempotent operations, inline Free-mode execution,
  lease-aware worker command, and SQLite WAL.
- Responsive landing/workbench pages with loading, error, empty, and blocked
  states; production web build and automated checks.
- Docker, Render, Cloudflare/OpenNext configuration, Supabase authentication and
  workspace tenancy, CI/evidence docs, and a provenance-checked Retail-17 import
  adapter. Local SQLite and PostgreSQL gates pass; the external hosted stack is
  not yet provisioned or verified end to end.

## Next approved milestones

1. Provision and verify the Supabase → Render → Cloudflare staging path,
   including effective Data API denial, both login methods, Turnstile, two-user
   isolation, cold starts, and the complete hosted workflow.
2. Run the locked production container startup/migration smoke once a container
   runtime is available; keep the free inline mode while retaining the worker
   for a paid deployment.
3. Begin Gate 1 only after checkpoint approval: a generic compiler seam plus the
   appointment-scheduling corpus and genuine side-by-side source-authority
   review.
4. Add `aletheia check` and one atomic Python guarded dispatcher before any live
   tool loop.
5. Then evaluate bounded Z3 analysis, restricted temporal monitors, mutation
   testing, local Qwen extraction, and a pinned upstream tau smoke run in that
   order. Never publish deterministic replay as an upstream benchmark result.
