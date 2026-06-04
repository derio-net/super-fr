# vk-isolation suite — implementation narrative

Spec: docs/superpowers/specs/2026-06-04-vk-isolation-suite-design.md

Build order: the click fix first (it unblocks `vk skills`, which P5 extends);
then the isolation core behind a Target protocol with every subprocess
(git/devcontainer/gh/docker) behind an injectable runner seam so the whole
lifecycle is unit-testable without Docker; then the thin typer layer; then the
vk-init scaffolder (pure file-writing, fully testable); finally the three
SKILL.md files and the wiring edits, where the existing validation suite
(frontmatter, ≤120 lines) acts as the gate.

Key invariants, from the spec:

- Worktrees default OUTSIDE the repo (~/.cache/vk/worktrees/<repo>/<branch>);
  state lives in <base>/.git/vk/isolation/<branch>.json — nothing committable.
- `up` always adds a second mount: the base repo's .git at the same absolute
  path, read-write — linked worktrees are unusable in-container without it.
- The CLI is agent-agnostic plain shell; no Claude-specific behavior.
- Hard requirements stay hard: no repo / no profile → exit 2 + vk-init
  pointer. Never degrade to unisolated.
- Secrets: host env-file per repo+profile; placeholders scaffolded;
  never committed, never baked into images.

Docker/devcontainer-CLI integration is exercised by the post-merge Test Plan
(operator-driven), not by unit tests.
