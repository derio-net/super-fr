# Writing standards for super-fr's published docs — plan

Spec: `docs/superpowers/specs/2026-11-13-writing-standards-docs-design.md`.

Six agentic phases:

1. **Wiring (skeleton).** The script, its test, the pin, the terms file, the three
   front-matter exceptions, the authoring rule and its mirror, and the recorded
   baseline. The CI gate is NOT on yet: `ci-ok` depends on `site-build`, so turning the
   gate on before every page passes would make every later phase's CI red.
2. **Reference pages to `ste`** (8 pages, `cli.md` prose only).
3. **Guides to `ste`** (9 pages).
4. **Explainers to `plain-language`, part 1** (6 pages).
5. **Explainers to `plain-language`, part 2** (6 pages).
6. **`01-fr-goal.md` (`plain-language`), `why-fr.md` (`elements-of-style`), then the CI
   gate on.**

## Per batch

Each rewrite task is one batch: RED (the checker fails it, baseline captured), GREEN
(rewrite, checker with `--preserve-from <baseline>` clean), REFACTOR (wording tripwires,
`fr docs check`, journal record). The blind fact review (blog-craft's `fact-keeper`)
needs an agent dispatch, which a phase executor cannot do, so the orchestrator runs it
per page in the phase's review step, with the baselines the executor wrote, and the
review record carries the per-page results (R8).

## Evidence

`tests: ci` throughout (`.fr/ci.yaml` gates on `ci-ok`); the draft PR opens when
implementation starts.
