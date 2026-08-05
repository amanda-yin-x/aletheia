# Aletheia — repository continuation and Gate 1 handoff v3

**Version:** 3.0  
**Reconciliation date:** 2026-08-04  
**Repository base inspected:** `91055f6043edfd7f0cb171eac0bd04c611f2d509` plus the current Gate 1 working tree  
**Predecessor:** `aletheia_refined_codex_execution_handoff_v2 (1).md`, retained unchanged as historical input  
**Predecessor SHA-256:** `325e6c980eeee5b11457e1ebe7475aef04d734962345fc84a83e81ba46c63948`

## 1. Purpose and precedence

This is the current continuation brief for the existing repository. It does not
replace source code, migrations, generated contracts, or test results. When a
claim conflicts, use this order:

1. inspected code, explicit migrations, generated schemas/OpenAPI, and tests;
2. `capabilities.json`, `current-state-and-production-roadmap.md`,
   `build-plan.md`, `architecture.md`, and `evidence-boundary.md` after their
   Gate 1 reconciliation;
3. this handoff;
4. the v2 handoff, independent reviews, and research map;
5. the root greenfield prompt/specification, which are historical and
   superseded as implementation instructions.

Do not erase historical prompt/specification headers. Do not rewrite the
repository as greenfield. Preserve working Gate 0 and hosted behavior while
advancing one bounded gate at a time.

## 2. Product decision

Build Aletheia as a **source-aware policy refactoring and compilation workbench
for tool-using AI agents**.

> Refactor reviewed prompts, skills, policies, SOPs, and tool schemas into a
> smaller always-loaded kernel plus scoped skills, knowledge, deterministic
> guards, tests, and explicit pending material—while retaining an inspectable
> source-to-generated-span chain.

The immediate proof is not a general AI policy engine. It is a deterministic,
two-domain workflow in which a human can inspect authority conflicts, approve
rule placement, compile portable artifacts, and trace generated material back
to exact reviewed inputs.

## 3. Normalized gate status

| Gate | Status at this reconciliation | Meaning |
|---|---|---|
| Gate 0 — deterministic Northstar foundation | Complete in the settled, tested local fixture scope | Existing ingest/review/build/run/trace/report behavior is the regression floor. |
| Gate 0H — hosted verification and hardening | In progress | Supabase, Render, Cloudflare staging/canonical Workers, and permanent-user staging E2E exist. Anonymous Turnstile redemption and full guest E2E remain unverified. |
| Gate 1 — source-aware refactoring/compiler | Complete in verified local two-domain fixture scope | Generic contracts/compiler, exact provenance, placement review, metrics, Acme, API/database/frontend/packaging, and browser E2E passed. Not deployed. |
| Gates 2–8 | Absent | Interfaces, schemas, adapters, research notes, or tau syncs are not operating product capabilities. |

Current confirmed local checkpoint: default API `139 passed, 1 skipped`;
focused regenerated-contract/Gate 1 suite `31 passed`; Ruff and mypy passed;
SQLite Alembic upgrade/drift passed through `0006`; fresh real PostgreSQL
migration integration `1 passed, 4 deselected` and removed its temporary
database; frontend ESLint/typecheck, `84/84` Vitest tests across 22 files, and
production Next.js build passed. OpenNext at compatibility date `2026-08-04`,
Wrangler `4.118.0` type generation, root/staging deploy dry-runs (53 assets;
8,019.91 KiB / 1,665.20 KiB gzip), and local startup check (34.0 ms) passed.
Focused two-domain E2E passed `1/1` in 15.2 seconds and the complete fresh-
isolated Playwright suite passed `6/6` in 1.3 minutes. `pip-audit` and the
production high-severity `pnpm audit` reported no known vulnerabilities. These
local results and packaging observations are not a deployment or
production-performance claim; the public Workers remain the separate
`147448a` bundle.

See [`gate-1-verification-report.md`](gate-1-verification-report.md) for the
verified roots, artifact tree, representative provenance/metrics, demo path,
and claim boundary.

Never infer a completed gate from the presence of a class, route, schema, UI
screen, configuration seam, or research note. Record `unverified` until the
end-to-end behavior has been run.

## 4. Existing architecture to preserve

The repository is a modular monolith:

- FastAPI, Pydantic, SQLAlchemy, Alembic, Typer, and a SQL-backed operation path;
- Next.js, React, TypeScript, TanStack Query, Vitest, and Playwright;
- SQLite for the no-key local path and PostgreSQL/Supabase for hosted state;
- Supabase Auth for identity, a same-origin Cloudflare API proxy, and a Render
  FastAPI origin protected by both user JWT and origin secret;
- immutable build/run inputs, content hashes, traces, and evidence exports;
- deterministic fixture evaluation, not a live model/tool integration.

Keep database access behind the service/API boundary. Do not expose application
tables through the Supabase Data API. Keep fixture mode functional without a
model key. A live-model failure must never silently become fixture success.

## 5. Gate 1 canonical data chain

```text
raw source bytes
  → immutable source version + authority metadata
  → exact source anchor (quote, lines, UTF-8 bytes, hashes, parser/normalizer)
  → rule revision (source-anchored or reviewer-authored guidance)
  → append-only placement decision
  → pinned compiler profile + compilation config
  → generated artifact + exact generated span
  → routing/preservation/metrics/source-map evidence
```

Every link must be inspectable and deterministic. Reviewer-authored guidance is
allowed only when it carries a reviewer identity, rationale, and offset-aware
`reviewed_at`; it must never be presented as a source quote. Test-generated span
markers are `compiler_scaffold`, not source-derived material.

### Placement destinations

The pinned `source-aware` profile recognizes:

- `prompt_kernel` — small always-loaded behavior or invariant;
- `skill` — scoped operational workflow;
- `knowledge` — reference information that should be retrieved/scoped;
- `pre_tool_policy` — deterministic proposal validation before mutation;
- `test` — executable regression/boundary case;
- `human_review` — unresolved or deliberately human-gated material;
- `unsupported` — material the compiler cannot honestly encode.

Allowed transform classes are `verbatim`, `reviewed_normalization`,
`reviewer_authored_guidance`, and `compiler_scaffold`. Compiler scaffold must be
visibly distinct from rule-derived spans.

### Primary build artifacts

The verified local compiler emits:

- `prompt-kernel.md`;
- `skills/<scope>/SKILL.md`;
- `knowledge/<scope>.md`;
- `policies/tool-policy.json`;
- `tests/regression.yaml`;
- `pending/unsupported-rules.json`;
- `routing-report.json`;
- `preservation-report.json`;
- `compilation-metrics.json`;
- `source-map.json`;
- pinned compiler profile, placements, source metadata, rules, findings, tool
  schemas, facts, manifest, and artifact hashes.

The exact manifest generated by a build is authoritative. Documentation must
not invent artifact counts.

## 6. Gate 1 measurement boundary

Report separate measurements for:

- baseline always-loaded instructions;
- compiled prompt kernel;
- scoped skills;
- scoped knowledge;
- machine-enforced artifacts;
- expected task context;
- total bundle size;
- routing/source linkage;
- severity-weighted structural preservation;
- high/critical guard-and-test placement;
- blocked, unsupported, unrouted, and unresolved clauses;
- protected literals such as negation, thresholds, durations, quoted values,
  tool names, boundaries, and exceptions.

Use `declared_rule_linkage`, `declared_source_linkage`, and
`declared_boundary_linkage` for fixture declarations. Do not call declarative
linkage observed runtime coverage.

Every preservation/metric report must say `behavioral_fidelity: not_measured`.
Byte/line provenance, structural routing, protected-literal preservation, and a
passing fixture suite do not establish semantic equivalence or improved model
behavior.

## 7. Two-domain proof corpus

### Northstar retail

Northstar remains the regression corpus for refund authority conflict,
source-linked review, deterministic guard behavior, the comparison run, traces,
and evidence reports. Its existing behavior is the compatibility floor.

### Acme appointments

The second pack must use the same schemas and generic compiler path. Its source
set includes a substantial `SKILL.md`, current scheduling policy, stale SOP,
baseline prompt, style and knowledge references, tool schemas, evaluation cases,
and synthetic state.

Its reviewed active policy includes verified identity, a trusted IANA timezone,
a weekday customer-local `[09:00, 17:00)` window, and exact confirmation before
cancellation or a fee-bearing change. Maximum reschedule count and cooldown are
pending/test-only. Undefined “daylight hours” is unsupported. Stale SOP content
must never silently enter the active build.

This pack tests domain neutrality; it does not represent a live scheduling
system or a complete appointment policy.

## 8. Gate 1 completion checkpoint (passed locally)

The verified working-tree state satisfied all of the following. Retain them as
the Gate 1 regression contract:

1. Northstar and Acme compile through the same generic compiler modules/profile
   with no domain branch in the compiler.
2. Repeated builds in separate processes produce the same relevant artifact
   bytes and digests from the same pinned inputs.
3. Every generated rule-derived span resolves to the exact build, artifact,
   rule revision, placement version, and verified source anchor.
4. Missing/shifted/forged source anchors, unknown profile values, and incomplete
   active dispositions fail closed.
5. Stale sources and ambiguous/unresolved clauses do not enter active artifacts.
6. High/critical machine-decidable rules have approved guard and test placement
   or the build fails with a precise reason.
7. Protected literals survive applicable transformations.
8. Placement updates are append-only, tenant-scoped, and protected by optimistic
   concurrency; cross-workspace reads return not found.
9. Old builds/runs remain immutable when current sources, rules, placements,
   profiles, or tests change.
10. API contracts, CLI path, source/rule review UI, build inspection UI,
    migrations, empty/legacy database upgrades, and generated contracts pass.
11. The full existing Gate 0 backend/frontend/E2E regression suite remains
    green.
12. README, canonical docs, and `capabilities.json` record exact results without
    upgrading hosted or behavioral-fidelity claims.

If any item is not executed, record it as pending—not implicitly passed.

## 9. Engineering rules

- Treat source text as untrusted data, never instructions to the compiler or
  model.
- Never execute customer-authored Python, JavaScript, shell, Rego, Cedar, or
  arbitrary expressions.
- Pin parser, normalizer, compiler profile, placement versions, and source
  versions into builds.
- Fail closed on malformed policy/rule/tool/test contracts.
- Validate every tool proposal before any state mutation; a rejected proposal
  must leave no execution event and no changed fixture state.
- Preserve tenant scoping and cross-resource ownership checks.
- Keep migrations explicit and reversible where practical; never create the
  schema opportunistically during API/worker startup.
- Preserve old build/run evidence rather than recomputing it from mutable rows.
- Do not weaken assertions or edit generated contracts by hand to make tests
  pass.

## 10. Scope after Gate 1

Stop and review evidence before Gate 2. The following remain future work and
must not be folded into the Gate 1 claim:

- bounded Z3 conflict, implication, redundancy, and boundary analysis;
- generic temporal monitors and stateful obligations;
- policy mutation generation and mutation score;
- Qwen/Ollama/vLLM extraction or a live model/tool loop;
- upstream tau task execution beyond data sync/import;
- production dispatcher SDK, observe/enforce rollout, signing, promotion, and
  last-known-good distribution;
- arbitrary uploads, shared enterprise tenancy, SSO/SCIM/RBAC, audit export,
  managed secrets, or compliance claims.

Those are Gates 2–8, not hidden subfeatures of Gate 1.

## 11. Documentation and release handoff

At each release checkpoint record:

- exact source commit and whether the working tree was clean;
- database dialects and migration path tested;
- exact commands and pass/fail counts;
- compiler profile/config identifiers and artifact digest(s);
- which domain packs ran;
- hosted deployment identifiers separately from local verification;
- known omissions and `not_measured` fields.

Do not promote a local result into a hosted claim. Do not promote a permanent
user staging result into an anonymous guest claim. Do not promote a structural
preservation metric into a behavioral-fidelity claim.

## 12. Changelog from handoff v2

- Reconciled the brief to an inspected existing repository and hosted
  Supabase/Render/Cloudflare architecture.
- Normalized the Gate 0, Gate 0H, Gate 1, and Gates 2–8 statuses.
- Narrowed the product center from a broad Policy CI/runtime roadmap to
  source-aware prompt/skill/policy refactoring and compilation.
- Added the exact provenance, placement, generated-span, primary artifact, and
  metric contracts implemented and verified for local Gate 1.
- Added the Acme appointments second-domain proof and its explicit unsupported
  and pending clauses.
- Moved solver, temporal, mutation, local-model, live-runner, tau-execution, and
  enterprise work beyond the Gate 1 checkpoint.
- Made structural-versus-behavioral evidence boundaries explicit.
