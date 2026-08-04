# Landing-page design references and decisions

**Snapshot:** 2026-08-03  
**Scope:** the public Aletheia landing page, its motion system, and the project-scoped design guidance retained for future work

This is a bookmark and decision record, not a claim that Aletheia authored or
bundles the referenced libraries. The repositories were inspected at the exact
revisions below before the landing redesign. Only Hallmark's Codex skill is
vendored; no React Bits, Vanta, GSAP, or Lenis source code is copied into the
application.

## Reference register

| Reference | Revision inspected | License at inspection | Useful idea | Decision for Aletheia |
|---|---|---|---|---|
| [Nutlope/hallmark](https://github.com/Nutlope/hallmark) | `aeb42fb354ff4efa36ab475773a082315a3af2ce` | MIT | Structural variety, honest copy, token discipline, responsive and anti-slop gates | Vendored as a project-scoped Codex skill under `.codex/skills/hallmark`; attribution and license retained. |
| [DavidHDev/react-bits](https://github.com/DavidHDev/react-bits) | `d26ed7a476148f1253cca3f5bc9f679fda53e1f5` | MIT plus Commons Clause in `LICENSE.md` | TextType, FadeContent, count-up, and interaction concepts | Used as interaction research only. A smaller original one-shot typed line avoids copying code, looping defaults, and an unnecessary GSAP dependency. |
| [tengbao/vanta](https://github.com/tengbao/vanta) | `f8b351906688b56f0fc744e53bde81fc3c56f150` | MIT | Lifecycle of animated WebGL backgrounds | Not installed. A full-canvas WebGL/Three.js or p5.js effect is disproportionate for a policy/evidence product and competes with the content. |
| [greensock/GSAP](https://github.com/greensock/GSAP) | `13e2b790546426a1a2e0e9b409f3f8dc6d6611f2` | GreenSock/Webflow standard no-charge license; not MIT | Timelines, scoped cleanup via `gsap.context()`, `matchMedia`, ScrollTrigger | Not installed. The page needs one type-in and one entrance sequence, both expressible with native React/CSS at lower bundle size and without introducing non-MIT license-compliance and maintenance overhead. Reconsider only for a genuinely complex product-tour timeline. |
| [darkroomengineering/lenis](https://github.com/darkroomengineering/lenis) | `2a6573775ac7883bd0606963bad04f47ee7eeeba` | MIT | Smooth-scroll lifecycle and anchor handling | Not installed. Native scrolling preserves expected behavior in the product's nested source, trace, table, drawer, and code scrollers. |
| [Claude Code product page](https://claude.com/product/claude-code) | Live site inspected 2026-08-03 | Anthropic custom webfonts; no redistribution licence observed | Anthropic Serif for display, Anthropic Sans for body/UI, Anthropic Mono for code | Used as typography direction only. No Anthropic font files are copied or hotlinked. |
| [Newsreader](https://github.com/google/fonts/tree/main/ofl/newsreader) + [Geist](https://github.com/vercel/geist-font) | Current upstream inspected 2026-08-03 | SIL Open Font License 1.1 | Open variable serif with optical sizing plus a precise sans/mono family | Loaded through `next/font`: Newsreader for display, Geist for body/UI, and Geist Mono for code. This is the redistributable approximation of the Claude Code type roles. |

Package versions and licensing can change. Re-check the upstream repository and
license before adding a dependency or copying source.

## Hallmark retention and update path

The full upstream `skills/hallmark` tree is retained, not only `SKILL.md`,
because the skill conditionally reads its `references/components`, `genres`,
`macrostructures`, `themes`, and `verbs` directories.

Project-scoped location:

```text
.codex/skills/hallmark/
├── SKILL.md
├── LICENSE
├── UPSTREAM.md
└── references/
```

It was installed through Codex's skill installer. A new Codex session opened in
this repository can discover it. Before updating, compare the upstream license,
release notes, and local `UPSTREAM.md`; do not overwrite it blindly.

## Research behind the page story

The landing page avoids invented adoption numbers, testimonials, benchmark
leadership, and “best” claims. It instead demonstrates the actual bundled
Northstar failure path. A verified customer requests gift-card credit for the
bundled `N-1099` order: `$249`, nine days after delivery, and marked
non-returnable. The retained SOP appears to authorize the action because it
allows 60-day returns, automatic refunds through `$250`, and the requested
destination. Current policy requires escalation for non-returnable items, the
original payment method, and matching approval above `$200`. The same exact
`issue_refund` proposal is compared with and without pre-tool enforcement.

That story aligns with current primary guidance and research:

- In [Moffatt v Air Canada, 2024 BCCRT 149](https://www.canlii.org/en/bc/bccrt/doc/2024/2024bccrt149/2024bccrt149.html), conflicting chatbot guidance and the airline's policy became a customer-visible representation for which the business remained responsible. The Northstar scenario is fictional evaluation data; it models the failure pattern rather than claiming to reproduce or prevent that case.
- The UK Competition and Markets Authority's [2026 AI-agent consumer-law guidance](https://www.gov.uk/government/publications/complying-with-consumer-law-when-using-ai-agents/complying-with-consumer-law-when-using-ai-agents) specifically asks businesses to test refund agents against differing rights, time limits, and amounts, with human oversight before deployment.
- [Stripe's refund documentation](https://docs.stripe.com/refunds) states that refunds return to the original payment method and describes duplicate-credit risk around concurrent dispute and refund paths. This supports treating destination and current payment state as decision inputs, not conversational preferences.
- [Shopify's idempotent refund-mutation guidance](https://shopify.dev/changelog/making-idempotency-mandatory-for-inventory-adjustments-and-refund-mutations) documents duplicate refunds and inventory inconsistency as real operational failure modes. Northstar includes a separate no-duplicate rule and regression case.
- [OWASP Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) recommends minimizing agent functionality, permissions, and autonomy around consequential actions.
- [OWASP Agentic AI threats and mitigations](https://genai.owasp.org/resource/agentic-ai-threats-and-mitigations/) provides a broad threat-model reference for emerging agentic threats and mitigations.
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework) treats AI risk across design, development, deployment, evaluation, and operation rather than as a single model-quality score.
- [OpenAI guardrails and approvals guidance](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals) places validation and approval around consequential tool actions.
- The [τ-bench paper](https://arxiv.org/abs/2406.12045) motivates evaluating agents in stateful tool-and-policy interactions instead of relying only on static question answering.

These sources inform the problem framing; they do not certify Aletheia's design
or current implementation.

## Design system chosen

Hallmark classification:

- Genre: modern-minimal
- Macrostructure: Narrative Workflow
- Theme: Cobalt adaptation
- Navigation: visible jump command plus direct workspace action
- Footer: closing product statement rather than a generic four-column sitemap
- Enrichment: an original policy-decision trace, without fake browser or IDE chrome

Visual system:

- cool near-white paper and cool graphite ink;
- one electric-cobalt brand signal, plus restrained semantic status colors;
- Newsreader for display, Geist for body copy and UI, and Geist Mono for the policy trace and keyboard/code UI;
- hairline structure and tight radii instead of glass, large shadows, gradient text, or decorative WebGL;
- a 4-point semantic spacing scale in the root `tokens.css`.

## Motion budget

The public page uses three motion primitives:

1. one coordinated hero settle on initial load;
2. one typed policy decision that plays once and then remains static;
3. short press/hover feedback on controls.

The main headline is always complete text, not a deleting/rotating typewriter.
No parallax, cursor follower, autoplay carousel, infinite background, shader, or
scroll hijacking is used. `prefers-reduced-motion` removes spatial motion and
shows the final decision immediately.

## Responsive and accessibility contract

The landing page is browser-tested at 320, 375, 414, and 768 CSS pixels in
addition to the desktop flows. The checks cover:

- no horizontal overflow;
- single-line primary affordances;
- a semantic ordered workflow;
- keyboard operation for the jump palette;
- escape dismissal and native dialog focus behavior;
- visible focus styling;
- static reduced-motion rendering;
- textual status in addition to color.

## When to revisit the skipped libraries

- Add GSAP only if a future real product tour needs a multi-element timeline
  that native CSS or the View Transitions API cannot express clearly.
- Add Lenis only to an isolated marketing surface after verifying anchors,
  nested scrolling, assistive technology, and reduced-motion behavior.
- Add Vanta only if interactive 3D communicates a product capability; never as
  ambient filler, and always with a static/data-saver/reduced-motion fallback.
- Copy a React Bits component only after auditing its semantics, cleanup,
  reduced-motion behavior, dependency cost, and license obligations. Record the
  exact source path and notice in `THIRD_PARTY_NOTICES.md`.

The current decision is deliberate restraint: the source conflict, runtime
order state, and blocked-mutation trace are more persuasive than a decorative
animation stack.
