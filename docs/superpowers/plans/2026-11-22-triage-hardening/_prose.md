# Triage intake hardening — implementation plan

Spec: `docs/superpowers/specs/2026-11-22-triage-hardening-design.md`.

Three agentic phases, each an independently reviewable ask:

1. **Intake trust boundary** (R1-R5, R7) — the skeleton and the `hard` phase: facts schema 16,
   the content digest and admit marker, the shared comment read, withheld titles, ignored claim
   markers, the `fr triage admit` command and every text that said the label admits.
2. **Batches and dedupe** (R6, R8-R10) — one set-apart predicate in `sets.py`, the `obsolete`
   stage and each reader of the stage (dependencies, waves, cancel), check and the Batches page.
3. **Collect, privacy, page script** (R11-R13) — judged PRs past the list limit, snapshot keys in
   the privacy guard, the filter-script guard. Depends only on phase 1 (collect.py and render.py
   both change in phase 1).

Every step is TDD: RED test first, GREEN change, REFACTOR or a recorded reason.
