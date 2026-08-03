# Aletheia

**Policy CI for AI agents.**

[![CI](https://github.com/amanda-yin-x/aletheia/actions/workflows/ci.yml/badge.svg)](https://github.com/amanda-yin-x/aletheia/actions/workflows/ci.yml)
[![Status: active build](https://img.shields.io/badge/status-active_build-2563eb)](docs/evidence-boundary.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-0f766e)](LICENSE)

Aletheia turns sprawling agent instructions into source-linked rules, a smaller
prompt, deterministic tool guards, and repeatable release tests. The included
Northstar Retail project is a working, API-key-free policy workspace: review two
concrete source conflicts, approve a strict refund boundary, compile an immutable artifact
bundle, compare three execution arms, inspect a blocked `$200.01` refund trace,
and export Markdown/JSON release evidence.

![Aletheia landing page showing the source-linked refund policy decision](docs/screenshots/landing-desktop.png)

> Aletheia turns agent policies into reviewed prompt, guard, and regression-test
> artifacts, then shows how a candidate behaves across repeatable release
> scenarios.

Aletheia is not a generic compressor, production agent firewall, formal
verification system, compliance certification, or claim about live-model
performance. Every bundled record is generated evaluation data; no customer
records are included.

## Why policy CI

Agent instructions rarely live in one clean prompt. A current policy can say
30 days and approval above `$200` while a legacy SOP still says 60 days and
automatic refunds up to `$250`. If both reach an agent as plain text, the first
visible failure may be a customer-facing side effect.

The bundled Northstar scenario makes that problem concrete. Aletheia exposes
the conflict for review, compiles the chosen boundary, and intercepts a
`$200.01` refund proposal before the covered operation changes state. It
preserves the proposal, policy decision, source rule, and unchanged state as
separate evidence.

## Quick start

Requirements: Python 3.12+, `uv`, Node 22 LTS, and Corepack. No API key or Docker
is required.

```bash
make bootstrap
make demo
```

Open [http://localhost:3000](http://localhost:3000). The API and OpenAPI UI are
at [http://localhost:8000](http://localhost:8000) and
[http://localhost:8000/docs](http://localhost:8000/docs).

`make bootstrap` installs locked dependencies, migrates SQLite, and resets the
bundled evaluation workspace. `make demo` runs the API and Next.js app. Docker
is optional:

```bash
docker compose up --build
```

> **Container verification note:** data paths are configuration-driven and the
> web image includes the shared design tokens, but Docker was unavailable in the
> final verification environment. Treat container/hosted startup as
> configuration-only until a clean-image smoke test is added; the local quick
> start above is the verified path.

## Product walkthrough

1. Open **Northstar Retail Refund Agent** and go to **Rules**.
2. Review the proved 30/60-day and $200/$250 conflicts plus the unresolved
   “daylight hours” ambiguity.
3. Resolve the critical conflicts in favour of Refund Policy v3. Open **Approval
   above $200**, inspect its exact quote and `amount > 200` condition, then
   approve the revision.
4. Open **Build** and compile a candidate. Prompt lines/characters/token estimate
   are computed from persisted text; the output includes the prompt kernel,
   refund workflow, tool policy, regression YAML, source map, and manifest.
5. Open **Tests**, run all 16 cases, and inspect the `$200.01 without approval`
   guarded trace. The proposal is recorded, the adapter requests approval, and
   no refund state mutation occurs.
6. Create the evidence report and download Markdown or canonical JSON.

The exact 90-second talk track is in [docs/demo-script.md](docs/demo-script.md).
For a candid implementation inventory, correctness audit, and production plan,
see
[docs/current-state-and-production-roadmap.md](docs/current-state-and-production-roadmap.md).

## Architecture

```text
source files → immutable documents + exact spans → reviewed Rule IR
    → deterministic compiler → prompt / workflow / policy / tests / source map
    → deterministic replay → pre-tool policy decision → covered tools
    → three-arm results → traces / metrics → immutable evidence report

                         ┌ Typer CLI
domain services + SQL ───┼ FastAPI / SQL job worker
                         └ Next.js typed client
```

The backend is a modular monolith. Core policy/compiler/runner modules do not
import FastAPI; HTTP routes and the Typer CLI call the same async services.
SQLite in WAL mode is the zero-install default, while the same SQLAlchemy models
support PostgreSQL. See [docs/architecture.md](docs/architecture.md).

The landing-page research, pinned design references, dependency decisions, and
motion/accessibility contract are recorded in
[docs/design-references.md](docs/design-references.md). The complete upstream
Hallmark skill subtree is retained project-locally under
`.codex/skills/hallmark` with its upstream license and provenance.

## Commands

```bash
make bootstrap                 # locked install, migrate, seed
make demo                      # API :8000 + web :3000
make test                      # pytest + Vitest
make ci                        # lint, typing, unit tests, production web build

cd apps/api
uv run aletheia analyze --project northstar-retail --extractor fixture
uv run aletheia compile --project northstar-retail
uv run aletheia test --project northstar-retail --adapter fixture --arms all
uv run aletheia report --latest --format markdown
uv run aletheia worker --once
```

A fresh seed intentionally blocks compilation. Resolve the two current-vs-legacy
critical findings and approve the threshold through the UI/API before compiling.
This is part of the product's human review gate, not a setup failure.

## Deterministic and optional live modes

The internal `fixture` runner is deterministic and never calls a model. It is
the only execution path used by tests and the public workspace. Provider protocols and
explicit failure stubs exist, but the OpenAI-compatible live tool loop is not
implemented and no live result is bundled or claimed. Missing credentials never
affect fixture mode.

The optional tau3 Retail sync is provenance-checked:

```bash
make benchmark-sync
```

It targets `sierra-research/tau2-bench` tag `v1.0.1`, verifies the resolved short
commit is `fc0055d`, and records the selected paths, hashes, MIT licence, and
exact task IDs `10 11 12 13 16 24 30 31 48 50 51 53 57 76 82 83 84`.
Benchmark data must be labelled “Simulated, real-world-like retail benchmark—not
real customer data.” A sync is optional and never blocks the bundled suite.

## Tests and evidence boundary

- Python: condition operators/precedence, fail-closed unknown facts, exact quote
  verification, critical-build gate, compiler/source map, boundary runner,
  mutation safety, ingestion validation, metrics/report hashes, seed idempotence.
- Web: strict TypeScript, ESLint, Vitest presentation/condition/trace checks.
- Browser: five Playwright Chromium paths covering the workspace flow, landing
  interactions/reduced motion, and 320/375/414/768 px overflow checks.

```bash
make ci
corepack pnpm --filter @aletheia/web test:e2e
```

For approved, machine-decidable rules, the covered tool proxy deterministically
allows, blocks, or requests approval before executing a covered tool call. This
is limited to configured rule semantics and calls passing through that proxy.
See [docs/evidence-boundary.md](docs/evidence-boundary.md).

## Deployment

- Vercel root: `apps/web`; set `NEXT_PUBLIC_API_URL`.
- Render: one API image with separate web and worker commands, Alembic pre-deploy,
  managed PostgreSQL, and `/healthz`.
- Docker Compose: intended local web/API/PostgreSQL stack with a
  configuration-driven API data root; startup still awaits a clean-image smoke
  test.

No external deployment is performed by repository scripts.

## Current limitations

- No authentication, tenancy, real customer data, or real business side effects.
- No OCR, URL ingestion, arbitrary policy code, or general agent framework SDK.
- The model extractor/live agent interfaces are optional and are not exercised
  in CI; fixture results do not predict live model quality or cost.
- The policy interpreter covers a deliberately small allowlisted AST and only
  the static covered-tool registry.
- The public reset endpoint is appropriate only for generated evaluation data
  and should be protected by `DEMO_RESET_SECRET` if exposed.

## Documentation

- [Current state and production roadmap](docs/current-state-and-production-roadmap.md)
- [Architecture](docs/architecture.md)
- [Evidence boundary](docs/evidence-boundary.md)
- [Design references and decisions](docs/design-references.md)
- [90-second product walkthrough](docs/demo-script.md)
- [Build plan and gates](docs/build-plan.md)

## License and acknowledgements

Aletheia is released under the [MIT License](LICENSE). Third-party data,
libraries, the project-scoped Hallmark skill, and research references are
documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and
[docs/design-references.md](docs/design-references.md).
