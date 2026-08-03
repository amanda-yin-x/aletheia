# Third-party notices

Aletheia uses open-source libraries whose licences are recorded in the Python
and pnpm lockfiles.

The project-scoped Hallmark Codex design skill under
`.codex/skills/hallmark` was copied from `Nutlope/hallmark` revision
`aeb42fb354ff4efa36ab475773a082315a3af2ce`. It is copyright 2026 Hallmark
contributors and licensed under MIT; its full licence and provenance are
retained inside that directory.

React Bits, Vanta, GSAP, and Lenis were reviewed as landing-page references but
are not copied into or installed by Aletheia. See `docs/design-references.md`
for the pinned source register and design decisions.

The optional tau3 Retail adapter targets `sierra-research/tau2-bench` tag
`v1.0.1` (expected short commit `fc0055d`), copyright Sierra Research 2025,
licensed under MIT. Provenance-checked upstream inputs for the selected 17
Retail tasks are currently present under `data/benchmarks/tau3-retail`; no
Aletheia benchmark result is present or claimed. The sync command verifies the
pinned tag/commit and file hashes before replacing those inputs.

Research references: [tau-bench](https://arxiv.org/abs/2406.12045),
[tau2-bench](https://arxiv.org/abs/2506.07982),
[Amazon tau2-Bench-Verified](https://github.com/amazon-agi/tau2-bench-verified),
[correction audit](https://github.com/amazon-agi/tau2-bench-verified/blob/main/FIXES.md),
and [SABER](https://arxiv.org/abs/2512.07850).
