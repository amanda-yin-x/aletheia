# Aletheia research map — 80 sources v2

**Original review date:** 2026-08-03  
**Repository reconciliation date:** 2026-08-04  
**Version:** 2.0  
**Purpose:** product positioning, adjacent-product analysis, user/practitioner evidence, benchmark design, formal/AI implementation, and enterprise architecture  
**Companion files:** `aletheia_independent_review_and_product_decision_v2.md` and `aletheia_refined_codex_execution_handoff_v3.md`  
**Predecessor:** `aletheia_research_map_80_sources (1).md`, retained unchanged as historical input  
**Predecessor SHA-256:** `206d2767343a31f24b3a6e7dcb02af3805c0dc205bcf25867788711fbc861ff4`

## Repository reconciliation preface

The 80 external entries below are retained from the original research map so
source numbering, links, evidence labels, and attribution remain reviewable.
This successor changes their repository interpretation; it does not claim that
each external page was freshly revalidated on 2026-08-04.

The current implementation evidence changes the earlier synthesis in four ways:

- the local Northstar deterministic foundation is Gate 0 complete in its settled
  tested fixture scope;
- Supabase, Render, and Cloudflare are provisioned, but hosted anonymous guest
  verification remains Gate 0H work in progress;
- a generic source-aware compiler, exact provenance/placement contracts,
  structural preservation metrics, and the Acme appointments corpus now exist as
  a Gate 1 implementation that is complete in the verified local two-domain
  fixture scope, including API/database/frontend/packaging/browser evidence;
- solver analysis, temporal monitors, mutation testing, live models, upstream
  tau execution, runtime SDKs, and enterprise controls remain absent Gates 2–8.

External evidence informs product and technical choices. It does not prove that
Aletheia has implemented a feature, passed a test, improved model behavior,
achieved performance, or found product-market fit. For repository status, use
current code/tests and the canonical capability/current-state documents.

## How to interpret this map

This is a decision-oriented source map, not a bibliometric review or proof of market traction.

- **Primary docs/spec/paper** means the source is authoritative for its own technical design or reported research.
- **Repository/issue/thread** is useful implementation or practitioner evidence, but individual reports are anecdotal.
- **Vendor page** establishes how a product is positioned and which features it claims; it does not independently verify adoption, performance, security, or customer outcomes.
- Recent preprints establish that the direction is active; their headline results remain author-reported until independently replicated.

The review intentionally includes direct competitors, mature adjacent platforms, open-source implementations, standards, papers, and user threads. It does not count duplicate search results or generic SEO summaries.

## A. Evaluation, observability, and guardrail platforms

| # | Source | Evidence type | Decision-relevant takeaway |
|---:|---|---|---|
| 1 | [Promptfoo introduction](https://www.promptfoo.dev/docs/intro/) | Official docs | Declarative tests, custom assertions, model comparison, red teaming, and local/CI execution already exist; do not build a generic eval runner as the wedge. |
| 2 | [Promptfoo CI/CD](https://www.promptfoo.dev/docs/integrations/ci-cd/) | Official docs | JSON/HTML/JUnit outputs and CI thresholds establish the expected developer workflow for Aletheia's CLI. |
| 3 | [Braintrust evaluation](https://www.braintrust.dev/docs/evaluate) | Official docs | Datasets, experiments, arbitrary tasks, scorers, and production/offline loops already cover generic AI evaluation. |
| 4 | [LangSmith evaluation](https://docs.langchain.com/langsmith/evaluation) | Official docs | Production traces can become datasets and offline regressions; Aletheia should export evidence rather than recreate this category. |
| 5 | [Langfuse documentation](https://langfuse.com/docs) | Official docs | Open/self-hostable tracing, prompt management, datasets, experiments, and evaluation make observability a poor primary wedge. |
| 6 | [Arize Phoenix overview](https://arize.com/docs/phoenix) | Official docs | OpenTelemetry traces, datasets, replay, prompt workbench, and experiments already cover general analysis UX. |
| 7 | [Parea evaluation overview](https://docs.parea.ai/evaluation/overview) | Official docs | Repeated trials, saved datasets, trace debugging, and experiment comparison overlap Aletheia's generic runner features. |
| 8 | [Giskard documentation](https://docs.giskard.ai/) | Official docs | Agent tests, business-specific scenarios, continuous red teaming, collaboration, RBAC, and enterprise controls are already bundled. |
| 9 | [Patronus documentation](https://docs.patronus.ai/docs) | Official docs | Experiments, evaluators, production monitoring, and trace analysis further crowd general evaluation. |
| 10 | [Galileo documentation](https://docs.galileo.ai/what-is-galileo) | Official docs | Offline evaluation, observability, agent metrics, and production guardrails are marketed as one platform. |
| 11 | [NeMo Guardrail types](https://docs.nvidia.com/nemo/guardrails/about-nemo-guardrails-library/rail-types) | Official NVIDIA docs | Input, retrieval, dialogue, execution, and output rails already span the agent lifecycle, including tool-call validation. |
| 12 | [Guardrails AI `Guard`](https://guardrailsai.com/guardrails/docs/concepts/guard) | Official docs | Structured validators and configurable failure behaviour cover model input/output validation; Aletheia should focus on business-policy lifecycle. |
| 13 | [Portkey guardrails](https://portkey.ai/docs/product/guardrails) | Official docs | Gateway-level synchronous/asynchronous checks and custom deny/log behaviour overlap runtime enforcement. |
| 14 | [Invariant Guardrails](https://github.com/invariantlabs-ai/invariant) | Official repository | Its rule language expresses cross-tool sequence and data-flow rules and can intercept MCP/LLM traffic; temporal runtime policy is not unique. |
| 15 | [Humanloop August 2025 changelog](https://humanloop.com/docs/changelog/2025/08) | Official changelog | Acquisition/sunset history illustrates category consolidation and vendor-lifecycle risk; portable artifacts matter. |

## B. Direct product and research overlap

| # | Source | Evidence type | Decision-relevant takeaway |
|---:|---|---|---|
| 16 | [TypeGlish](https://typeglish.dev/) | Vendor/product docs; maturity unverified | Directly markets contradiction/vagueness detection, prompt bloat analysis, compilation, tests, and CI. |
| 17 | [PathReader](https://pathreader.ai/) | Vendor page; maturity unverified | Very close upstream overlap: policy documents, source-linked candidates, human review, and deterministic decisions. |
| 18 | [RAIGO](https://raigo.ai/) | Vendor page; claims unverified | Advertises policy upload, AI extraction, compiled rules, CI, and runtime enforcement. |
| 19 | [Mirage](https://www.trymirage.dev/) | Product/release page; claims unverified | Uses one policy file in deterministic CI simulations and a production gateway; runtime-plus-CI messaging is crowded. |
| 20 | [Phrony](https://phrony.com/) | Product/docs; claims unverified | Versioned manifests, tool policy, human approval, traces, deploy, and rollback overlap the proposed data plane. |
| 21 | [Edictum](https://edictum.ai/) | Product/docs; claims unverified | Cross-language pre-tool decisions, workflow gates, approvals, audit, observe mode, and replay overlap runtime scope. |
| 22 | [Faramesh core](https://github.com/faramesh/faramesh-core) | Repository | Pre-execution policy, approval, credential isolation, and durable evidence further crowd a generic enforcement wedge. |
| 23 | [PolicyLayer](https://policylayer.com/) | Vendor page; claims unverified | MCP proxy, scoped grants, deterministic policies, approvals, credential mediation, and audit target agent tool calls directly. |
| 24 | [Tandem](https://tandem.ac/) | Vendor page; claims unverified | Frames tools, data, approvals, and records as a governance runtime for agents with real access. |
| 25 | [EVE proof-bearing governance docs](https://docs.eveaicore.com/start-here) | Vendor docs; claims unverified | Deterministic pre-action decisions and signed decision records overlap Aletheia's future enforcement/evidence story. |
| 26 | [GuardEntry Agent Policy Router](https://guardentry.ai/agent-policy-router) | Vendor page; claims unverified | Offers allow/block/approval/verify decisions and correlation/audit for agent actions. |
| 27 | [APort](https://aport.io/) | Vendor page; claims unverified | Agent identity/passports, pre-action authorization, guardrails, and audit overlap control-plane ambitions. |
| 28 | [BoundaryAI](https://boundaryai.ai/) | Vendor page; performance unverified | Markets deterministic action-level enforcement and signed records across tools/data/robots; threshold blocking is not differentiation. |
| 29 | [Enkrypt Agent Policy Engine](https://www.enkryptai.com/product/agent-policy-engine) | Vendor page; claims unverified | Enterprise agent policy enforcement is already an explicit product category. |
| 30 | [Sponsio](https://github.com/SponsioLabs/Sponsio) | Official repository; alpha | Natural-language rules compiled to deterministic temporal contracts, multi-framework adapters, and runtime checks directly overlap the proposed temporal core. |
| 31 | [IBM `tool_guard`](https://github.com/IBM/tool_guard) | Research repository | Takes Markdown policies and OpenAPI tools, generates reviewable per-tool policies/examples, then Python guards; this is the closest open implementation comparator. |
| 32 | [AWS Automated Reasoning concepts](https://docs.aws.amazon.com/bedrock/latest/userguide/automated-reasoning-checks-concepts.html) | Official AWS docs | Source documents become formal rules/variables with grounding/fidelity and versioning; Aletheia must differentiate through agent-action release workflow, portability, and local operation. |
| 33 | [IBM policy-adherence paper](https://research.ibm.com/publications/towards-enforcing-company-policy-adherence-in-agentic-workflows) | Peer-reviewed paper page | Describes build-time policy-to-guard compilation plus pre-action runtime checks on a tau domain; the broad concept is research-adjacent, not novel by itself. |

## C. Practitioner and implementation threads

| # | Source | Evidence type | Decision-relevant takeaway |
|---:|---|---|---|
| 34 | [HN: controlling agents that take real actions](https://news.ycombinator.com/item?id=47134506) | Practitioner thread | Discussion favours model proposals plus deterministic gates/human approval, while noting integration and maintenance cost. |
| 35 | [HN: AI agent benchmarks are broken](https://news.ycombinator.com/item?id=44531697) | Practitioner thread | Raises grader validity, contamination, holdouts, and human calibration; public scores are not sufficient product evidence. |
| 36 | [OpenAI Agents SDK issue: per-tool authorization middleware](https://github.com/openai/openai-agents-python/issues/2868) | GitHub user issue | A practitioner distinguishes content guardrails from identity/scope/session-aware tool authorization, confirming demand and adjacent framework evolution. |
| 37 | [Promptfoo issue: local/privacy claim](https://github.com/promptfoo/promptfoo/issues/5808) | GitHub user issue | Reported remote behaviour under a “local” expectation shows why Aletheia must make provider/data boundaries explicit and testable. |
| 38 | [OpenAI Agents SDK issue: structured output plus tool calls](https://github.com/openai/openai-agents-python/issues/1263) | GitHub user issue | Structured output and tool use can fail in combination; schema validity and tool correctness need separate tests. |
| 39 | [Qwen issue: unstable tool-call formatting](https://github.com/QwenLM/Qwen3.6/issues/125) | GitHub issue | Qwen model/serving combinations can emit unexpected tool formats; capability probes and pinned engine/model versions are mandatory. |
| 40 | [Guardrails AI issue: agent integration](https://github.com/guardrails-ai/guardrails/issues/651) | GitHub user issue | Framework streaming/agent integration can be nontrivial; one framework-neutral dispatcher is a better MVP than many adapters. |

## D. Benchmarks, formal methods, and instruction evidence

| # | Source | Evidence type | Decision-relevant takeaway |
|---:|---|---|---|
| 41 | [tau-bench paper](https://arxiv.org/abs/2406.12045) | Research paper | Stateful user-agent-tool evaluation, database end state, and repeated-trial reliability motivate Aletheia's sandbox metrics. |
| 42 | [tau2-bench paper](https://arxiv.org/abs/2506.07982) | Research paper | Dual-control environments reinforce that user and agent actions jointly determine outcomes. |
| 43 | [tau2/tau3 repository at v1.0.1](https://github.com/sierra-research/tau2-bench/tree/v1.0.1) | Official repository | Provides the upstream runner, environments, tasks, evaluators, and MIT-licensed code that should remain authoritative. |
| 44 | [tau v1.0.1 release](https://github.com/sierra-research/tau2-bench/releases/tag/v1.0.1) | Official release | Supplies the pinned release and short commit prefix `fc0055d`; provenance must resolve the full tag commit at sync time. |
| 45 | [Versioned Retail tasks](https://raw.githubusercontent.com/sierra-research/tau2-bench/v1.0.1/data/tau2/domains/retail/tasks.json) | Official versioned data | Contains 114 task records and embedded open issues, including tasks 4, 5, and 7; the selected 17 tasks are a smoke subset. |
| 46 | [SABER: Small Actions, Big Errors](https://arxiv.org/abs/2512.07850) | Research preprint | Author-reported results emphasize failures around mutating actions and task-quality ceilings; action-level metrics are appropriate. |
| 47 | [Evidence-supported benchmark bounds](https://arxiv.org/abs/2605.10448) | Research preprint | Argues outcome checks may support bounds/unknowns rather than one definitive score; Aletheia should preserve evidence and abstention. |
| 48 | [Don't Make Models Guess Security and Safety](https://arxiv.org/abs/2604.15579) | Research preprint/systematic review | Reviews symbolic-guard evaluation across many benchmarks; supports deterministic checks while keeping scope claims bounded. |
| 49 | [Autoformalization of Agent Instructions into Policy-as-Code](https://arxiv.org/abs/2606.26649) | Research preprint | LLM generator/critic plus Cedar directly overlaps instruction-to-policy work; source review, CI, temporal rules, and runtime evidence are the product differentiators to test. |
| 50 | [Agent-C](https://arxiv.org/abs/2512.23738) | Research preprint | Temporal policy DSL, SMT encoding, and runtime enforcement show that temporal agent contracts are an active technical direction. |
| 51 | [Z3 Guide](https://microsoft.github.io/z3guide/) | Official technical guide | Defines satisfiability, models, and solver semantics; Aletheia should expose SAT/UNSAT/unknown/timeout and declared assumptions. |
| 52 | [LTLf/LDLf runtime monitoring](https://arxiv.org/abs/2004.01859) | Research paper | Provides finite-trace monitoring foundations and clarifies the safety/liveness distinction. |
| 53 | [OPA policy testing](https://www.openpolicyagent.org/docs/policy-testing) | Official docs | Policy unit tests and coverage are mature patterns; generated tests must be measurable rather than decorative. |
| 54 | [NIST pseudo-exhaustive ABAC testing](https://www.nist.gov/publications/pseudo-exhaustive-testing-attribute-based-access-control-rules) | NIST publication | Systematic combinations are useful for policy-rule boundary and interaction testing. |
| 55 | [AgentDojo](https://github.com/ethz-spylab/agentdojo) | Research repository | Separates utility and security under prompt injection; useful later, but not the first customer-policy benchmark. |
| 56 | [ToolSandbox](https://github.com/apple/ToolSandbox) | Research repository | Stateful multi-turn tool-use diagnostics and milestone checks inform trace and end-state design. |
| 57 | [Berkeley Function Calling Leaderboard](https://github.com/ShishirPatil/gorilla/tree/main/berkeley-function-call-leaderboard) | Research repository | Function/tool-selection and argument diagnostics are complementary to business-policy adherence. |
| 58 | [IFScale](https://arxiv.org/abs/2507.11538) | Research preprint | Author-reported instruction-following degradation as simultaneous instructions grow motivates testing prompt refactoring, not assuming it helps. |
| 59 | [Lost in the Middle](https://doi.org/10.1162/tacl_a_00638) | Peer-reviewed research | Long-context use varies with information position; it does not establish a universal 400-line threshold. |
| 60 | [LongLLMLingua](https://arxiv.org/abs/2310.06839) | Research paper | Context compression can help in some settings, but is not evidence that policy semantics survive compression; deterministic preservation gates are needed. |

## E. Qwen and local serving

| # | Source | Evidence type | Decision-relevant takeaway |
|---:|---|---|---|
| 61 | [Qwen3.5-9B model card](https://huggingface.co/Qwen/Qwen3.5-9B) | Official model card | Records license, model behaviour, context, and serving guidance; actual local context/quality must be measured and pinned. |
| 62 | [Qwen3.5 repository](https://github.com/QwenLM/Qwen3.5) | Official repository | Compatibility and deployment guidance evolve; pin model and serving versions rather than mutable tags. |
| 63 | [Ollama Qwen3.5 9B](https://ollama.com/library/qwen3.5:9b) | Official registry entry | Provides a practical local artifact and size/digest information for the course path. |
| 64 | [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs) | Official docs | JSON-schema constrained output supports candidate extraction, but semantic source truth still requires application verification. |
| 65 | [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling) | Official docs | Supports multi-turn tool loops; Aletheia must still validate proposals and mediate execution. |
| 66 | [vLLM structured outputs](https://docs.vllm.ai/en/stable/features/structured_outputs/) | Official docs | Provides server-side structured-output options, with behaviour that should be capability-tested rather than assumed equivalent to Ollama. |
| 67 | [vLLM tool calling](https://docs.vllm.ai/en/stable/features/tool_calling/) | Official docs | Tool parsers and automatic-tool-choice configuration are model/engine-specific and need pinned conformance tests. |
| 68 | [Qwen vLLM deployment guidance](https://qwen.readthedocs.io/en/stable/deployment/vllm.html) | Official Qwen docs | Documents Qwen-specific reasoning/tool-parser flags; record exact serving configuration in every live report. |

## F. Enterprise architecture, storage, and integration

| # | Source | Evidence type | Decision-relevant takeaway |
|---:|---|---|---|
| 69 | [OPA management architecture](https://www.openpolicyagent.org/docs/management-introduction) | Official docs | Distributed local decision points with a logical control plane are a strong analogue for later Aletheia bundle distribution. |
| 70 | [OPA bundle management](https://www.openpolicyagent.org/docs/management-bundles) | Official docs | Revisioned/signed bundles, ETags, persistence, last-known-good, and atomic activation are mature patterns to borrow later. |
| 71 | [Cedar policy validation](https://docs.cedarpolicy.com/policies/validation.html) | Official docs | Schema validation is distinct from runtime authorization; Aletheia needs typed rule/tool/fact contracts before activation. |
| 72 | [NIST SP 800-207 Zero Trust Architecture](https://csrc.nist.gov/pubs/sp/800/207/final) | NIST standard | Separating policy decision and enforcement functions supports a control-plane/reference-runtime boundary, not a synchronous control-plane call on every action. |
| 73 | [PostgreSQL `SKIP LOCKED`](https://www.postgresql.org/docs/current/sql-select.html) | Official database docs | Queue-like consumers are an appropriate use, but leases, heartbeat, retry, cancellation, and idempotency still need implementation. |
| 74 | [PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html) | Official database docs | Owners and bypass roles complicate RLS; shared tenancy should wait until it is required and can be tested comprehensively. |
| 75 | [OWASP AI Agent Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html) | OWASP guidance | High-impact actions need independent validation, exact action-bound approvals, least privilege, and idempotent retries. |
| 76 | [OWASP File Upload Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) | OWASP guidance | Public customer uploads require content/type limits, isolation, scanning, safe storage, and parser controls; keep them out of the current demo. |
| 77 | [AWS: making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/) | Primary engineering guidance | Caller request IDs should bind atomically to parameters/results; tool execution and build/run jobs need idempotency contracts. |
| 78 | [JSON Schema 2020-12 core](https://json-schema.org/draft/2020-12/json-schema-core) | Formal specification | Use language-neutral versioned contracts for policy IR, facts, tools, tests, bundles, decisions, and evidence. |
| 79 | [OpenAPI 3.1.1](https://spec.openapis.org/oas/v3.1.1.html) | Formal specification | Generate web/CLI clients from the HTTP contract and fail CI on drift. |
| 80 | [OpenTelemetry sensitive-data guidance](https://opentelemetry.io/docs/security/handling-sensitive-data/) | Official docs | Raw policies, prompts, tool arguments, and outputs should not enter default telemetry; export a redacted projection from a stable internal event model. |

## Research synthesis

The external evidence supports six decisions:

1. **Keep the project, change the centre.** Runtime guardrails are crowded; source-aware policy change review and CI is the stronger remaining wedge.
2. **Accept the bounded Gate 1 result.** The working tree contains a second domain and a generic source-aware compiler whose local two-domain, packaging, and browser checkpoint passed; hosted deployment and real model/customer integrations remain later work.
3. **Keep hard decisions deterministic and bounded.** The current path uses schemas, exact source verification, human review, placement decisions, tests, and runtime code. LLM proposals, solvers, and generic monitors remain future gates.
4. **Use benchmarks carefully.** Retail-17 is an intentionally selected smoke suite; a proper external result requires the upstream full split, exact version/configuration, and separately reported applicability.
5. **Right-size the architecture.** The current modular monolith, SQLite/Postgres, provider seams, SQL jobs, and CLI are enough for Gate 1 proof. A customer runtime SDK, signed distribution, broader shared tenancy, and enterprise controls remain later work.
6. **Validate adoption, not only technical feasibility.** The next evidence milestone is real redacted artifacts, an adopted CI check, and a design-partner commitment—not a longer production checklist.
