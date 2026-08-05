# Build plan and gates

**Reconciled:** 2026-08-04  
**Inspected base:** `91055f6043edfd7f0cb171eac0bd04c611f2d509`; verified Gate 1 implementation: `d10af278f785be76a8232589b4d0264792147a17`

## Status at a glance

| Track | Status | Exit boundary |
|---|---|---|
| Gate 0 — deterministic Northstar foundation | Complete in the settled tested local fixture scope | Preserve ingest → review → build → run → trace → report behavior and its no-key path. |
| Gate 0H — hosted preview and release hardening | In progress | Permanent-user staging passed; anonymous Turnstile redemption and the complete guest lifecycle still require hosted verification. |
| Gate 1 — source-aware policy refactoring/compiler | Complete in verified local two-domain fixture scope | API/database/frontend/packaging/browser checks cover the shared Northstar/Acme path; not deployed. |
| Gates 2–8 | Absent | Start only after a recorded Gate 1 review. |

## Gate 0 foundation to preserve

- Explicit SQLAlchemy/Alembic persistence, typed contracts, exact hashes, and
  deterministic seed data.
- Source-linked rule review, authority conflict resolution, optimistic
  concurrency, loser retirement, and forced review after semantic edits.
- Build-pinned tools, facts, tests, policy, runs, traces, metrics, and
  content-digested Markdown/JSON evidence.
- Strict proposal validation before any fixture mutation, with separate
  proposal/decision/execution/state events.
- FastAPI, Typer, idempotent `202` operations, lease-aware worker support,
  inline free-tier execution, and local SQLite/PostgreSQL paths.
- Responsive Next.js workbench, automated backend/frontend/browser checks,
  generated contracts, container/Render/Cloudflare configuration, and a
  provenance-checked Retail-17 data adapter that does not execute the upstream
  benchmark.

## Gate 0H remaining checkpoint

The Supabase → Render → Cloudflare stack is provisioned and the permanent-user
staging lifecycle passed. Complete the anonymous guest path before calling the
public preview end-to-end verified:

1. redeem a real Turnstile token and obtain/refresh/revoke the guest session;
2. verify guest-to-guest and guest-to-permanent isolation;
3. exercise limits, expiry, cleanup, reset denial, waitlist persistence, and
   cold-start recovery on hosted infrastructure;
4. run the complete Northstar review/build/run/trace/report/download path;
5. record exact Worker/Render/Supabase identifiers and observable failures.

This hosted checkpoint is independent of Gate 1 local completion.

## Gate 1 implementation slices

The verified local implementation introduces:

1. a pinned, fail-closed source-aware compiler profile and compilation config;
2. document authority metadata and exact source anchors over raw/normalized
   hashes, quote, line and UTF-8 byte ranges, parser, and normalizer;
3. source-anchored rules versus reviewer-authored guidance with reviewer,
   rationale, and offset-aware `reviewed_at`;
4. append-only, tenant-scoped placement decisions with optimistic updates;
5. prompt-kernel, skill, knowledge, pre-tool-policy, test, human-review, and
   unsupported destinations;
6. exact generated spans and source-map, routing, preservation, unsupported,
   metric, pinned-input, and manifest artifacts;
7. separate context-size, structural-preservation, protected-literal, and
   declared-linkage measures with `behavioral_fidelity: not_measured`;
8. an Acme appointments corpus using the same compiler contracts as Northstar;
9. source/rule placement review and build-inspection surfaces.

Confirmed on the verified local implementation commit: default API `139 passed, 1
skipped`; focused regenerated-contract/Gate 1 suite `31 passed`; Ruff, mypy,
SQLite Alembic upgrade/drift through `0006`, and fresh PostgreSQL migration
integration `1 passed, 4 deselected`; frontend ESLint/typecheck, all 84 Vitest
tests across 22 files, and production Next.js build. The temporary PostgreSQL
database was removed. OpenNext at compatibility date `2026-08-04`, Wrangler
`4.118.0` type generation, root/staging deploy dry-runs (53 assets; 8,019.91 KiB
/ 1,665.20 KiB gzip), and local startup check (34.0 ms) passed. Browser E2E
passed. The focused two-domain E2E passed 1/1 in 15.2 seconds; the complete
fresh-isolated Playwright suite passed 6/6 in 1.3 minutes. `pip-audit` and the
production high-severity `pnpm audit` reported no known vulnerabilities. The
dry-run bundle/startup values are packaging observations, not deployment or
production-performance evidence. None of this changes the deployed public
`147448a` release.

See [the Gate 1 local verification report](gate-1-verification-report.md) for
the exact build roots, artifact tree, representative provenance/metrics, demo
path, and unsupported claims.

## Gate 1 regression contract

The local checkpoint passed. Keep these requirements green on every later
change:

- Run Northstar and Acme through the same compiler and confirm no domain branch
  exists in generic compilation modules.
- Confirm deterministic artifact bytes/digests across fresh processes.
- Resolve every rule-derived generated span to its exact reviewed source anchor
  and placement version.
- Prove fail-closed behavior for forged/stale anchors, unknown profile values,
  unresolved active clauses, protected-literal loss, and missing critical
  guard/test placement.
- Prove old build/run immutability and tenant isolation for placements and build
  inspection.
- Run empty/legacy SQLite migrations, PostgreSQL integration when credentials
  are available, generated contract drift, lint, type checks, backend tests,
  frontend tests/build, and browser flows.
- Record exact results in `capabilities.json`; do not convert structural
  conformance into a behavioral-fidelity claim.

## After Gate 1

Stop for evidence review. Gates 2–8 may explore bounded Z3 analysis, temporal
monitors, mutation testing, local-model extraction, a live model/tool loop,
upstream tau execution, a dispatcher SDK, signed promotion, and production
controls. None is part of Gate 1, and none is currently an operating product
capability.
