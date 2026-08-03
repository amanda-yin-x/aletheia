# Build plan and gates

## Completed P0 gates

- Scaffold, SQL models/migration, UUIDs/hashes, typed contracts, and seed corpus.
- Safe allowlisted policy interpreter and money-boundary evaluation cases.
- Source-linked rule review, seeded proved findings, and a revisioned approval
  flow. Semantic-edit re-review hardening remains Phase 0 work.
- Compiler, seven guarded rules, 16 cases, three-arm runner, trace, metrics, and
  immutable Markdown/JSON report.
- FastAPI, Typer CLI, inline persisted jobs, worker command, and SQLite WAL.
- Responsive landing/workbench pages with loading, error, empty, and blocked
  states; production web build and automated checks.
- Docker, Render, and Vercel configuration; CI/evidence docs; and a benchmark
  provenance sync adapter. The data root is now configuration-driven; a clean
  container startup smoke test and the hosted async-job contract remain Phase 0
  work in the production roadmap.

## Next milestones

1. Fix the build/run truth invariants and hosted async-job contract, then add a
   clean-image startup smoke test as identified in
   `current-state-and-production-roadmap.md`.
2. Run structured extraction against a user-selected provider, keeping exact
   quote verification and manual approval unchanged.
3. Finish a production-quality live tool-calling loop with recorded provider
   usage and bounded timeouts/retries.
4. Normalize the pinned tau3 task subset into the local declarative contract and
   run it with an explicitly selected adapter; never publish deterministic replay output as
   benchmark results.
5. Add auth, tenant isolation, encrypted storage, and retention controls before
   accepting confidential customer documents.
