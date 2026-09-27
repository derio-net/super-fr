# CI hardening — implementation plan

Spec: `docs/superpowers/specs/2026-09-27-ci-hardening-design.md` (batch
`ci-hardening`: #707 + #706, one PR).

One agentic phase: the change is confined to `.github/**`, two test files and
the acceptance matrix, and every part is verified by the same unit suite and the
PR's own CI run. There is no second phase to smoke-test.

- Task 1 builds the tripwire first (red against today's tag pins), then pins
  every remote action to the SHA re-resolved from its tag and adds Dependabot.
- Task 2 adds `ci-ok`, pinned by a structural test: `needs` must equal every
  other job, so a future job cannot fall outside the gate.
- Task 3 moves the three acceptance rows and runs the full gate.

Out of bounds: `packages/**` (other batches own it; the consumer scaffold's tag
pins are a follow-up issue) and `main`'s ruleset.
