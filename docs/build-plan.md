# Build plan and gates

**Reconciled:** 2026-08-04  
**Last independently audited anchor:** `4f4e410a2b114bb16b55566bca79c555a489bd9b`  
**Original Gate 1 start:** `91055f6043edfd7f0cb171eac0bd04c611f2d509`  
**Reconciliation start:** `0d5b356e6143f784c726f55406ca1ba12d308af0`; verified implementation: `2292a5f7089d061c9dc8b977852ee04d182373bc`  
**Hosted release:** `2329a1e39c00bf6313965bc06454f9bd49119816`; Render `dep-d9pa9f6417fc73dfhcvg`; Alembic `0006`

## Status at a glance

| Track | Status | Exit boundary |
|---|---|---|
| Gate 0 — Local deterministic foundation | Complete in the settled tested Northstar fixture/local scope | Preserve ingest → review → build → run → trace → report behavior and its no-key path. |
| Gate 0H — Hosted verification and release hardening | In progress | Permanent-user Northstar staging passed historically; fresh guest bootstrap, basic two-domain navigation/inventory, and bounded isolation passed on staging and production. Complete guest E2E remains unverified. |
| Gate 1 — Source-aware policy refactoring and prompt/skill compilation | Complete locally; deployed preview | API/database/frontend/packaging/browser checks cover the shared Northstar/Acme path. The code and migration are live; hosted build/run/report remains unverified. |
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

The Supabase → Render → Cloudflare stack is provisioned. Fresh Turnstile
redemption, anonymous session creation, bootstrap, basic Northstar/Acme
navigation/inventory, and bounded ownership/reference isolation passed on both
named Workers. Complete the remaining guest path before calling the public
preview end-to-end verified:

1. verify session refresh, repeat-bootstrap idempotency, logout/revocation, and
   replay rejection;
2. broaden guest-to-guest and guest-to-permanent read, mutation, job, and export
   isolation checks;
3. exercise limits, expiry, cleanup, reset denial, waitlist persistence, and
   cold-start/outage recovery on hosted infrastructure;
4. run the complete Northstar and Acme
   review/build/run/trace/report/download paths; and
5. repeat invalid/expired JWT, direct-origin, Origin/CSRF, and credential-
   stripping checks against the current release.

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

Confirmed on the verified local implementation commit: default API `148 passed, 1
skipped`; focused regenerated-contract/Gate 1 suite `40 passed`; Ruff, mypy,
SQLite Alembic upgrade/drift through `0006`, and fresh PostgreSQL migration
integration `1 passed, 4 deselected`; frontend ESLint/typecheck, all 87 Vitest
tests across 23 files, and production Next.js build. The temporary PostgreSQL
database was removed. OpenNext at compatibility date `2026-08-04`, Wrangler
`4.118.0` type generation, root/staging deploy dry-runs (53 assets; 8,026.44 KiB
/ 1,666.83 KiB gzip), and local startup check (40.4 ms active) passed. Browser
E2E passed. The focused two-domain E2E passed 1/1 in 34.6 seconds; the complete
fresh-isolated Playwright suite passed 6/6 in 1.1 minutes. `pip-audit` and the
production high-severity `pnpm audit` reported no known vulnerabilities. The
dry-run bundle/startup values remain local packaging observations, not
production-performance evidence. Release commit `2329a1e` subsequently
packaged and deployed this implementation; deployment does not convert those
local measurements into hosted behavioral evidence.

See [the Gate 1 local verification report](gate-1-verification-report.md) for
the exact build roots, artifact tree, representative provenance/metrics, demo
path, and unsupported claims.

## Gate 1 reviewable-slice record

The implementation landed across `d10af27` and focused reconciliation
`2292a5f`, so Git history does not independently prove that every intermediate
slice was runnable. The table below is the
equivalent review/status breakdown required by the execution brief; only the
combined end state carries the recorded pass claim.

| Slice | Principal paths | Evidence-backed outcome |
|---|---|---|
| 1 — contracts and profiles | models/schemas, migration `0006`, compiler profile, generated OpenAPI/JSON Schema/client | Fail-closed profile, placement, generated-span, routing, preservation, and metric contracts passed contract/persistence tests. |
| 2 — generic compiler and Northstar parity | `services/compilation/`, compiler facade, Northstar seeds/tests | Northstar builds through the profile-driven core; fresh-process bytes/digests and legacy-build readability passed. |
| 3 — Acme corpus | `data/demo/acme-appointments/`, appointment seed, shared runner | The substantial appointment corpus, manual authority conflicts, pending temporal clauses, and unsupported daylight clause passed the shared compiler/runner path. |
| 4 — review and inspection UI | project switcher, routing/placement workbench, build inspection, presentation helpers | Source authority, placement versions, bundle tree, metrics, and exact span links passed unit/component and browser coverage. |
| 5 — evidence and documentation | verification report, successor documents, capability inventory, screenshots | Claims, artifact roots, unsupported boundaries, and local-versus-hosted status were recorded without starting Gate 2. |

Repository-wide [GitHub Actions run
30970432139](https://github.com/amanda-yin-x/aletheia/actions/runs/30970432139)
is green on release commit `2329a1e`, including the production API-container
smoke for the pinned profile and both domain packs. Hosted Supabase/Render is at
`0006_gate1_compilation_contracts`. A protected pre-migration `0005` archive
exists, but no restore drill is claimed.

The existing CLI retains deterministic `compile`, `test`, and `report`
commands. A stable customer-facing `aletheia check` exit/evidence contract and
narrow pre-side-effect dispatcher were deliberately not improvised inside this
checkpoint; they are the immediate post-Gate-1 integration seam if product
validation requires them, and must not be described as complete Gate 8.

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
