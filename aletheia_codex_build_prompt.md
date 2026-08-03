# Copy/paste build prompt: Aletheia Policy CI

You are the lead product engineer and product designer for a new repository. Build the application described below end to end. The repository is empty at the start.

Do not stop after proposing a plan. Inspect the environment, make a short implementation plan, then create the complete working repository, run it, test it, inspect the rendered product, and fix defects you find. Work autonomously unless a genuine permission, credential, or irreversible-choice blocker requires the user. Do not ask the user to choose routine libraries or design details; those decisions are already fixed below.

At the end, report exactly what works, commands run, test results, local/hosted URLs if available, and any unfinished optional integration. Never represent a skipped network-dependent benchmark or live-model run as completed.

---

## 1. Product and course context

The product is **Aletheia**. The name is spelled A-l-e-t-h-e-i-a.

Brand line:

> Policy CI for AI agents.

Value proposition:

> Turn sprawling agent instructions into source-linked rules, a smaller prompt, deterministic tool guards, and repeatable release tests.

This is a prototype for University of Toronto Summer 2026 **CSC454 Business of Software** and **CSC491 Capstone**. The combined Assignment 3 presentation is eight minutes and is due Friday, August 7, 2026 at 1:30 p.m. The course expects a latest demo, build progress, updated build plan, technical feasibility and stack, product-evolution screenshots, and paper-prototype feedback. This is a serious prototype, not a production enterprise platform.

The team is John Ding, Amanda Yin, and Andrew Xie. Their earlier CSC491 concept focused on agent traces, controlled replay, comparison, and policy assurance. Preserve the useful ideas—trace, compare, and evidence—but use the new product entry point: **test policy and prompt changes before release**.

A recent founder/mentor interview supplied the key direction. Their customer-facing agent had an instruction file around 400 lines long. It became slower, more expensive, and easier to confuse; they reported better quality and lower cost after reducing it to around 50 lines. They gave an example rule such as only booking appointments during “daylight hours” in the customer’s timezone. They would pay for a product that reduced error rate and cost. Treat this as one strong interview signal, not market validation or proof of willingness to pay.

The product should demonstrate this insight accurately:

- agent instructions mix style, workflow, knowledge, runtime facts, handoff requirements, hard constraints, and quality checks;
- those categories should not all remain in one always-on prompt;
- a model can suggest a structured interpretation, but source verification and human approval are required;
- a prompt is not a security boundary for consequential tool calls;
- machine-decidable rules can be checked at a tool boundary;
- every change should be tested on the same sandbox fixtures and reported with provenance.

Do not build a generic prompt compressor. Do not build an observability clone. Do not claim formal verification, certification, universal safety, causal proof, lossless compression, or protection outside the covered sandbox tool adapter.

Use this exact evidence-boundary language in relevant product copy:

> Aletheia turns agent policies into reviewed prompt, guard, and regression-test artifacts, then shows how a candidate behaves on repeatable sandbox scenarios.

For deterministic decisions, use this narrower statement:

> Approved, machine-decidable rules can allow, block, or request approval before a covered sandbox tool call executes. Results are limited to the configured rules and calls passing through this adapter.

---

## 2. Product decision

Build a narrow **policy compiler and regression-test workbench** for a customer-facing retail/refund AI agent.

The user journey is:

1. Open a seeded project containing a baseline system prompt, current policy, stale SOP, style guide, tool schemas, and fictional order data.
2. Inspect rules extracted from exact source spans.
3. Review conflicts, duplicates, ambiguous language, and unenforceable facts.
4. Approve, edit, or reject candidate rules.
5. Compile approved rules into:
   - a smaller always-on prompt kernel;
   - a scoped refund workflow;
   - a knowledge/reference artifact;
   - deterministic tool-policy JSON;
   - declarative regression tests;
   - a source map and content-hashed manifest.
6. Run the same scenarios in three arms:
   - original prompt, observe only;
   - compiled prompt, observe only;
   - compiled prompt with enforcement.
7. Compare task outcomes, proposed/executed violations, false blocks, coverage, prompt size, tokens when known, latency, and first divergence.
8. Inspect a source-linked trace.
9. Export a release-evidence report as Markdown and JSON.

The complete demonstration must run without an API key using deterministic fixtures. Optional live extraction and live agent execution must be adapters, not foundations.

---

## 3. Users and job to be done

First-user hypothesis: a 20–200-person B2B company that builds customer-facing AI agents and is entering enterprise pilots or security review.

- Economic buyer: VP Engineering, Head of AI, or technical founder.
- Daily champion: AI/ML engineer or agent-platform engineer.
- Collaborator: solutions engineer or customer-success lead maintaining client-specific SOPs.
- Evidence consumer: enterprise security, risk, operations, or procurement reviewer.

Core job:

> Before I ship a prompt or policy change, help me see which rules changed, which are enforceable, whether important workflows still pass, and what evidence I can give my team or customer.

The application should look credible to this user. It must not look like a student CRUD dashboard or a generic AI-generated landing page.

---

## 4. Required scope

### P0: mandatory polished vertical slice

Implement all of this:

- seeded “Northstar Retail Refund Agent” project;
- versioned source ingest for direct text and `.txt`, `.md`, `.json`, `.yaml`, and text-based `.pdf` files up to 2 MB;
- source viewer with numbered lines and highlighted rule spans;
- source-linked rule table, review drawer, and revision-safe approve/edit/reject actions;
- deterministic conflict, duplicate, ambiguity, missing-fact, and missing-test findings;
- safe form-based editor for a small deterministic condition AST;
- deterministic artifact compiler;
- computed prompt line/character/token-estimate comparison and side-by-side diff;
- at least 16 Aletheia-authored refund boundary cases;
- deterministic fixture agent, sandbox tool registry, policy interpreter, three comparison arms, traces, metrics, and reports;
- background job record and local/hosted worker path;
- Typer CLI and FastAPI API using the same service layer;
- Next.js product UI and short landing page;
- Markdown and JSON export;
- local quick start, optional Docker Compose, CI, and deployment configuration;
- automated backend, frontend, and Playwright tests;
- designed empty/loading/error states and accessibility basics;
- no API key required for the demo or CI.

### P1: implement after P0 is green

- optional structured-LLM extractor behind a provider protocol;
- optional OpenAI-compatible live tool-calling agent adapter;
- pinned τ³-bench Retail sync/normalizer and adapter;
- exact 17-task benchmark manifest and provenance;
- graceful errors when optional dependencies or credentials are absent.

### Do not build

- user accounts, SSO, billing, organizations, or multi-tenancy;
- production SDK integrations for many agent frameworks;
- real refunds or external business APIs;
- arbitrary URL ingest, OCR, scanned PDFs, archives, browser automation, or a vector database;
- Redis, Celery, Kafka, Kubernetes, microservices, or a general workflow engine;
- voice, airline, telecom, or banking benchmark domains;
- general prompt red-teaming or a full prompt marketplace;
- React Flow diagrams or complex causal graphs;
- user-authored Python, JavaScript, Rego, Cedar, shell, or `eval`;
- LLM-as-judge for hard policy checks;
- automatic publication of model-generated rules;
- hard-coded marketing percentages, token savings, cost, test results, or latency.

---

## 5. Fixed technical architecture

Use a **modular monolith**. Core application services must not import FastAPI or UI code. The FastAPI routes, Typer CLI, and worker call the same services. The Next.js frontend is a thin typed API client.

### Stack

- Python 3.12.
- `uv` with a committed lockfile.
- FastAPI.
- Pydantic v2 with discriminated unions and generated JSON Schema.
- SQLAlchemy 2 async and Alembic.
- SQLite + WAL through `aiosqlite` as the zero-install local default.
- PostgreSQL through `asyncpg` for Docker/hosted use.
- Typer CLI.
- `pypdf` for text PDFs and safe YAML parsing.
- `regex` only if needed for bounded regex evaluation; enforce pattern/input length and timeout.
- Optional Instructor/Pydantic structured extraction in an extras group.
- Optional OpenAI-compatible model adapter in an extras group or small direct dependency. Never call it in tests.
- Next.js App Router with strict TypeScript. Use the current stable, non-canary release compatible with Node 22 LTS and commit the lockfile.
- `pnpm` workspace.
- Tailwind CSS and shadcn/ui-style local components.
- `@tanstack/react-query` for API state/polling.
- TanStack Table for rule/test/run tables.
- Recharts for one compact comparison chart.
- CodeMirror merge view for the prompt diff.
- Lucide icons.
- `openapi-typescript` plus `openapi-fetch` for a generated client.
- pytest, pytest-asyncio, and httpx.
- Vitest and Testing Library.
- Playwright Chromium.
- Ruff, mypy, ESLint, TypeScript strict checks.
- Vercel configuration for the web app.
- Render configuration for a FastAPI web service, a worker command from the same image, and PostgreSQL.

Do not use an agent framework, policy sidecar, or observability server. The architecture can expose future adapter/export seams for OPA/Cedar and OpenTelemetry/OpenInference without depending on them.

### High-level flow

```text
source files
  → immutable ingest and exact provenance
  → structured candidate extraction
  → deterministic quote/schema verification
  → conflict and ambiguity findings
  → human review
  → prompt/workflow/policy/test compilation
  → baseline/candidate/guarded sandbox runs
  → trace, comparison, and evidence report
```

---

## 6. Repository structure

Create this structure, adapting only when a framework convention genuinely requires it:

```text
/
├── README.md
├── LICENSE
├── THIRD_PARTY_NOTICES.md
├── .env.example
├── .gitignore
├── Makefile
├── docker-compose.yml
├── render.yaml
├── package.json
├── pnpm-workspace.yaml
├── apps/
│   ├── api/
│   │   ├── pyproject.toml
│   │   ├── uv.lock
│   │   ├── alembic.ini
│   │   ├── migrations/
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── cli.py
│   │   │   ├── worker.py
│   │   │   ├── api/routes/
│   │   │   ├── core/
│   │   │   ├── db/
│   │   │   ├── models/
│   │   │   ├── schemas/
│   │   │   ├── services/
│   │   │   │   ├── ingestion.py
│   │   │   │   ├── extraction.py
│   │   │   │   ├── verification.py
│   │   │   │   ├── findings.py
│   │   │   │   ├── compiler.py
│   │   │   │   ├── policy/
│   │   │   │   ├── test_generation.py
│   │   │   │   ├── runner/
│   │   │   │   ├── metrics.py
│   │   │   │   └── reporting.py
│   │   │   ├── adapters/
│   │   │   └── seed/
│   │   └── tests/
│   └── web/
│       ├── app/
│       ├── components/
│       ├── features/
│       ├── lib/
│       ├── public/
│       └── tests/
├── packages/
│   └── api-client/
├── data/
│   ├── demo/northstar-retail/
│   └── benchmarks/tau3-retail/
├── scripts/
│   └── sync_tau3_retail.py
├── docs/
│   ├── architecture.md
│   ├── course-context.md
│   ├── demo-script.md
│   ├── evidence-boundary.md
│   └── build-plan.md
└── .github/workflows/ci.yml
```

Keep generated/cache/runtime files out of version control. Do not create placeholder packages or files with no purpose.

---

## 7. Persistence and immutability

Use UUID strings externally, UTC timestamps, SHA-256 content hashes, optimistic revision checks, and SQLAlchemy’s portable `JSON` type rather than Postgres-only JSONB.

Implement these entities:

1. `projects`
   - `id`, `slug`, `name`, `domain`, `description`, `mode`, timestamps.
2. `documents`
   - project ID, kind, name, version, original hash, normalized text, MIME type, line count, exact/estimated token fields, origin/provenance JSON, timestamps.
3. `rules`
   - stable key, integer revision, title, normalized text, category, effect, severity, status, confidence, scope JSON, condition JSON, enforcement, decidability, source references JSON, target tools, exceptions, reviewer note, timestamps.
4. `findings`
   - type, severity, related rule IDs, proof status (`proved`, `suspected`, `unknown`), message, witness JSON when deterministic, resolution state/note.
5. `builds`
   - project, status, input manifest/hash, compiler version, artifact bundle JSON/text, source map, stats, content hash, timestamps.
6. `test_cases`
   - project, stable key, provenance, messages, initial state, expected assertions, rule IDs, tags, scripted trajectories, review status.
7. `runs`
   - project/build, requested arms, adapter/model, dataset manifest, status, metrics, start/end times.
8. `scenario_results`
   - run/test/arm, verdicts, metrics, final-state hash, first divergence, trace ID.
9. `trace_events`
   - result/trace ID, sequence, type, payload, rule IDs, duration, timestamp.
10. `reports`
    - run, verdict, evidence JSON, rendered Markdown, content hash, timestamp.
11. `jobs`
    - kind, payload, status, progress, resource ID, owner, lease expiry, attempt count, error code/message, timestamps.

Do not silently overwrite source text, published builds, scenario results, or reports. Edits create revisions or new immutable snapshots. A build stores the exact source/rule/test revisions it used.

Alembic must create the database from zero. The seed/reset path must be idempotent.

---

## 8. Versioned data contracts

Create Pydantic schemas and export their JSON Schemas for at least:

- `SourceRef`
- `RuleIR`
- condition AST nodes
- `PolicyDecisionRequest`
- `PolicyDecisionResult`
- `TestCaseSpec`
- `TraceEvent`
- `RunManifest`
- `BuildManifest`
- `EvidenceReport`

### Rule IR

The following is illustrative and should validate as the real contract:

```json
{
  "schema_version": "0.1",
  "id": "rule.refund.approval_threshold",
  "revision": 2,
  "title": "Refunds above $200 require approval",
  "normative_text": "Require supervisor approval before issuing a refund over $200.",
  "category": "hard_constraint",
  "effect": "require_approval",
  "severity": "high",
  "scope": {
    "domain": "retail",
    "tools": ["issue_refund"],
    "lifecycle": "pre_tool"
  },
  "when": {
    "all": [
      {"fact": "tool.name", "op": "eq", "value": "issue_refund"},
      {"fact": "tool.arguments.amount", "op": "gt", "value": 200}
    ]
  },
  "requires": [
    {
      "event": "approval.granted",
      "match": {"amount": {"fact": "tool.arguments.amount"}}
    }
  ],
  "exceptions": [],
  "enforcement": "guard",
  "decidability": "machine_decidable",
  "status": "approved",
  "confidence": 0.96,
  "source_refs": [
    {
      "document_id": "doc-policy-v3",
      "line_start": 41,
      "line_end": 43,
      "quote": "Refunds over $200 require supervisor approval.",
      "source_sha256": "computed-at-seed-time"
    }
  ]
}
```

Categories and destinations:

- `style` → short prompt kernel;
- `workflow` → scoped workflow and tests;
- `knowledge` → reference artifact;
- `runtime_fact` → typed runtime field, not copied static prose;
- `hard_constraint` → concise prompt summary + deterministic policy + tests;
- `handoff` → typed handoff contract + tests;
- `quality` → deterministic assertion or optional model/human review, never a hard guard unless fully decidable.

Rule review states: `candidate`, `needs_review`, `approved`, `rejected`, `superseded`.

Enforcement values: `prompt`, `guard`, `test_only`, `human_review`.

Decidability values: `machine_decidable`, `model_judged`, `human`.

---

## 9. Safe policy interpreter

Generated policy is data, not executable code.

Support an allowlisted JSON AST:

- boolean: `all`, `any`, `not`;
- comparison: `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `in`, `not_in`;
- string/presence: `exists`, `contains`, and bounded `regex`;
- fact roots: `tool`, `state`, `user`, `context`, `events`;
- lifecycle: `pre_tool` in the MVP;
- effects: `allow`, `deny`, `require_approval`, `require_prior_event`, `observe_only`.

Do not use `eval`, `exec`, dynamic imports, shell calls, generated Python, or user-supplied callbacks.

Implement:

- strict type validation;
- safe dotted-path resolution;
- an allowlist of available fact paths derived from tool/state schemas;
- deterministic canonical JSON and decision hashes;
- exact evaluated facts and contributing rule IDs in every result;
- `indeterminate` with a reason for unknown facts/types;
- fail closed for indeterminate high-severity rules protecting mutating tools;
- configurable default for unprotected/read-only tools;
- precedence: deny → missing prerequisite → approval → allow → no applicable rule/default.

For bounded regex, cap pattern length, input length, and execution time. If that cannot be made reliable, keep regex out of guarded seed rules and return `indeterminate` rather than risking unbounded work.

Add comprehensive tests for every operator, nested boolean form, types, missing facts, precedence, approval matching, event history, hashes, and state-mutation safety.

---

## 10. Source ingest and provenance

Accept UTF-8 direct text and `.txt`, `.md`, `.json`, `.yaml`, and text-based `.pdf` up to 2 MB.

Reject remote URLs, archives, executable/binary input, scanned PDFs without usable text, and oversized files.

Pipeline:

1. Hash original bytes.
2. Parse as untrusted data without executing anything.
3. Normalize newlines while preserving a page/line locator map.
4. Number lines deterministically.
5. Identify heading/paragraph sections.
6. Store normalized text and provenance.
7. Render escaped source text in the web UI; never use unsanitized HTML.

Chunk optional model requests at heading/paragraph boundaries, roughly 1,500–2,500 estimated tokens with a small overlap. Include document ID, hash, version, line range, and numbered text. Do not add embeddings or a vector store.

The hosted demo must show a visible warning that the seed data is fictional and that confidential uploads should not be used. It is acceptable to disable uploads when `DEMO_MODE=true`, while local mode keeps them enabled.

---

## 11. Candidate extraction and deterministic verification

Implement two extractors behind a protocol:

1. `FixtureExtractor` — required default; loads checked-in candidate rules for the seed project.
2. `StructuredLLMExtractor` — optional; uses typed structured output and bounded retries.

The optional extractor has no tools and no network access except its model API. It treats document text as data. It proposes:

- title and normative clause;
- category/effect/severity;
- exact quote and line range;
- subject/topic/semantic key;
- action/tool, conditions, obligations, exceptions;
- candidate machine-decidability;
- confidence and clarification question.

Then application code must:

- verify that the exact quote occurs inside the source span;
- recompute line boundaries and source hash;
- validate tool names and fact paths against uploaded schemas;
- reject unsupported operators and malformed ASTs;
- mark unverifiable proposals as `needs_review` with an explicit reason;
- never auto-approve model output.

Do not use LLM output to decide that a hard rule is active.

The model layer must be an internal protocol returning canonical typed responses. Provider SDK response classes must never leak into core services or database models. Live model calls require server-only configuration, timeouts, token limits, bounded retry, and no silent cross-provider fallback.

---

## 12. Finding engine

Implement deterministic findings first:

- exact duplicate or canonical-equivalent rule;
- direct conflict across overlapping scope with incompatible effect, threshold, or obligation;
- impossible numeric/set condition where obvious;
- shadowed/redundant same-effect rule where the limited AST can prove it;
- missing tool or fact path;
- exact source quote/hash mismatch;
- stale source when a newer version supersedes a clause;
- ambiguous language from a configurable lexicon, including “reasonable,” “large,” “soon,” “daylight hours,” and “when possible” without a measurable definition;
- orphan approved hard rule without positive/negative tests.

Use proof status:

- `proved` only for deterministic evidence;
- `suspected` for heuristic/model suggestions;
- `unknown` when overlap/equivalence cannot be established.

Do not silently resolve conflicts by document order. The human must approve priority or reject/supersede a rule. Even after resolution, preserve the finding in history.

Seed exact findings for:

- current 30-day return window versus stale 60-day SOP;
- current approval required above $200 versus old automatic refunds up to $250;
- repeated identity/confirmation clauses;
- “daylight hours” with no numeric range or timezone source;
- at least one hard rule that needs a runtime fact absent from the current schema.

---

## 13. Artifact compiler

Compilation is deterministic over approved rule revisions. Do not call an LLM during compilation.

Produce this immutable bundle:

```text
builds/<build-id>/
├── prompt-kernel.md
├── workflows/refunds.md
├── knowledge/refund-reference.md
├── policies/tool-policy.json
├── tests/regression.yaml
├── source-map.json
├── manifest.json
└── README.md
```

Compiler behavior:

- retain global role, goals, response contract, routing, high-level workflow, and concise summaries of hard constraints in the always-on prompt;
- move detailed refund steps to a scoped workflow;
- move stable explanatory/reference prose to a knowledge file;
- move changing values to typed runtime facts;
- compile only approved machine-decidable hard constraints into the policy AST;
- keep a concise human-readable hard-rule summary in the prompt so the model can avoid repeatedly proposing blocked calls;
- keep style rules in the prompt, never in the hard guard;
- generate test references and source mapping for every emitted clause/rule/test;
- canonicalize and remove reviewed duplicates;
- block compilation while an unresolved critical conflict remains;
- never silently delete negation, numeric bounds, exception clauses, or provenance;
- compute exact lines/characters and a labelled token estimate. Use actual provider usage when supplied; otherwise use a documented estimator such as `ceil(characters / 4)` labelled `char_4_estimate`;
- display actual reduction, including zero or a regression. Do not target or fake a percentage.

The manifest must contain compiler version, timestamps, all input hashes and rule revisions, generated artifact hashes, tokenizer/estimator label, unresolved findings, test IDs, and evidence limitations. Hash the canonical manifest.

---

## 14. Seeded demo corpus

Create realistic, internally consistent, fictional fixtures. Do not use real names, customer data, secrets, or external services.

Project: **Northstar Retail Refund Agent**.

Create:

- `baseline-system-prompt.md`: plausible, repetitive customer-support instructions with natural headings and overlaps. About 180–260 meaningful lines is enough; do not pad it with nonsense to hit the mentor’s 400-line anecdote.
- `refund-policy-v3.md`: current 30-day eligibility, identity, confirmation, refund destination, duplicate-refund, returnability, and $200 approval rules.
- `refund-sop-legacy.md`: stale 60-day window and old automatic-refund-up-to-$250 language.
- `support-style.md`: concise, empathetic response guidance plus the ambiguous callback instruction using “daylight hours.”
- `tools.json`: typed schemas for `get_customer`, `get_order`, `request_supervisor_approval`, `issue_refund`, `cancel_item`, `escalate_case`, and `book_callback`.
- `orders.json`: fictional users, orders, items, dates, payment methods, returnability, prior refunds, and approval records.
- fixture candidate rules and scripted trajectories.

The seed code must locate exact quotes in source files and compute line spans/hashes rather than relying on brittle manually entered line numbers.

The UI must show `Aletheia demo` provenance badges and a visible “Synthetic data—no customer records” note.

---

## 15. Declarative test cases

Implement a versioned YAML/JSON test contract with:

- stable ID and title;
- provenance;
- linked rule/source IDs;
- tags;
- messages;
- trusted initial state;
- tool schemas;
- maximum turns and timeout;
- expected task outcome;
- required/forbidden proposed and executed tool calls;
- argument predicates;
- call-order/prior-event constraints;
- expected policy decisions/reason codes;
- expected final-state predicates;
- scripted trajectories by arm for fixture mode.

For each hard rule, support positive, negative, threshold-boundary, and exception cases when applicable.

Include at least these 16 cases:

1. eligible refund on day 29;
2. eligible refund exactly on day 30;
3. ineligible refund on day 31;
4. $200 refund without approval;
5. $200.01 refund without approval;
6. $249 refund with a matching approval event;
7. order details requested before identity verification;
8. verified customer may view the order;
9. alternate refund destination is rejected;
10. duplicate refund for a line item is rejected;
11. mutation before explicit customer confirmation is rejected;
12. non-returnable item follows escalation;
13. stale 60-day SOP produces a conflict finding/test;
14. old $250 automatic-refund language produces a conflict finding/test;
15. “daylight hours” is ambiguous and does not compile to a guard;
16. a style rule remains prompt/test content and never becomes a hard guard.

Generate numeric boundary cases at `x-ε`, `x`, and `x+ε` using decimal-safe arithmetic for money.

---

## 16. Sandbox tools, adapters, and execution

Create a static allowlisted sandbox tool registry. No tool can access the network, shell, arbitrary filesystem, environment secrets, or a real business service.

All mutating tools operate on a deep copy of a test’s initial state. They must produce a typed result and an explicit state diff.

Implement adapters:

- `FixtureAgentAdapter`: required and deterministic; consumes scripted trajectories.
- `RecordedTraceAdapter`: evaluates imported trace events without executing a model.
- `OpenAICompatibleAgentAdapter`: optional live tool-calling loop.
- `TauRetailAdapter`: optional P1 benchmark adapter.

Run these three arms:

1. `baseline_unenforced`: original prompt; policy engine observes only.
2. `compiled_unenforced`: compiled prompt/workflow; policy engine observes only.
3. `compiled_enforced`: compiled artifacts; policy decisions are enforced.

Do not merge prompt and guard effects into one unlabeled comparison.

Execution loop:

1. Deep-copy and hash initial state.
2. Provide the selected prompt/workflow/messages/tools to the adapter.
3. Record messages and proposed calls.
4. Validate tool arguments.
5. Evaluate applicable pre-tool rules.
6. Observe-only arms record the decision but execute valid sandbox calls.
7. Enforced arm executes only `allow`; otherwise return typed `denied` or `approval_required` results and do not mutate state.
8. Record result, state diff, latency, and usage if available.
9. Stop on final answer, routed approval, maximum turns, or error.
10. Evaluate calls, decisions, and final state deterministically.

Trace event types:

`run_started`, `user_message`, `assistant_message`, `tool_proposed`, `policy_evaluated`, `tool_blocked`, `approval_required`, `tool_executed`, `tool_result`, `state_changed`, `final_answer`, `assertion_evaluated`, `run_finished`, `error`.

The UI and data model must clearly distinguish **proposed** from **executed** calls.

Every policy event links to rule revisions, source references, evaluated facts, reason code, and decision hash.

---

## 17. Metrics and report logic

Compute, do not hard-code:

- deterministic task/end-state success;
- attempted hard-rule violation rate;
- executed hard-rule violation rate;
- forbidden-call escape rate;
- false-block rate on allowed cases;
- approval-route accuracy;
- per-rule and worst-rule pass rate;
- rule/source/test coverage;
- positive/negative/boundary coverage;
- unnecessary tool calls;
- prompt lines, characters, and estimated/actual tokens;
- model input/output tokens when returned;
- duration;
- optional cost only when a user-provided pricing configuration exists—otherwise `N/A`;
- optional `pass^k` only for repeated trials, correctly labelled.

Keep model/provider/tool errors separate from policy failures.

The report verdict is one of:

- `Changes required`;
- `Ready for sandbox pilot`.

Never use `Safe`, `Certified`, `Compliant`, or `Production ready`.

Every report must begin with scope/evidence boundary and include:

- dataset provenance and whether it is deterministic fixture or simulated benchmark;
- adapter and exact model label if applicable;
- build/run/test/tool-schema hashes;
- rule revisions and compiler/runner versions;
- test counts and comparison arms;
- blocking findings and top failures;
- computed metrics;
- links from failures to trace and source evidence;
- limitations;
- Markdown and canonical JSON exports with a content hash.

---

## 18. Background jobs

Use the `jobs` table and a worker command. Do not add Redis.

- Local default: `DEMO_INLINE_JOBS=true` may execute synchronously/immediately after creating the job record.
- Hosted: run `uv run aletheia worker` as a separate process from the same package.
- PostgreSQL worker: claim jobs in a short transaction with `FOR UPDATE SKIP LOCKED`; store owner, lease expiry, attempts, progress, and error.
- SQLite: one local worker with an atomic status claim.
- Reclaim expired leases or mark unrecoverable jobs stale.
- Make seed, compile, and fixture runs idempotent by input hash where practical.

Job states: `queued`, `running`, `succeeded`, `failed`, `cancelled`, `stale`.

Use one-second polling in the web UI. Do not add WebSockets/SSE unless the polling implementation is already complete and the extra work is trivial.

---

## 19. API

Prefix with `/api/v1`. Use a consistent error envelope:

```json
{
  "code": "machine_readable_code",
  "message": "Human-readable explanation",
  "details": {},
  "request_id": "..."
}
```

Required endpoints:

### System

- `GET /healthz`
- `GET /readyz`
- `GET /api/v1/config/public`
- `POST /api/v1/demo/reset`, available only when demo mode permits it

### Projects/documents

- `GET /api/v1/projects`
- `POST /api/v1/projects`
- `GET /api/v1/projects/{project_id}`
- `GET /api/v1/projects/{project_id}/documents`
- `POST /api/v1/projects/{project_id}/documents`
- `GET /api/v1/documents/{document_id}`
- `POST /api/v1/projects/{project_id}/analysis-jobs`

### Rules/findings

- `GET /api/v1/projects/{project_id}/rules`
- `GET /api/v1/rules/{rule_id}`
- `PATCH /api/v1/rules/{rule_id}` with expected revision
- `POST /api/v1/rules/{rule_id}/approve`
- `POST /api/v1/rules/{rule_id}/reject`
- `GET /api/v1/projects/{project_id}/findings`
- `PATCH /api/v1/findings/{finding_id}`

### Builds/tests

- `POST /api/v1/projects/{project_id}/builds`
- `GET /api/v1/builds/{build_id}`
- `GET /api/v1/builds/{build_id}/artifacts/{path}`
- `GET /api/v1/projects/{project_id}/test-cases`
- `POST /api/v1/projects/{project_id}/test-generation-jobs`
- `PATCH /api/v1/test-cases/{test_case_id}`

### Runs/reports

- `POST /api/v1/projects/{project_id}/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/results`
- `GET /api/v1/scenario-results/{result_id}/trace`
- `POST /api/v1/runs/{run_id}/reports`
- `GET /api/v1/reports/{report_id}`
- `GET /api/v1/reports/{report_id}/export?format=markdown|json`
- `GET /api/v1/jobs/{job_id}`

Configure CORS from `WEB_ORIGIN`. Add request IDs, structured errors, validation limits, and OpenAPI descriptions/examples. Generate and commit/update the TypeScript API client; CI should fail if regeneration creates an uncommitted diff.

---

## 20. CLI

Implement these commands using the same services as the API:

```bash
uv run aletheia db upgrade
uv run aletheia demo seed --reset
uv run aletheia analyze --project northstar-retail --extractor fixture
uv run aletheia compile --project northstar-retail
uv run aletheia test --project northstar-retail --adapter fixture --arms all
uv run aletheia report --latest --format markdown
uv run aletheia worker
uv run aletheia benchmark sync-tau-retail
uv run aletheia benchmark run-tau-retail --adapter fixture
```

Add `--json` where useful. Print deterministic IDs and hashes. Return non-zero on failure. Help text should be polished.

---

## 21. τ³-bench integration

This integration is optional at runtime but must be implemented honestly after P0.

Pin exactly:

- repository: `https://github.com/sierra-research/tau2-bench`
- tag: `v1.0.1`
- official release-page short commit: `fc0055d`
- licence: MIT, copyright Sierra Research 2025

The v1.0.0 release introduced the audited task-quality fixes. The v1.0.1 release notes state that its changes are confined to banking knowledge and that all other domains are unaffected. Use v1.0.1 because it is the current signed tag. During sync, resolve and record the tag’s full commit; reject the checkout if its short SHA does not match `fc0055d`. Do not substitute an unverified full SHA in source code or documentation.

Exact Retail task manifest:

```text
10 11 12 13 16 24 30 31 48 50 51 53 57 76 82 83 84
```

Known-open Retail tasks 4, 5, and 7 must not be included.

The sync script must:

1. fetch/clone only the pinned tag/commit into a cache/temp directory;
2. resolve the signed tag to its full commit, verify that its short SHA matches `fc0055d`, and record the full value before reading data;
3. read only the Retail policy, database, tasks/split, domain environment/tools/model/utilities, and final-state evaluator dependencies;
4. create an Aletheia manifest mapping every selected task ID to its purpose and upstream path;
5. record upstream URL, tag, commit, task IDs, selected file hashes, import time, and licence;
6. preserve the MIT notice in `THIRD_PARTY_NOTICES.md` and copy `LICENSE.upstream` when data is copied;
7. skip voice, banking/RAG, web leaderboard, RL, and all other domains;
8. be idempotent and fail loudly on hash/commit mismatch.

Prefer an optional pinned dependency/import plus normalized selected data over copying and modifying the upstream runtime.

If network access is unavailable, do not block P0. Finish and test the sync/adapter interfaces with a tiny fake upstream fixture, document the exact command, and report that the real sync/run was not executed. Do not create fake τ results.

Label this dataset in the UI/report as:

> Simulated, real-world-like retail benchmark—not real customer data.

Also cite, in `THIRD_PARTY_NOTICES.md` or a research note:

- original τ-bench paper: `https://arxiv.org/abs/2406.12045`
- τ²-bench paper: `https://arxiv.org/abs/2506.07982`
- Amazon τ²-Bench-Verified: `https://github.com/amazon-agi/tau2-bench-verified`
- correction audit: `https://github.com/amazon-agi/tau2-bench-verified/blob/main/FIXES.md`
- SABER: `https://arxiv.org/abs/2512.07850`

Do not maintain both Sierra and Amazon runtimes. Sierra v1.0.1 is the runtime source; Amazon’s correction log is an audit/test-design source.

---

## 22. Web application and visual design

Build a polished product, not a slide mockup. Use real seeded API data for every metric and status.

### Visual system

- Background: `#F6F8FB`.
- Surface: white.
- Primary ink: `#0F172A`.
- Brand navy: `#17345F`.
- Action blue: `#2563EB`.
- Allow teal: `#0F766E`.
- Approval amber: `#B45309`.
- Block red: `#B42318`.
- Thin cool-grey borders, an 8 px spacing grid, 10 px radius, and restrained shadows.
- Package a variable sans and mono font locally; do not depend on a runtime font CDN.
- Use Lucide icons with text labels.
- Do not use gradients, glassmorphism, glow, stock robot imagery, oversized pills, emoji icons, fake terminal decoration, or decorative charts.
- Never communicate status through colour alone.
- Desktop-first at 1280×800, responsive to tablet/mobile.
- Semantic HTML, keyboard focus, accessible names, adequate contrast, reduced-motion support.

### Navigation and routes

```text
/
/demo
/projects/[projectId]/overview
/projects/[projectId]/sources
/projects/[projectId]/rules
/projects/[projectId]/builds/[buildId]
/projects/[projectId]/tests
/runs/[runId]
/scenario-results/[resultId]
/reports/[reportId]
```

Shared project navigation: **Overview · Sources · Rules · Build · Tests · Report**.

### Landing page

Keep it short and useful.

- Headline: `Policy CI for AI agents.`
- Supporting line: `Turn sprawling instructions into source-linked rules, enforceable tool policies, and repeatable release tests.`
- Primary button: `Open the refund demo`.
- Secondary link: `See the workflow`.
- Small computed preview card labelled `Demo run`.
- Three steps: `Review rules` → `Build artifacts` → `Test a release`.
- Note: `Runs on synthetic data. No safety certification.`

No long generic marketing sections.

### Overview

- project title, Demo data badge, current build, last run;
- cards for sources, approved rules, unresolved critical findings, test coverage;
- horizontal stage indicator;
- one clear primary action based on state;
- recent activity.

### Sources

- left document list with kind/version/status;
- centre source viewer with numbered lines and highlighted spans;
- right linked rules/findings panel;
- exact-text search;
- upload/paste modal in local mode;
- confidentiality warning or disabled upload in hosted demo mode.

### Rules

- table columns: status, rule, type, severity, enforcement, source, tests;
- filters: Needs review, Critical, Guarded, Missing test;
- finding cards above the table with human wording, e.g. `Conflict: old SOP says 60 days; policy v3 says 30.`;
- rule detail drawer with exact quote, normalized text, source link, plain-English condition, form-based AST editor, related tests, clarification note, approve/reject;
- never require raw-code editing.

### Build

- build and manifest hashes;
- tabs: Prompt kernel, Refund workflow, Tool policy, Regression tests;
- CodeMirror original/candidate merge view;
- computed line/token cards;
- routing summary such as number kept/moved/guarded/tested;
- critical conflict disables `Build candidate` and explains exactly why.

### Tests

- coverage by rule and positive/negative/boundary type;
- cases table with provenance badge, tags, expected decision, review state;
- controls for adapter, arms, case set, optional model;
- primary button `Run comparison`;
- real completed/total job progress—no fake animated stages.

### Run comparison

- verdict banner `Changes required` or `Ready for sandbox pilot`;
- metric cards for all three arms, using `N/A` when unavailable;
- one compact grouped bar chart for task success, executed violations, and false blocks;
- table with case, linked rules, three arm verdicts, and first divergence;
- filters for failed, blocked, false block, changed outcome, benchmark source.

### Trace detail

- linear event timeline;
- case/expected/initial-final hashes summary;
- selected-event payload, policy reason, evaluated facts, source-linked rules, state diff;
- clear visual distinction between proposed and executed tool calls;
- first-divergence marker between selected arms.

### Report

- evidence scope first;
- verdict and blocking reasons;
- prompt facts, coverage, results, failures, provenance;
- model/adapter/build/run hashes;
- download Markdown and JSON.

### UI states

Design empty, loading, success, partial, and error states for every core page. Errors include request ID and retry. Skeletons reflect final layout. No lorem ipsum, dead buttons, or “coming soon” in mandatory paths.

Use concise human writing. Avoid phrases such as “revolutionary,” “seamless,” “AI-powered insights,” “unlock,” and “next-generation.”

---

## 23. Security and privacy requirements

- Treat prompts, SOPs, tool descriptions, and traces as untrusted data.
- Optional extractor has no tools and receives only bounded chunks.
- Store credentials only server-side; redact them from errors, traces, and logs.
- Validate file type/size and parser work; never follow remote links.
- Escape/sanitize all displayed source and Markdown.
- Validate all tool arguments.
- Tool registry is static and sandbox-only.
- Policy AST cannot execute code.
- No real side effects or outbound network from test tools.
- No full source text in routine structured logs.
- Use canonical JSON and hashes for evidence artifacts.
- Add request/job/run IDs and redaction tests.
- Public demo uses fictional data and a reset mechanism.
- Protect demo-reset endpoint by environment mode and, if exposed, a simple server-side secret or deployment-only action; do not put the secret in the browser.
- Add strict CORS and sensible security headers/CSP.
- Do not add runtime package/plugin downloads.

Document later requirements—auth, tenant isolation, encrypted object storage, retention/deletion controls, audit administration—without implementing them.

---

## 24. Tests and quality gates

### Backend unit tests

At minimum:

- every AST operator and precedence;
- missing/invalid fact and fail-closed paths;
- exact quote/span/hash verification;
- rule validation and revisions;
- deterministic findings;
- compiler routing, protected spans, source-map completeness;
- money/date boundary generation;
- blocked call never mutates state;
- approval and prior-event matching;
- metrics and report hashes;
- seed idempotence;
- worker claim/lease transitions for SQLite and PostgreSQL logic where feasible;
- τ manifest parser and fake-sync test.

### Backend integration tests

- project → analyze → review → compile → run → report;
- invalid upload and unverified quote;
- critical conflict blocks compilation;
- job success/failure/stale transition;
- API error envelope and optimistic revision conflict;
- migrations from empty database.

### Frontend tests

- rule filters and source navigation;
- drawer condition form validation;
- computed diff/stat labels;
- test coverage and run filters;
- proposed/executed trace distinction;
- report evidence boundary/export;
- accessible names for key dialog/table/button interactions.

### Playwright flows

1. Landing → Open refund demo → inspect the 30/60-day source-linked conflict.
2. Resolve/approve the required seeded rules → build candidate → inspect prompt diff.
3. Run comparison → open `$200.01 without approval` trace → export report.

Make the seed state support these flows deterministically. If critical conflicts initially block build, the UI should offer a clear seeded resolution action; Playwright must exercise it.

### CI

- Ruff.
- mypy.
- pytest.
- ESLint.
- `tsc --noEmit`.
- Vitest.
- generated OpenAPI client consistency.
- Playwright Chromium against the seeded app.

Do not use flaky sleeps; use user-facing locators, web-first assertions, and polling.

---

## 25. Local scripts, deployment, and documentation

Required commands:

```bash
make bootstrap
make demo
make test
make ci
make benchmark-sync
docker compose up --build
```

`make bootstrap` should install locked dependencies, migrate the database, generate the client, and seed the demo. `make demo` starts API and web and prints URLs. Docker is optional, not required for ordinary local development.

`.env.example` must include documented, non-secret defaults for:

- `DATABASE_URL`
- `WEB_ORIGIN`
- `NEXT_PUBLIC_API_URL`
- `DEMO_MODE`
- `DEMO_INLINE_JOBS`
- optional model/base URL/key/model name;
- worker poll/lease limits;
- upload size;
- log level.

README must include:

- what Aletheia is and is not;
- one-command/short quick start;
- architecture diagram;
- demo flow;
- fixture versus live mode;
- data/evidence boundary;
- optional benchmark sync/run;
- tests;
- deployment;
- known prototype limitations.

Add:

- `docs/course-context.md` explaining CSC454/CSC491 and the direction change;
- `docs/demo-script.md` with the exact 90-second script;
- `docs/build-plan.md` with completed gates and next milestones;
- `docs/evidence-boundary.md` with permitted claims;
- `THIRD_PARTY_NOTICES.md` with benchmark and library attributions as required.

For Render, use one image/package with separate web and worker commands, a pre-deploy migration command, and `/healthz`. For Vercel, set the web root correctly and document the API URL variable. Do not attempt a real external deployment unless the environment/user authorizes it; still create valid configuration and verify production builds locally.

---

## 26. Implementation order and exit gates

Follow this order. Do not begin visual polish before the deterministic vertical slice works.

### Gate 0: scaffold and invariants

- create workspaces/config/lockfiles;
- database/migration/config/health;
- Pydantic contracts and JSON Schema export;
- policy interpreter with tests;
- seed corpus and exact source hashes.

Exit: bootstrap and core policy tests pass.

### Gate 1: backend vertical slice

- ingest/source viewer API;
- fixture extraction and verification;
- findings and human review;
- deterministic compiler;
- test cases, sandbox, three-arm fixture runner;
- trace, metrics, report;
- CLI, jobs, worker, API.

Exit: complete no-key workflow works from CLI and API.

### Gate 2: polished web product

- landing and navigation;
- Overview, Sources, Rules, Build, Tests, Run, Trace, Report;
- typed generated client and polling;
- responsive/accessibility/error/loading states;
- Playwright flows.

Exit: the 90-second demo is smooth at 1280×800 and tablet width.

### Gate 3: optional model and benchmark adapters

- structured LLM extractor;
- OpenAI-compatible live tool loop;
- τ³ sync/normalizer/adapter and exact manifest;
- provenance and graceful missing-key/dependency states.

Exit: adapters do not break fixture mode; execute real sync only if network permits.

### Gate 4: hardening and handoff

- CI and production builds;
- Docker/Render/Vercel config;
- documentation/third-party notices;
- final screenshot/render inspection and defect fixes.

Exit: `make ci` passes, or any environmental exception is clearly evidenced and narrowly documented.

---

## 27. Definition of done

The work is complete only when all mandatory statements are true:

1. A fresh developer can run the deterministic demo without an API key.
2. Every approved seed rule has a verified exact source reference.
3. Every guarded hard rule has positive and negative/boundary coverage.
4. A blocked tool proposal cannot mutate sandbox state.
5. All three arms start from identical fixtures.
6. The UI distinguishes proposed and executed calls.
7. The prompt comparison is computed, not hard-coded.
8. The report records provenance, hashes, adapter/model, scope, and limitations.
9. The 16-case seeded suite runs through UI and CLI.
10. The `$200.01 without approval` trace visibly shows proposal, policy decision, no unauthorized mutation, and approval routing in the guarded arm.
11. Core API, component, and three Playwright flows pass.
12. Production builds succeed.
13. No secrets, real customer data, lorem ipsum, dead P0 controls, or unsupported safety claims remain.
14. Optional failures do not prevent fixture mode.
15. README and docs make the project understandable to a course evaluator and a prospective technical user.

---

## 28. Required 90-second demo behavior

Ensure the finished seed and UI support this exact flow:

1. Open Northstar Retail and explain that rules are spread across a prompt, current policy, and stale SOP.
2. Open Rules. Show the 30/60-day conflict, $200/$250 conflict, and “daylight hours” ambiguity.
3. Resolve the seeded critical conflicts using the current policy, then approve the machine-decidable refund threshold. Show its exact source and plain-English condition.
4. Build the candidate. Show actual prompt diff and the prompt/workflow/policy/test artifacts.
5. Run the deterministic 16-case three-arm comparison.
6. Open `$200.01 without approval`. In baseline, show the refund proposal/execution. In guarded mode, show the same proposal intercepted, `require_approval`, no state mutation, and the approval route.
7. Open the report. Point to scope, provenance, metrics, and the honest verdict.

Use the product itself—not hard-coded screenshots—to demonstrate these facts.

---

## 29. Final engineering behavior

While building:

- prefer simple, readable implementations over clever abstraction;
- keep modules cohesive and functions typed;
- make invalid states difficult to represent;
- write tests alongside the policy/compiler/runner code;
- preserve unrelated existing files if the repository turns out not to be empty;
- use safe, non-destructive commands;
- inspect actual rendered pages with Playwright screenshots at desktop and tablet widths;
- fix overflows, clipped content, inaccessible controls, inconsistent spacing, confusing labels, and empty/error-state defects;
- do not lower test rigor merely to make CI green;
- do not leave core TODOs, mocked API responses, or static metric cards in mandatory paths;
- do not wait for the user after the initial plan—continue through implementation and verification.

At handoff, provide:

- concise outcome summary;
- repository tree overview;
- exact start/test commands;
- tests and builds run with pass/fail counts;
- screenshot paths if produced;
- benchmark/live-model integration status;
- the smallest honest list of remaining optional work.

Build Aletheia now.
