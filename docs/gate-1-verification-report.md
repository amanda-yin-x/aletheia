# Gate 1 local verification report

**Gate:** source-aware policy refactoring and prompt/skill compilation  
**Verdict:** complete in the verified local two-domain deterministic fixture scope  
**Verification date:** 2026-08-04  
**Inspected base:** `91055f6043edfd7f0cb171eac0bd04c611f2d509`  
**Deployment boundary:** not deployed; public Workers remain on `147448a`

## 1. What this verdict means

Gate 1 closes the local product checkpoint defined in the successor review and
handoff: one generic, profile-driven compiler now builds Northstar retail and
Acme appointments; exact source/placement/generated-span evidence is persisted
and inspectable; structural preservation/context metrics are explicit; the
review/build UI exposes the new contracts; and the complete local quality,
database, packaging, and browser checkpoint passes.

The verdict is deliberately narrow:

- it applies to deterministic synthetic fixtures, not customer documents;
- it applies to the final verified working tree, not to base commit `91055f6`
  alone;
- the working tree was not yet committed when verified, so a later commit must
  preserve this exact state and rerun release checks if it changes;
- no Gate 1 bundle was promoted to Cloudflare, Render, or Supabase;
- Gate 0H anonymous hosted verification remains a separate in-progress track;
- behavioral fidelity remains `not_measured`.

## 2. Ending-state map

The verified working tree adds or materially changes these Gate 1 areas:

| Area | Principal repository paths |
|---|---|
| Persistence and HTTP contracts | `apps/api/app/models.py`, `schemas.py`, `api/routes.py`, `tenancy.py`, migration `0006_gate1_compilation_contracts.py` |
| Generic compiler | `apps/api/app/services/compiler.py`, `apps/api/app/services/compilation/` |
| Domain packs | `data/demo/northstar-retail/`, `data/demo/acme-appointments/`, `appointment_seed.py` |
| Pinned profile | `data/compiler-profiles/source-aware-v1.json` |
| Generated contracts | `apps/api/openapi.json`, 34 JSON Schemas in `apps/api/schemas/`, generated TypeScript client schema |
| Reviewer UI | source/rule pages, project switcher, `routing/`, `placement-workbench.tsx` |
| Build evidence UI | `build-inspection.tsx`, `compilation-presentation.ts`, build workbench |
| Verification | Gate 1 compilation/persistence tests, web unit/component tests, six Playwright flows |

`git diff --check` passed. The three original untracked `(1).md` research files
remain byte-for-byte unchanged; their versioned successors record predecessor
names and SHA-256 values.

## 3. Implemented source-to-artifact chain

```text
raw source bytes + normalized text
  → document authority metadata
  → exact source anchor
      quote + line range + UTF-8 byte range
      raw/normalized/quote hashes + parser/normalizer identity
  → versioned rule provenance
      source_anchored
      OR reviewer_authored_guidance with reviewer/rationale/reviewed_at
  → append-only placement version
  → pinned compiler profile/configuration
  → generated artifact span
  → routing/preservation/metrics/source-map/manifest evidence
```

The compiler recognizes `prompt_kernel`, `skill`, `knowledge`,
`pre_tool_policy`, `test`, `human_review`, and `unsupported` destinations.
Transforms are explicitly classified. Reviewer-authored guidance carries no
source-anchor claim. Test-generated span markers and other generated framing are
`compiler_scaffold`, never source-derived text.

## 4. Final verification results

| Check | Final result |
|---|---|
| Default API suite | **139 passed, 1 skipped** |
| Focused regenerated-contract/Gate 1 suite | **31 passed** |
| Python lint/types | Ruff passed; mypy passed |
| SQLite schema | Alembic upgrade and drift check passed through `0006` |
| Fresh PostgreSQL migration marker | **1 passed, 4 deselected**; temporary database removed |
| Frontend unit/component | ESLint passed; strict typecheck passed; **84/84** Vitest tests across 22 files passed |
| Next.js | Production build passed; dynamic `/projects/[projectId]/routing` emitted |
| Focused browser path | Two-domain E2E **1/1** in 15.2 seconds |
| Complete browser path | Playwright **6/6** in 1.3 minutes using fresh isolated API/web ports and Next output |
| Cloudflare bundle | OpenNext passed at compatibility date `2026-08-04` |
| Wrangler | Version `4.118.0` type generation, root/staging deploy dry-runs, and startup check passed |
| Dry-run package observation | 53 assets; 8,019.91 KiB / 1,665.20 KiB gzip |
| Local startup observation | Active startup 34.0 ms |
| Dependency audits | `pip-audit` and production `pnpm audit --audit-level high`: no known vulnerabilities reported |
| Patch hygiene | `git diff --check` passed |

The final browser command was:

```bash
PLAYWRIGHT_API_PORT=18081 \
PLAYWRIGHT_WEB_PORT=13031 \
PLAYWRIGHT_ISOLATED_WEB=1 \
pnpm --filter @aletheia/web test:e2e
```

An earlier full run hit a transient Next development 404 only when stale reused
Next output was present. The clean isolated run passed without a product
workaround. This is why the final 6/6 result, not the earlier intermediate run,
is the accepted browser evidence.

The dry-run size and startup values are packaging observations. They do not
measure production latency, capacity, availability, or a deployed Gate 1
Worker. Dependency audits are not an independent security assessment.

## 5. Two-domain proof

The same compiler version/profile and generic modules build both packs. A
regression scans generic compiler code for Northstar/refund/Acme/appointment
semantic branches. Separate-process Northstar and Acme builds produce
byte-identical artifact bytes, manifest bytes, and digests for identical pinned
inputs.

### Northstar retail

- Preserves the current-versus-legacy refund authority workflow.
- Retains the deterministic 16-case, three-arm release scenario.
- Exercises source review, placement, build, guarded mutation behavior, traces,
  and evidence exports.

### Acme appointments

- Uses a substantial source `SKILL.md`, current booking policy, stale SOP,
  baseline prompt, style/knowledge references, strict tools, and synthetic state.
- Exercises verified identity, trusted IANA timezone, weekday customer-local
  `[09:00, 17:00)`, and exact confirmation before cancellation or a fee-bearing
  change.
- Runs 10 deterministic cases through the shared runner; the enforced arm has
  zero executed violations in the fixture assertion.
- Keeps cooldown and reschedule-limit clauses blocked pending a correlated
  temporal monitor; undefined “daylight hours” is unsupported.

The full browser suite verifies project switching in both directions, Acme
placements/build/routing/preservation/source-map inspection, and return to
isolated Northstar evidence.

### Browser evidence

![Acme placement routing with explicit blocked and human-review states](screenshots/acme-routing-desktop.png)

![Acme compiled bundle with an exact generated span and source anchor](screenshots/acme-build-desktop.png)

## 6. Artifact tree

Both verified builds contain 19 artifacts. The Acme build demonstrates the
generic shape:

```text
README.md
manifest.json
prompt-kernel.md
compilation-metrics.json
preservation-report.json
routing-report.json
source-map.json
tools.json
facts/
  evaluation.json
inputs/
  compiler-profile.json
  findings.json
  pinned-source-metadata.json
  placement-decisions.json
  rules.json
knowledge/
  appointment-scheduling.md
skills/
  appointment-scheduling/
    SKILL.md
policies/
  tool-policy.json
tests/
  regression.yaml
pending/
  unsupported-rules.json
```

The manifest pins the concrete artifact names and digests for a build. This
tree is a representative verified build, not a promise that every future
profile must emit the same scoped filenames.

## 7. Verified build roots and representative metrics

| Measure | Northstar retail | Acme appointments |
|---|---:|---:|
| Build root | `4e0601f04010ae67b837a718c1a97942b048fa9468eb4820c098ee54c9ab99df` | `efccbe65a0f57e4eafbc649dc4b707a2dd69949771d4310c53762b3b690e95c5` |
| Artifact count | 19 | 19 |
| Baseline always-loaded | 165 lines / 6,794 chars / 1,699 est. tokens | 40 / 2,284 / 571 |
| Compiled kernel | 7 / 198 / 50 | 7 / 221 / 56 |
| Expected task context | 32 / 1,113 / 279 | 29 / 1,273 / 319 |
| Scoped skill | 18 / 724 / 181 | 15 / 792 / 198 |
| Scoped knowledge | 7 / 191 / 48 | 7 / 260 / 65 |
| Guard | 7,884 chars / 1,971 est. tokens | 5,893 / 1,474 |
| Regression tests | 943 lines / 24,602 chars / 6,151 est. tokens | 583 / 18,121 / 4,531 |
| Total without manifest | 986 lines / 98,763 chars / 24,691 est. tokens | 623 / 155,881 / 38,971 |

The deterministic estimator is reported with the build. These values separate
always-loaded/task context from total generated evidence; total bundle size is
not presented as runtime prompt size.

For both builds:

- active clauses / explicit dispositions: `9 / 9`;
- routing coverage: `1.0`;
- verified source-anchor coverage: `1.0`;
- approved and severity-weighted preservation: `1.0`;
- high/critical guard-and-test placement: `1.0`;
- unsupported: `1`;
- unresolved: `1`;
- `behavioral_fidelity: not_measured`.

Acme additionally records two blocked clauses, one unsupported clause, and one
unresolved clause. The protected-literal regression confirms identifiers such
as `ACME-STYLE-001` do not invent numeric thresholds; actual `$200` and `30
days` literals remain detected.

## 8. Representative exact provenance

One final Acme generated span resolves as follows:

```text
knowledge/appointment-scheduling.md
  generated line 7
  generated UTF-8 bytes [153, 259)
    → rule.appointment.knowledge@1
    → placement version 1
    → appointment-knowledge.md@1
      source line 14
      source UTF-8 bytes [503, 609)
      source-anchor id 1f21fa…
      quote SHA-256 bc6b6f…
```

Tests independently slice the stored normalized UTF-8 bytes at every anchor,
decode them, compare the exact quote, recompute the quote hash, and match raw
and normalized document hashes. Generated spans are persisted and their count
matches the source-map span count.

## 9. Demo path

1. Run `make bootstrap`, then `make demo`; open `http://localhost:3000`.
2. Enter the seeded workspace and use **Project / domain** to select Acme.
3. In **Sources**, compare the current policy and superseded SOP, inspect owner,
   status/effective scope, both hashes, and exact line links.
4. In **Rules**, review conflict witness context, authority, exact sources, and
   the winner/loser consequence.
5. In **Placements**, inspect every non-superseded rule, current placement
   version, destinations, transform, disposition, reviewer/rationale, and
   missing/blocked/unsupported/human-review states. Concurrent updates use
   `expected_version` and an explicit `409` refresh path.
6. In **Build**, compile and inspect the full artifact tree, exact hashes and
   downloads, generated spans, routing, preservation, and context metrics.
7. Follow a source-derived span back to its exact source line; contrast it with
   reviewer-authored no-source-anchor attribution and compiler scaffold.
8. Confirm “Behavioral fidelity: Not measured.”
9. Run the Acme deterministic cases, then switch to Northstar and confirm the
   refund artifacts/evidence remain project-isolated.

## 10. Claims this evidence supports

- A reviewed clause can be given one explicit, versioned disposition.
- The same bounded compiler operates over two materially different synthetic
  domains without fixture semantics in generic compiler modules.
- Generated rule-derived text can be traced to exact verified source bytes and
  a placement version.
- Reviewer-authored guidance is attributable without pretending it is quoted
  source text.
- Stale, blocked, unsupported, and unresolved material remains explicitly
  visible instead of silently entering active artifacts.
- A covered deterministic proposal can be stopped before fixture mutation.
- Local builds and their evidence can be reproduced and inspected.

## 11. Claims this evidence does not support

- automatic extraction or understanding of arbitrary customer documents;
- automatic/general conflict discovery or formal verification;
- semantic equivalence or behavioral fidelity after refactoring;
- live-model quality, cost, latency, or reliability improvement;
- a live scheduling/refund integration or customer runtime SDK;
- upstream tau benchmark execution or a benchmark score;
- policy mutation scoring or generic temporal monitors;
- hosted Gate 1 operation, anonymous guest verification, or production SLOs;
- database RLS, secure customer uploads, signed promotion, enterprise controls,
  compliance, certification, or independent security assurance.

## 12. Exact next gate

The immediate next step is a product/evidence checkpoint, not automatic scope
expansion:

1. commit and, if desired, separately deploy this exact verified Gate 1 state;
2. keep Gate 0H anonymous hosted verification separate and do not infer it from
   local Gate 1;
3. gather design-partner evidence on whether authority/placement/source-map
   review saves real policy-engineering time;
4. only with explicit approval begin **Gate 2: bounded deterministic analysis**
   over the existing typed IR, with SAT/UNSAT/unknown/timeout and declared
   assumptions.

Temporal monitors, mutation testing, local/live models, upstream tau execution,
runtime SDKs, signed distribution, and enterprise control planes remain Gates
3–8 or later production work. They are not hidden parts of this Gate 1 verdict.
